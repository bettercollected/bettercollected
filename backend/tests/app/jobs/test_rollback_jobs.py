"""Rows a release 4.1 stack left in the Postgres job queue, run by this
release after a rollback (``DB_*=postgres``, ``JOBS_BACKEND=postgres``).

A worker that does not know a task name fails the row (``TaskNotFound``, no
retry), so every task name 4.1 can queue must be registered here. The two
erasure/revocation jobs do their real work; the two periodic ones complete
without doing anything. Uses procrastinate's in-memory connector: no queue
database. The provider service and Google are stand-ins."""

import json
import logging
from unittest.mock import AsyncMock

import httpx
import pytest
from loguru import logger
from procrastinate.testing import InMemoryConnector

from backend.app.container import container
from backend.app.services.credential_purge import (
    PURGE_ATTEMPTS,
    PURGE_RETRY_SECONDS,
    CredentialPurge,
)
from backend.app.services.google_grant_revocation import (
    REVOKE_ATTEMPTS,
    REVOKE_RETRY_SECONDS,
    REVOKE_URL,
)
from backend.app.utils import AiohttpClient
from backend.jobs import tasks
from backend.jobs.app import DEFAULT_QUEUE, JOB_NAMES, app

# every task name release 4.1's backend registers (backend/jobs/tasks.py) plus
# run_action, which the actions-executor owns
RELEASE_41_TASKS = {
    "delete_user",
    "purge_provider_credentials",
    "revoke_google_grant",
    "delete_response",
    "import_form",
    "expire_stale_imports",
    "scim_reconcile",
    "sso_release_retry",
    "recheck_verified_domains",
}

EMAIL = "erased-person-secret@example.com"
TOKEN = "ya29.rollback-secret-token"


@pytest.fixture
def memory_jobs():
    connector = InMemoryConnector()
    with app.replace_connector(connector):
        yield connector


def sealed(payload: dict) -> str:
    """What 4.1 writes: the JSON of its dataclass, encrypted with the backend key."""
    return container.crypto().encrypt(json.dumps(payload))


def purge_payload(user_id="user-1", provider="google") -> dict:
    return {"user_id": user_id, "email": EMAIL, "provider": provider}


class FakeProviderService:
    """The response of the provider (Google Forms) service to a DELETE."""

    def __init__(self, status=200):
        self.status = status
        self.error = None
        self.calls = []
        self.open = 0  # responses not released yet

    def delete(self, url, params=None, timeout=None, **kwargs):
        """Like aiohttp's: used as ``async with``, which releases the response."""
        self.calls.append((url, dict(params or {})))
        fake = self

        class Reply:
            status = fake.status

            async def __aenter__(self):
                if fake.error:
                    raise fake.error
                fake.open += 1
                return self

            async def __aexit__(self, *exc):
                fake.open -= 1

        return Reply()


@pytest.fixture
def provider(monkeypatch):
    fake = FakeProviderService()
    monkeypatch.setattr(AiohttpClient, "get_aiohttp_client", lambda: fake)
    monkeypatch.setattr(
        container.form_provider_service(),
        "get_provider_url",
        AsyncMock(return_value="http://google-service"),
    )
    return fake


