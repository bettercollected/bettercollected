"""Account deletion never depends on the Google Forms service, and never drops
the user's stored Google credentials silently.

The account, its sessions and its workspace data go first. Then the provider
service deletes the stored credentials; when it fails, or in
GOOGLE_FORMS_IMPORT=off, a retryable ``purge_provider_credentials`` job is
queued (only the queuing is retried in the deletion). A purge that cannot be
queued makes the deletion fail after the erasure, so it is retried and shows.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from procrastinate.testing import InMemoryConnector

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.services import credential_purge as purge_module
from backend.app.services.credential_purge import (
    CredentialPurge,
    CredentialPurgeFailed,
    CredentialPurgeNotQueued,
    unseal,
)
from backend.app.services.temporal_service import TemporalService
from backend.config import settings
from backend.jobs import tasks
from backend.jobs.app import app
from common.db import load_flags
from tests.app.controllers.data import testUser

GOOGLE_URL = "http://google-forms.invalid"
LOGGERS = ("backend.app.services.credential_purge", "backend.app.services.auth_service")


@pytest.fixture()
async def google_provider_config():
    await container.form_provider_service().add_provider(
        FormProviderConfigDto(
            enabled=True,
            provider_name="google",
            provider_url=GOOGLE_URL,
            auth_callback_url=f"{GOOGLE_URL}/google/oauth/callback",
        )
    )


@pytest.fixture(autouse=True)
def no_queue_pause(monkeypatch):
    monkeypatch.setattr(purge_module, "QUEUE_RETRY_SECONDS", 0)


class Google:
    """The Google Forms service's erase (POST) and the auth service's account
    DELETE: ``answer`` is an exception to raise or a status for the Google
    service; the auth service always answers 200."""

    def __init__(self, answer):
        self.answer = answer
        self.session = MagicMock()
        self.session.delete = AsyncMock(side_effect=self._call)
        self.session.post = AsyncMock(side_effect=self._call)

    async def _call(self, url, **kwargs):
        if url.startswith(GOOGLE_URL):
            if isinstance(self.answer, BaseException):
                raise self.answer
            return MagicMock(status=self.answer)
        return MagicMock(status=200)

    def calls(self, prefix=GOOGLE_URL):
        made = self.session.delete.await_args_list + self.session.post.await_args_list
        return [c for c in made if c.args[0].startswith(prefix)]

    def __enter__(self):
        self._patch = patch(
            "backend.app.services.auth_service.AiohttpClient.get_aiohttp_client",
            return_value=self.session,
        )
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()


@pytest.fixture()
def queue():
    with patch.object(
        container.temporal_service(),
        "queue_credential_purge",
        AsyncMock(return_value="queued"),
    ) as queued:
        yield queued


def _logged(caplog) -> str:
    return " ".join(r.getMessage() for r in caplog.records if r.name in LOGGERS)


FAILURES = [
    pytest.param(aiohttp.ClientConnectionError("refused"), id="unreachable"),
    pytest.param(asyncio.TimeoutError(), id="timeout"),
    pytest.param(500, id="error-status"),
    pytest.param(404, id="not-found"),
]


@pytest.mark.parametrize("answer", FAILURES)
async def test_a_failed_delete_queues_a_purge_and_logs_ids_only(
    google_provider_config, queue, caplog, answer
):
    with Google(answer) as google, caplog.at_level(logging.WARNING):
        await container.auth_service().delete_credentials_from_integrations(testUser)

    assert len(google.calls()) == 1
    (purge,) = queue.await_args.args
    assert purge == CredentialPurge(user_id=testUser.id, email=testUser.sub, provider="google")
    logged = _logged(caplog)
    assert testUser.id in logged and testUser.sub not in logged


async def test_a_successful_delete_queues_nothing(google_provider_config, queue):
    with Google(200) as google:
        await container.auth_service().delete_credentials_from_integrations(testUser)
    assert len(google.calls()) == 1
    queue.assert_not_awaited()


async def test_the_email_is_never_in_the_url(google_provider_config, queue):
    """The service's access log records URLs: an erasure sends the email in
    the body only, and nothing in the URL names the person."""
    with Google(200) as google:
        await container.auth_service().delete_credentials_from_integrations(testUser)
    (call,) = google.calls()
    assert call.args[0] == f"{GOOGLE_URL}/google/oauth/credentials/erase"
    assert google.session.post.await_count == 1
    assert "params" not in call.kwargs
    assert call.kwargs["json"] == {"user_id": testUser.id, "email": testUser.sub}
    for made in google.session.post.await_args_list + google.session.delete.await_args_list:
        assert testUser.sub not in made.args[0]
        assert testUser.sub not in str(made.kwargs.get("params", ""))


async def test_a_disabled_provider_is_still_purged(queue):
    """Disabling a provider stops new use, not the erasure of what it
    already stores: the purge is attempted, and queued when it fails."""
    await container.form_provider_service().add_provider(
        FormProviderConfigDto(
            enabled=False,
            provider_name="google",
            provider_url=GOOGLE_URL,
            auth_callback_url=f"{GOOGLE_URL}/google/oauth/callback",
        )
    )
    with Google(200) as google:
        await container.auth_service().delete_credentials_from_integrations(testUser)
    assert len(google.calls()) == 1
    queue.assert_not_awaited()

    with Google(503) as google:
        await container.auth_service().delete_credentials_from_integrations(testUser)
    assert len(google.calls()) == 1
    (purge,) = queue.await_args.args
    assert purge == CredentialPurge(user_id=testUser.id, email=testUser.sub, provider="google")


async def test_the_service_call_has_a_short_timeout(google_provider_config, queue):
    with Google(200) as google:
        await container.auth_service().delete_credentials_from_integrations(testUser)
    timeout = google.calls()[0].kwargs["timeout"]
    assert isinstance(timeout, aiohttp.ClientTimeout) and timeout.total <= 30


async def test_the_auth_delete_has_a_timeout_in_seconds(google_provider_config, queue):
    with Google(200) as google:
        await container.auth_service().delete_user_form_auth(testUser)
    (call,) = google.calls(settings.auth_settings.BASE_URL)
    assert isinstance(call.kwargs["timeout"], aiohttp.ClientTimeout)
    assert call.kwargs["timeout"].total <= 60


async def test_off_never_calls_the_service_and_queues_a_purge(
    google_provider_config, queue, monkeypatch
):
    monkeypatch.setattr(settings.google_forms, "IMPORT", "off")
    with Google(200) as google:
        await container.auth_service().delete_credentials_from_integrations(testUser)
    assert google.calls() == []
    assert queue.await_count == 1


@pytest.mark.parametrize("mode", ["on", "readonly", "off"])
async def test_erasure_comes_first_even_when_the_purge_cannot_be_queued(
    google_provider_config, workspace, monkeypatch, mode
):
    monkeypatch.setattr(settings.google_forms, "IMPORT", mode)
    sessions = AsyncMock()
    with Google(503) as google, patch.object(
        container.temporal_service(),
        "queue_credential_purge",
        AsyncMock(side_effect=RuntimeError("queue down")),
    ) as queued, patch.object(
        container.session_service(), "delete_all_for_user", sessions
    ), patch(
        "backend.app.services.auth_service.event_logger_service.delete_contact",
        AsyncMock(),
    ) as marketing_contact:
        with pytest.raises(CredentialPurgeNotQueued):
            await container.auth_service().delete_user(testUser)
    # the marketing contact is erased too before the failure surfaces
    marketing_contact.assert_awaited_once()

    # only the queuing was retried, after the account, sessions and workspace
    assert queued.await_count == purge_module.QUEUE_ATTEMPTS
    assert len(google.calls(settings.auth_settings.BASE_URL)) == 1
    sessions.assert_awaited_once_with(testUser.id)
    assert (
        await container.workspace_repo().get_default_workspace_by_owner_id(testUser.id)
        is None
    )
    assert len(google.calls()) == (0 if mode == "off" else 1)


async def test_a_failed_delete_leaves_a_pending_purge_that_later_succeeds(
    google_provider_config, workspace, monkeypatch
):
    connector = InMemoryConnector()
    jobs_service = TemporalService(
        server_uri="unused:7233",
        namespace="default",
        crypto=container.crypto(),
        flags=load_flags({"JOBS_BACKEND__purge_provider_credentials": "postgres"}),
        jobs=app,
    )
    google = Google(503)
    with app.replace_connector(connector), google, patch.object(
        container.credential_purge_service(), "_jobs", jobs_service
    ):
        await container.auth_service().delete_user(testUser)

        (job,) = [
            j for j in connector.jobs.values() if j["task_name"] == "purge_provider_credentials"
        ]
        assert job["status"] == "todo" and job["args"]["user_id"] == testUser.id
        # the email travels encrypted
        assert testUser.sub not in job["args"]["sealed"]
        assert unseal(container.crypto(), job["args"]["sealed"]).email == testUser.sub

        # still failing: the attempt is retried later (the job stays pending)
        await app.run_worker_async(wait=False, install_signal_handlers=False)
        assert job["status"] == "todo" and job["attempts"] == 1
        assert job["scheduled_at"] is not None

        # the service is back: the next attempt erases them
        google.answer = 200
        job["scheduled_at"] = None
        await app.run_worker_async(wait=False, install_signal_handlers=False)
        assert job["status"] == "succeeded"
    assert len(google.calls()) == 3  # the deletion, the failed and the good attempt


async def test_the_purge_is_queued_once_with_an_encrypted_email():
    connector = InMemoryConnector()
    jobs_service = TemporalService(
        server_uri="unused:7233",
        namespace="default",
        crypto=container.crypto(),
        flags=load_flags({"JOBS_BACKEND__purge_provider_credentials": "postgres"}),
        jobs=app,
    )
    purge = CredentialPurge(user_id="u1", email="secret@example.com", provider="google")
    with app.replace_connector(connector):
        assert await jobs_service.queue_credential_purge(purge) == "queued"
        assert await jobs_service.queue_credential_purge(purge) == "already_queued"
    (job,) = connector.jobs.values()
    assert job["queueing_lock"] == "purge_provider_credentials:google:u1"
    assert "secret@example.com" not in str(job["args"])


async def test_a_purge_routed_to_temporal_cannot_be_queued():
    jobs_service = TemporalService(
        server_uri="unused:7233",
        namespace="default",
        crypto=container.crypto(),
        flags=load_flags({}),
        jobs=app,
    )
    with pytest.raises(RuntimeError):
        await jobs_service.queue_credential_purge(
            CredentialPurge(user_id="u1", email="e@example.com", provider="google")
        )


class TestTheJobInOff:
    """GOOGLE_FORMS_IMPORT=off: no call to the service; the database function
    when the Google store is Postgres only, else the job keeps failing."""

    PURGE = CredentialPurge(user_id="u1", email="e@example.com", provider="google")

    async def test_postgres_store_uses_the_definer_function(self, monkeypatch):
        monkeypatch.setattr(settings.google_forms, "IMPORT", "off")
        monkeypatch.setenv("DB_WRITE_MODE__GOOGLE", "postgres")
        monkeypatch.setenv("DB_READ_SOURCE__GOOGLE", "postgres")
        conn = MagicMock()
        conn.execute = AsyncMock(return_value=MagicMock(scalar=MagicMock(return_value=2)))
        engine = MagicMock()
        engine.begin.return_value.__aenter__ = AsyncMock(return_value=conn)
        engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        service = purge_module.CredentialPurgeService(MagicMock(), MagicMock(), engine)
        with Google(200) as google:
            assert await service.purge(self.PURGE) == "deleted"
        assert google.calls() == []
        statement, params = conn.execute.await_args.args
        assert "google.purge_user_credentials" in str(statement)
        assert params == {"user_id": "u1", "email": "e@example.com"}

    @pytest.mark.parametrize("write_mode", ["mongo", "dual", "postgres_primary_dual"])
    async def test_mongo_and_dual_stores_rely_on_the_service(
        self, monkeypatch, write_mode
    ):
        monkeypatch.setattr(settings.google_forms, "IMPORT", "off")
        monkeypatch.setenv("DB_WRITE_MODE__GOOGLE", write_mode)
        monkeypatch.setenv(
            "DB_READ_SOURCE__GOOGLE",
            "postgres" if write_mode == "postgres_primary_dual" else "mongo",
        )
        service = purge_module.CredentialPurgeService(MagicMock(), MagicMock(), MagicMock())
        with pytest.raises(CredentialPurgeFailed):
            await service.purge(self.PURGE)

    @pytest.mark.parametrize("mode", ["on", "readonly"])
    async def test_on_and_readonly_go_through_the_service_which_revokes(
        self, google_provider_config, monkeypatch, mode
    ):
        monkeypatch.setattr(settings.google_forms, "IMPORT", mode)
        monkeypatch.setenv("DB_WRITE_MODE__GOOGLE", "postgres")
        with Google(200) as google:
            assert await container.credential_purge_service().purge(self.PURGE) == "deleted"
        assert len(google.calls()) == 1


async def test_a_missing_provider_url_still_queues(google_provider_config, queue):
    with Google(200), patch.object(
        container.form_provider_service(),
        "get_provider_url",
        AsyncMock(side_effect=HTTPException(404, "not found")),
    ):
        await container.auth_service().delete_credentials_from_integrations(testUser)
    assert queue.await_count == 1
