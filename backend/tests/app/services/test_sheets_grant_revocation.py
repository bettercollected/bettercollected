"""After re-consent (services/sheets_grant_revocation.py): the new drive.file
grant is stored and the re-consent markers cleared in one write, then the old
broad grant is revoked at Google's pinned revoke address. A failed revocation
queues a retry job and never blocks the new grant; ``invalid_token`` counts as
done; nothing happens under ``google_service``; no token is ever logged.
Google is faked (tests/app/sheets_helpers.py); nothing leaves the process."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from loguru import logger
from procrastinate.testing import InMemoryConnector

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.form_integration import (
    FormActionType,
    FormIntegrationType,
)
from backend.app.services import sheets_grant_revocation as grants
from backend.app.services.google_sheets_oauth import DRIVE_FILE_SCOPE
from backend.app.services.sheets_reconsent import (
    MAILED_AT,
    NEEDS_RECONSENT,
    SKIPPED_RUNS,
)
from backend.app.services.temporal_service import TemporalService
from backend.jobs.app import app
from common.db import load_flags
from tests.app.controllers.data import testUser
from tests.app.sheets_helpers import (
    ACCESS_TOKEN,
    CLIENT_ID,
    REFRESH_TOKEN,
    TOKEN_URI,
    backend_sheets_oauth,  # noqa: F401 (fixture)
    credential_dict,
    fake_google,  # noqa: F401 (fixture)
    sheets_client,  # noqa: F401 (fixture)
)

OAUTH_URL = f"/api/v1/integration/{FormIntegrationType.GOOGLE_SHEET.value}/oauth"
LEGACY_REFRESH = "legacy-refresh-token-value"
LEGACY_ACCESS = "legacy-access-token-value"
LEGACY_CLIENT = "google-forms-service-client.apps.fake-google.test"
SECRETS = (LEGACY_REFRESH, LEGACY_ACCESS, REFRESH_TOKEN, ACCESS_TOKEN)


def legacy_credential(**overrides) -> str:
    credential = {
        "token": LEGACY_ACCESS,
        "refresh_token": LEGACY_REFRESH,
        "token_uri": "https://evil.example.test/token",
        "client_id": LEGACY_CLIENT,
        "client_secret": "legacy-client-secret",
        "scopes": "https://www.googleapis.com/auth/spreadsheets "
        "https://www.googleapis.com/auth/drive",
        "expiry": "2026-01-01T00:00:00.000000Z",
        **overrides,
    }
    return container.crypto().encrypt(json.dumps(credential))


@pytest.fixture()
def logged(caplog):
    """Every log line: loguru's and the standard library's (procrastinate)."""
    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    caplog.set_level(logging.DEBUG)
    yield lambda: "\n".join(lines + [r.getMessage() for r in caplog.records])
    logger.remove(sink)


def assert_no_token(text: str):
    for secret in SECRETS:
        assert secret not in text


@pytest.fixture()
async def sheets_action():
    return await container.action_repository().create_global_action(
        ActionDto(
            name=FormIntegrationType.GOOGLE_SHEET.value,
            action_code="",
            type=FormActionType.EXTERNAL.value,
        ),
        testUser,
    )


@pytest.fixture()
async def legacy_connected(workspace_form, sheets_action):
    """A Sheets action holding a legacy credential, marked for re-consent."""
    form_id, action_id = workspace_form.form_id, str(sheets_action.id)
    await container.integration_action_service().add_credentials_to_form_action(
        form_id=form_id, action_id=action_id, credentials=legacy_credential()
    )
    repo = container.form_repo()
    await repo.update_action_parameters(form_id, action_id, values={"Title": "Sheet"})
    await repo.update_action_parameters(
        form_id,
        action_id,
        values={NEEDS_RECONSENT: "true", MAILED_AT: "2026-10-01T00:00:00+00:00"},
        increment=SKIPPED_RUNS,
    )
    return form_id, action_id


@pytest.fixture()
def jobs():
    """Revocation retries routed to an in-memory procrastinate queue."""
    connector = InMemoryConnector()
    service = TemporalService(
        server_uri="unused:7233",
        namespace="default",
        crypto=container.crypto(),
        flags=load_flags({"JOBS_BACKEND__revoke_google_grant": "postgres"}),
        jobs=app,
    )
    with app.replace_connector(connector), patch.object(
        container.sheets_grant_service(), "_jobs", service
    ):
        yield connector


def revoke_jobs(connector):
    return [j for j in connector.jobs.values() if j["task_name"] == grants.REVOKE_JOB]


async def run_worker():
    await app.run_worker_async(wait=False, install_signal_handlers=False)


async def _connect(client, cookies, form_id, action_id):
    state = container.crypto().encrypt(
        json.dumps({"client_referer_uri": None, "user_id": testUser.id})
    )
    return await client.post(
        f"{OAUTH_URL}/callback",
        cookies=cookies,
        json={"state": state, "code": "the-code", "form_id": form_id, "action_id": action_id},
    )


async def _stored(form_id, action_id):
    form = await container.form_repo().get_form_document_by_id(form_id)
    params = {p.name: p.value for p in (form.parameters or {}).get(action_id) or []}
    creds = [s.value for s in form.secrets[action_id] if s.name == "Credentials"]
    return params, creds


class TestSwitch:
    async def test_reconnecting_stores_the_grant_clears_the_markers_and_revokes_once(
        self,
        client,
        test_user_cookies,
        legacy_connected,
        backend_sheets_oauth,  # noqa: F811
        jobs,
        logged,
    ):
        form_id, action_id = legacy_connected
        response = await _connect(client, test_user_cookies, form_id, action_id)
        assert response.status_code == 200, response.text

        params, creds = await _stored(form_id, action_id)
        assert params == {"Title": "Sheet"}  # the markers are gone, the rest kept
        assert len(creds) == 1
        new = credential_dict(creds[0])
        assert new["scopes"] == DRIVE_FILE_SCOPE
        assert new["refresh_token"] == REFRESH_TOKEN
        # the old ciphertext is gone locally
        assert LEGACY_REFRESH not in json.dumps(
            (await container.form_repo().get_form_document_by_id(form_id)).model_dump(
                mode="json"
            )
        )
        # revoked once, with the old refresh token, form-encoded, at Google
        assert backend_sheets_oauth.revoke_requests() == [{"token": LEGACY_REFRESH}]
        assert revoke_jobs(jobs) == []
        assert_no_token(logged())

    async def test_a_failed_revocation_never_blocks_the_new_grant(
        self,
        client,
        test_user_cookies,
        legacy_connected,
        backend_sheets_oauth,  # noqa: F811
        jobs,
        logged,
    ):
        backend_sheets_oauth.revoke_status = 503
        form_id, action_id = legacy_connected
        response = await _connect(client, test_user_cookies, form_id, action_id)
        assert response.status_code == 200, response.text
        params, creds = await _stored(form_id, action_id)
        assert params == {"Title": "Sheet"}
        assert credential_dict(creds[0])["scopes"] == DRIVE_FILE_SCOPE
        (job,) = revoke_jobs(jobs)
        assert job["args"]["form_id"] == form_id
        assert job["args"]["action_id"] == action_id
        assert LEGACY_REFRESH not in json.dumps(job["args"])
        assert_no_token(logged())

    async def test_google_service_mode_never_revokes(
        self,
        client,
        test_user_cookies,
        legacy_connected,
        sheets_client,  # noqa: F811
        fake_google,  # noqa: F811
        jobs,
    ):
        assert container.integration_action_service()._sheets_grants is not None
        with patch.object(
            container.sheets_grant_service(), "store_new_grant"
        ) as store_new_grant:
            providers = [
                container.integration_service().integration__provider_factory.google_integration_provider,
                container.integration_provider().google_integration_provider,
            ]
            http_client = MagicMock()
            http_client.post = AsyncMock(return_value=legacy_credential())
            provider_service = MagicMock()
            provider_service.get_provider_url = AsyncMock(return_value="http://google")
            with patch.object(providers[0], "http_client", http_client), patch.object(
                providers[0], "form_provider_service", provider_service
            ), patch.object(providers[1], "http_client", http_client), patch.object(
                providers[1], "form_provider_service", provider_service
            ):
                form_id, action_id = legacy_connected
                response = await _connect(client, test_user_cookies, form_id, action_id)
        assert response.status_code == 200, response.text
        store_new_grant.assert_not_called()
        assert fake_google.revoke_requests() == []
        assert revoke_jobs(jobs) == []


class TestRevocation:
    """The service and the job, without the OAuth exchange."""

    @pytest.fixture()
    def service(self, sheets_client, fake_google):  # noqa: F811
        return container.sheets_grant_service()

    async def _replace(self, service, form_id, action_id, credential="new-ciphertext"):
        return await service.store_new_grant(form_id, action_id, credential)

    async def test_failure_queues_a_job_that_retries_until_done(
        self, service, legacy_connected, fake_google, jobs, logged  # noqa: F811
    ):
        form_id, action_id = legacy_connected
        fake_google.revoke_status = 500
        assert await self._replace(service, form_id, action_id) == "queued"
        params, creds = await _stored(form_id, action_id)
        assert creds == ["new-ciphertext"] and params == {"Title": "Sheet"}

        (job,) = revoke_jobs(jobs)
        assert job["status"] == "todo"
        # still failing: retried later
        await run_worker()
        assert job["status"] == "todo" and job["attempts"] == 1
        assert job["scheduled_at"] is not None

        # Google is back: the next attempt revokes it
        fake_google.revoke_status = 200
        job["scheduled_at"] = None
        await run_worker()
        assert job["status"] == "succeeded"
        assert [r["token"] for r in fake_google.revoke_requests()] == [LEGACY_REFRESH] * 3
        assert_no_token(logged())

    async def test_an_unreachable_google_queues_too(
        self, service, legacy_connected, fake_google, jobs, logged  # noqa: F811
    ):
        fake_google.fail_with = lambda request: httpx.ConnectTimeout("down", request=request)
        assert await self._replace(service, *legacy_connected) == "queued"
        assert len(revoke_jobs(jobs)) == 1
        assert_no_token(logged())

    async def test_invalid_token_counts_as_done(
        self, service, legacy_connected, fake_google, jobs  # noqa: F811
    ):
        fake_google.revoke_status = 400
        fake_google.revoke_body = {
            "error": "invalid_token",
            "error_description": "Token expired or revoked",
        }
        assert await self._replace(service, *legacy_connected) == "already_invalid"
        assert revoke_jobs(jobs) == []

    async def test_the_job_finishes_on_invalid_token(
        self, service, legacy_connected, fake_google, jobs  # noqa: F811
    ):
        fake_google.revoke_status = 502
        assert await self._replace(service, *legacy_connected) == "queued"
        (job,) = revoke_jobs(jobs)
        fake_google.revoke_status = 400
        fake_google.revoke_body = {"error": "invalid_token"}
        await run_worker()
        assert job["status"] == "succeeded"

    @pytest.mark.parametrize(
        "status, body",
        [(400, {"error": "invalid_request"}), (400, {}), (401, {}), (429, {}), (503, {})],
    )
    async def test_other_answers_are_failures(self, status, body, fake_google):  # noqa: F811
        fake_google.revoke_status, fake_google.revoke_body = status, body
        with pytest.raises(grants.GrantRevocationFailed) as failure:
            await grants.revoke_at_google("some-token", fake_google.transport)
        assert "some-token" not in str(failure.value)

    async def test_a_job_that_cannot_be_queued_never_blocks_the_grant(
        self, service, legacy_connected, fake_google, logged  # noqa: F811
    ):
        fake_google.revoke_status = 503
        # Temporal routing (the default): no procrastinate job for it
        unrouted = TemporalService(
            server_uri="unused:7233",
            namespace="default",
            crypto=container.crypto(),
            flags=load_flags({}),
            jobs=app,
        )
        with patch.object(service, "_jobs", unrouted):
            assert await self._replace(service, *legacy_connected) == "not_queued"
        _, creds = await _stored(*legacy_connected)
        assert creds == ["new-ciphertext"]
        assert_no_token(logged())

    async def test_a_drive_file_credential_is_not_revoked(
        self, service, workspace_form, sheets_action, fake_google, jobs  # noqa: F811
    ):
        form_id, action_id = workspace_form.form_id, str(sheets_action.id)
        await self._replace(
            service, form_id, action_id, legacy_credential(scopes=DRIVE_FILE_SCOPE)
        )
        assert await self._replace(service, form_id, action_id) == "not_legacy"
        assert fake_google.revoke_requests() == []

    async def test_a_first_connection_revokes_nothing(
        self, service, workspace_form, sheets_action, fake_google, jobs  # noqa: F811
    ):
        assert (
            await self._replace(service, workspace_form.form_id, str(sheets_action.id))
            == "no_previous"
        )
        assert fake_google.revoke_requests() == []

    @pytest.mark.parametrize("client_id", [CLIENT_ID, None, ""])
    async def test_a_legacy_grant_of_the_sign_in_client_is_only_deleted(
        self, client_id, service, workspace_form, sheets_action, fake_google, jobs  # noqa: F811
    ):
        """Revoking it would revoke the user's whole grant to that client,
        the new drive.file grant included."""
        form_id, action_id = workspace_form.form_id, str(sheets_action.id)
        await container.integration_action_service().add_credentials_to_form_action(
            form_id=form_id,
            action_id=action_id,
            credentials=legacy_credential(client_id=client_id),
        )
        assert await self._replace(service, form_id, action_id) == "same_client"
        assert fake_google.revoke_requests() == []
        _, creds = await _stored(form_id, action_id)
        assert creds == ["new-ciphertext"]

    async def test_an_unreadable_credential_is_only_deleted(
        self, service, workspace_form, sheets_action, fake_google  # noqa: F811
    ):
        form_id, action_id = workspace_form.form_id, str(sheets_action.id)
        await container.integration_action_service().add_credentials_to_form_action(
            form_id=form_id, action_id=action_id, credentials="not-a-ciphertext"
        )
        assert await self._replace(service, form_id, action_id) == "unreadable"
        assert fake_google.revoke_requests() == []

    async def test_an_unknown_form_is_refused(self, service, fake_google):  # noqa: F811
        from backend.app.exceptions import HTTPException

        with pytest.raises(HTTPException):
            await self._replace(service, "no-such-form", "a1")
        assert fake_google.revoke_requests() == []


class TestPinnedAddress:
    def test_the_revoke_url_is_googles(self):
        assert grants.REVOKE_URL == "https://oauth2.googleapis.com/revoke"

    async def test_neither_the_credential_nor_settings_move_it(
        self, monkeypatch, sheets_client, legacy_connected, fake_google, jobs  # noqa: F811
    ):
        monkeypatch.setattr(sheets_client, "TOKEN_URI", "https://elsewhere.example.test/t")
        service = container.sheets_grant_service()
        await service.store_new_grant(*legacy_connected, "new-ciphertext")
        hosts = {r.url.host for r in fake_google.requests}
        assert hosts == {"oauth2.googleapis.com"}
        assert [str(r.url) for r in fake_google.requests] == [grants.REVOKE_URL]
        assert TOKEN_URI not in [str(r.url) for r in fake_google.requests]

    def test_no_other_revoke_address_in_the_module(self):
        source = open(grants.__file__).read()
        assert source.count("oauth2.googleapis.com/revoke") == 2  # docstring + constant
        assert "settings.google_sheets.TOKEN_URI" not in source


class TestSealing:
    def test_the_token_travels_sealed(self):
        revocation = grants.GrantRevocation(form_id="f", action_id="a", token=LEGACY_REFRESH)
        sealed = grants.seal(container.crypto(), revocation)
        assert LEGACY_REFRESH not in sealed
        assert grants.unseal(container.crypto(), sealed) == revocation