class FakeGoogle:
    def __init__(self, status=200, body=None):
        self.status, self.body = status, body or {}
        self.requests = []

    def __enter__(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            if isinstance(self.body, Exception):
                raise self.body
            return httpx.Response(self.status, json=self.body)

        self._service = container.google_grant_service()
        self._service.transport = httpx.MockTransport(handler)
        return self

    def __exit__(self, *exc):
        self._service.transport = None


@pytest.fixture
def log_lines(caplog):
    """Everything logged (std logging and loguru) while the test runs."""
    caplog.set_level(logging.DEBUG)
    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    yield lines, caplog
    logger.remove(sink)


def nothing_secret_logged(log_lines, *secrets):
    lines, caplog = log_lines
    text = "\n".join(lines) + "\n" + caplog.text
    for secret in secrets:
        assert secret not in text


async def run_worker():
    await app.run_worker_async(wait=False, install_signal_handlers=False)


def jobs_named(connector, name):
    return [j for j in connector.jobs.values() if j["task_name"] == name]


def test_every_task_release_41_can_queue_is_registered():
    registered = set(app.tasks)
    assert RELEASE_41_TASKS <= registered, RELEASE_41_TASKS - registered


def test_retry_strategies_match_release_41():
    purge = app.tasks["purge_provider_credentials"].retry_strategy
    revoke = app.tasks["revoke_google_grant"].retry_strategy
    assert (purge.max_attempts, purge.wait) == (PURGE_ATTEMPTS, PURGE_RETRY_SECONDS)
    assert (revoke.max_attempts, revoke.wait) == (REVOKE_ATTEMPTS, REVOKE_RETRY_SECONDS)
    assert PURGE_ATTEMPTS == REVOKE_ATTEMPTS == 48
    assert PURGE_RETRY_SECONDS == REVOKE_RETRY_SECONDS == 3600
    assert {"purge_provider_credentials", "revoke_google_grant"} <= set(JOB_NAMES)


# -- purge_provider_credentials ----------------------------------------------
async def test_a_queued_purge_erases_the_credentials(memory_jobs, provider, log_lines):
    await tasks.purge_provider_credentials.defer_async(
        sealed=sealed(purge_payload()), user_id="user-1"
    )
    await run_worker()

    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "succeeded" and job["queue_name"] == DEFAULT_QUEUE
    assert provider.calls == [
        (
            "http://google-service/google/oauth/credentials",
            {"user_id": "user-1", "email": EMAIL},
        )
    ]
    assert provider.open == 0  # the response was released
    nothing_secret_logged(log_lines, EMAIL)
    # the job row holds the argument only encrypted
    assert EMAIL not in json.dumps(job["args"])


async def test_a_purge_is_idempotent(memory_jobs, provider):
    for _ in range(2):  # the same job twice: the service answers 200 both times
        await tasks.purge_provider_credentials.defer_async(
            sealed=sealed(purge_payload()), user_id="user-1"
        )
    await run_worker()
    jobs = jobs_named(memory_jobs, "purge_provider_credentials")
    assert [j["status"] for j in jobs] == ["succeeded", "succeeded"]
    assert len(provider.calls) == 2


async def test_an_unreachable_service_retries_without_leaking(
    memory_jobs, provider, log_lines
):
    provider.error = OSError(f"connect failed for http://x/?email={EMAIL}")
    await tasks.purge_provider_credentials.defer_async(
        sealed=sealed(purge_payload()), user_id="user-1"
    )
    await run_worker()
    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "todo" and job["attempts"] == 1  # retried later
    nothing_secret_logged(log_lines, EMAIL)


@pytest.mark.parametrize("status", [500, 502, 503, 429, 408])
async def test_a_server_side_failure_retries(memory_jobs, provider, status):
    provider.status = status
    await tasks.purge_provider_credentials.defer_async(
        sealed=sealed(purge_payload()), user_id="user-1"
    )
    await run_worker()
    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "todo" and job["attempts"] == 1
    assert provider.open == 0  # released on a failure answer too


@pytest.mark.parametrize("status", [400, 401, 404, 422])
async def test_a_refused_request_fails_once_not_for_two_days(
    memory_jobs, provider, status
):
    provider.status = status
    await tasks.purge_provider_credentials.defer_async(
        sealed=sealed(purge_payload()), user_id="user-1"
    )
    await run_worker()
    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "failed"


async def test_a_purge_for_another_user_does_nothing(memory_jobs, provider):
    await tasks.purge_provider_credentials.defer_async(
        sealed=sealed(purge_payload("user-1")), user_id="user-2"
    )
    await run_worker()
    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "failed" and provider.calls == []


async def test_an_unreadable_purge_fails_once(memory_jobs, provider, log_lines):
    await tasks.purge_provider_credentials.defer_async(
        sealed="not-an-encrypted-value", user_id="user-1"
    )
    await run_worker()
    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "failed" and provider.calls == []


@pytest.mark.parametrize("unknown", [None, AttributeError("no record")])
async def test_an_unknown_provider_fails_once(memory_jobs, provider, unknown):
    # (the real service raises AttributeError on the missing record)
    lookup = container.form_provider_service().get_provider_url
    if unknown is None:
        lookup.return_value = None
    else:
        lookup.side_effect = unknown
    await tasks.purge_provider_credentials.defer_async(
        sealed=sealed(purge_payload(provider="typeform")), user_id="user-1"
    )
    await run_worker()
    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "failed" and provider.calls == []


async def test_unreadable_provider_records_retry(memory_jobs, provider):
    container.form_provider_service().get_provider_url.side_effect = RuntimeError("db")
    await tasks.purge_provider_credentials.defer_async(
        sealed=sealed(purge_payload()), user_id="user-1"
    )
    await run_worker()
    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "todo" and job["attempts"] == 1 and provider.calls == []


@pytest.mark.parametrize(
    "name", ["", "../admin", "google/../x", "Google", "a b", "google\n"]
)
async def test_a_provider_name_that_is_not_one_is_refused(memory_jobs, provider, name):
    await tasks.purge_provider_credentials.defer_async(
        sealed=sealed(purge_payload(provider=name)), user_id="user-1"
    )
    await run_worker()
    (job,) = jobs_named(memory_jobs, "purge_provider_credentials")
    assert job["status"] == "failed" and provider.calls == []


def test_the_purge_request_has_the_shape_release_41_seals():
    assert set(CredentialPurge.__dataclass_fields__) == {
        "user_id",
        "email",
        "provider",
    }


# -- revoke_google_grant -----------------------------------------------------
def revoke_payload(token=TOKEN) -> dict:
    return {"form_id": "form-1", "action_id": "action-1", "token": token}


async def defer_revoke(payload=None, **override):
    args = {"form_id": "form-1", "action_id": "action-1", **override}
    await tasks.revoke_google_grant.defer_async(
        sealed=sealed(payload or revoke_payload()), **args
    )


async def test_a_queued_revocation_revokes_at_google(memory_jobs, log_lines):
    with FakeGoogle() as google:
        await defer_revoke()
        await run_worker()

    (job,) = jobs_named(memory_jobs, "revoke_google_grant")
    assert job["status"] == "succeeded"
    (request,) = google.requests
    assert str(request.url) == REVOKE_URL == "https://oauth2.googleapis.com/revoke"
    assert request.method == "POST"
    assert request.content == f"token={TOKEN}".encode()
    nothing_secret_logged(log_lines, TOKEN)
    assert TOKEN not in json.dumps(job["args"])  # only sealed in the job row


async def test_a_token_google_already_invalidated_is_done(memory_jobs):
    with FakeGoogle(400, {"error": "invalid_token"}):
        await defer_revoke()
        await run_worker()
    (job,) = jobs_named(memory_jobs, "revoke_google_grant")
    assert job["status"] == "succeeded"


async def test_revocation_is_idempotent(memory_jobs):
    with FakeGoogle() as google:
        await defer_revoke()
        await defer_revoke()
        await run_worker()
    jobs = jobs_named(memory_jobs, "revoke_google_grant")
    assert [j["status"] for j in jobs] == ["succeeded", "succeeded"]
    assert len(google.requests) == 2


@pytest.mark.parametrize(
    "status,body", [(500, {}), (503, {}), (400, {"error": "invalid_request"})]
)
async def test_a_failed_revocation_retries_without_leaking(
    memory_jobs, log_lines, status, body
):
    with FakeGoogle(status, body):
        await defer_revoke()
        await run_worker()
    (job,) = jobs_named(memory_jobs, "revoke_google_grant")
    assert job["status"] == "todo" and job["attempts"] == 1
    nothing_secret_logged(log_lines, TOKEN)


async def test_an_unreachable_google_retries_without_leaking(memory_jobs, log_lines):
    with FakeGoogle(body=httpx.ConnectError(f"cannot reach {TOKEN}")):
        await defer_revoke()
        await run_worker()
    (job,) = jobs_named(memory_jobs, "revoke_google_grant")
    assert job["status"] == "todo" and job["attempts"] == 1
    nothing_secret_logged(log_lines, TOKEN)


async def test_a_revocation_for_another_action_does_nothing(memory_jobs):
    with FakeGoogle() as google:
        await defer_revoke(action_id="another-action")
        await run_worker()
    (job,) = jobs_named(memory_jobs, "revoke_google_grant")
    assert job["status"] == "failed" and google.requests == []


async def test_an_unreadable_revocation_fails_once(memory_jobs):
    with FakeGoogle() as google:
        await tasks.revoke_google_grant.defer_async(
            sealed="not-an-encrypted-value", form_id="form-1", action_id="action-1"
        )
        await run_worker()
    (job,) = jobs_named(memory_jobs, "revoke_google_grant")
    assert job["status"] == "failed" and google.requests == []


# -- the periodic jobs 4.1 schedules -----------------------------------------
@pytest.mark.parametrize("name", ["sso_release_retry", "recheck_verified_domains"])
async def test_a_leftover_periodic_row_completes_and_does_nothing(
    memory_jobs, monkeypatch, name
):
    touched = AsyncMock()
    # what 4.1's bodies would have called
    monkeypatch.setattr(
        container.workspace_domain_service(), "recheck_verified_domains", touched
    )
    monkeypatch.setattr(container.sso_connection_service(), "_polis", touched)

    await app.configure_task(name, queueing_lock=name).defer_async(timestamp=1760000000)
    await run_worker()

    (job,) = jobs_named(memory_jobs, name)
    assert job["status"] == "succeeded"
    assert not touched.called and not touched.mock_calls


def test_this_release_does_not_schedule_the_periodic_jobs_itself():
    scheduled = {p.task.name for p in app.periodic_registry.periodic_tasks.values()}
    assert not scheduled & {"sso_release_retry", "recheck_verified_domains"}
