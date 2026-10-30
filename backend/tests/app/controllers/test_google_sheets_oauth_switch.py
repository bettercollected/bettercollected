"""The Google Sheets action's endpoints follow GOOGLE_SHEETS_OAUTH: by default
the Google Forms service runs the flow as before; with ``backend`` the backend
runs it with the sign-in client and never calls that service. Google itself
is faked (tests/app/sheets_helpers.py)."""

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.form_integration import (
    FormActionType,
    FormIntegrationType,
)
from backend.app.services.google_sheets_oauth import (
    DRIVE_FILE_SCOPE,
    STATE_MAX_AGE_SECONDS,
)
from backend.app.services.session_service import user_from_access_token
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser, testUser1
from tests.app.sheets_helpers import (
    AUTH_URI,
    CLIENT_ID,
    SPREADSHEET_ID,
    backend_sheets_oauth,  # noqa: F401 (fixture)
    credential_dict,
    oauth_state,
    session_oauth_state,
    fake_google,  # noqa: F401 (fixture)
    sheets_client,  # noqa: F401 (fixture)
)

OAUTH_URL = f"/api/v1/integration/{FormIntegrationType.GOOGLE_SHEET.value}/oauth"


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
def google_service():
    """The Google Forms service's side of the old flow, stubbed in both
    provider instances (OAuth endpoints and action saving)."""
    http_client = MagicMock()
    http_client.get = AsyncMock(return_value={"oauth_url": "https://google-service/oauth"})
    http_client.post = AsyncMock(return_value="service-result")
    form_provider_service = MagicMock()
    form_provider_service.get_provider_url = AsyncMock(return_value="http://google")
    providers = [
        container.integration_service().integration__provider_factory.google_integration_provider,
        container.integration_provider().google_integration_provider,
    ]
    patches = [
        patch.object(provider, name, value)
        for provider in providers
        for name, value in (
            ("http_client", http_client),
            ("form_provider_service", form_provider_service),
        )
    ]
    for p in patches:
        p.start()
    yield http_client
    for p in patches:
        p.stop()


async def _connect(client, cookies, form_id, action_id, user=None):
    return await client.post(
        f"{OAUTH_URL}/callback",
        cookies=cookies,
        json={
            "state": session_oauth_state(cookies) if user is None else oauth_state(user),
            "code": "the-code",
            "form_id": form_id,
            "action_id": action_id,
        },
    )


async def _form(form_id):
    return await container.form_repo().get_form_document_by_id(form_id)


async def _save_action(client, cookies, workspace, form_id, action_id, title="Sheet"):
    return await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form_id}/actions",
        cookies=cookies,
        json={
            "action_id": action_id,
            "parameters": [{"name": "Title", "value": title}],
        },
    )


class TestDefaultGoogleService:
    async def test_the_switch_defaults_to_the_google_service(self):
        assert settings.google_sheets.SHEETS_OAUTH == "google_service"

    async def test_the_flow_still_goes_through_the_google_service(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service,
        sheets_client,  # noqa: F811
        fake_google,  # noqa: F811
    ):
        url = await client.get(OAUTH_URL, cookies=test_user_cookies)
        assert url.json() == "https://google-service/oauth"

        connected = await _connect(
            client, test_user_cookies, workspace_form.form_id, str(sheets_action.id)
        )
        assert connected.status_code == 200, connected.text
        secrets = (await _form(workspace_form.form_id)).secrets
        assert secrets[str(sheets_action.id)][0].value == "service-result"

        saved = await _save_action(
            client, test_user_cookies, workspace, workspace_form.form_id, str(sheets_action.id)
        )
        assert saved.status_code == 200, saved.text
        assert google_service.post.call_args.args[0].endswith("/forms/create_google_sheet")
        # the credential travels in the body, never in the query string
        assert "params" not in google_service.post.call_args.kwargs
        assert google_service.post.call_args.kwargs["json"]["credential"] == "service-result"
        assert fake_google.requests == []


class TestBackendFlow:
    async def test_the_authorization_url_is_the_backends(
        self,
        client: AsyncClient,
        test_user_cookies,
        google_service,
        backend_sheets_oauth,  # noqa: F811
    ):
        response = await client.get(OAUTH_URL, cookies=test_user_cookies)

        assert response.status_code == 200, response.text
        url = urlparse(response.json())
        params = {k: v[0] for k, v in parse_qs(url.query).items()}
        assert f"{url.scheme}://{url.netloc}{url.path}" == AUTH_URI
        assert params["client_id"] == CLIENT_ID
        assert params["scope"] == DRIVE_FILE_SCOPE
        state = json.loads(container.crypto().decrypt(params["state"]))
        assert state["user_id"] == testUser.id
        google_service.get.assert_not_called()
        assert backend_sheets_oauth.requests == []

    async def test_connect_and_save_create_the_sheet_without_the_google_service(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service,
        backend_sheets_oauth,  # noqa: F811
    ):
        connected = await _connect(
            client, test_user_cookies, workspace_form.form_id, str(sheets_action.id)
        )
        assert connected.status_code == 200, connected.text
        [stored] = (await _form(workspace_form.form_id)).secrets[str(sheets_action.id)]
        assert stored.name == "Credentials"
        assert credential_dict(stored.value)["scopes"] == DRIVE_FILE_SCOPE

        saved = await _save_action(
            client,
            test_user_cookies,
            workspace,
            workspace_form.form_id,
            str(sheets_action.id),
            title="Feedback",
        )
        assert saved.status_code == 200, saved.text
        parameters = (await _form(workspace_form.form_id)).parameters[
            str(sheets_action.id)
        ]
        assert {p.name: p.value for p in parameters} == {
            "Title": "Feedback",
            "Google Sheet Id": SPREADSHEET_ID,
        }
        [created] = backend_sheets_oauth.sheets_requests()
        assert json.loads(created.content) == {"properties": {"title": "Feedback"}}
        google_service.get.assert_not_called()
        google_service.post.assert_not_called()

    async def test_a_state_of_another_user_is_refused_before_the_exchange(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        backend_sheets_oauth,  # noqa: F811
    ):
        response = await _connect(
            client,
            test_user_cookies,
            workspace_form.form_id,
            str(sheets_action.id),
            user=testUser1,
        )

        assert response.status_code == 403
        assert backend_sheets_oauth.requests == []
        assert not (await _form(workspace_form.form_id)).secrets

    async def test_a_refused_exchange_stores_nothing(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        backend_sheets_oauth,  # noqa: F811
    ):
        backend_sheets_oauth.token_status = 400
        backend_sheets_oauth.token_body = {"error": "invalid_grant"}

        response = await _connect(
            client, test_user_cookies, workspace_form.form_id, str(sheets_action.id)
        )

        assert response.status_code == 417
        assert not (await _form(workspace_form.form_id)).secrets

    async def test_unconfigured_sign_in_client_answers_503(
        self,
        client: AsyncClient,
        test_user_cookies,
        backend_sheets_oauth,  # noqa: F811
        monkeypatch,
    ):
        monkeypatch.setattr(settings.google_sheets, "CLIENT_SECRET", "")
        response = await client.get(OAUTH_URL, cookies=test_user_cookies)
        assert response.status_code == 503


class TestCallerSuppliedSecrets:
    """Only the OAuth callback writes the Sheets action's credential."""

    @pytest.mark.parametrize("name", ["Credentials", "Other"])
    async def test_adding_the_sheets_action_with_secrets_is_refused(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        backend_sheets_oauth,  # noqa: F811
        name,
    ):
        forged = container.crypto().encrypt(
            json.dumps(
                {
                    "token": "x",
                    "refresh_token": "x",
                    "token_uri": "http://10.0.0.1:6379/internal",
                    "expiry": "2000-01-01T00:00:00.000000Z",
                }
            )
        )
        for attempt in range(2):  # adding, then adding again (the update path)
            response = await client.post(
                f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/actions",
                cookies=test_user_cookies,
                json={
                    "action_id": str(sheets_action.id),
                    "parameters": [{"name": "Title", "value": "Sheet"}],
                    "secrets": [{"name": name, "value": forged}],
                },
            )
            assert response.status_code == 422, response.text
            assert response.json()["code"] == "action_secrets_not_allowed"

        form = await _form(workspace_form.form_id)
        assert not form.secrets
        assert not (form.actions or {}).get("on_submit")
        assert backend_sheets_oauth.requests == []

    async def test_a_connected_credential_survives_a_refused_attempt(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        backend_sheets_oauth,  # noqa: F811
    ):
        connected = await _connect(
            client, test_user_cookies, workspace_form.form_id, str(sheets_action.id)
        )
        assert connected.status_code == 200, connected.text
        before = (await _form(workspace_form.form_id)).secrets

        refused = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/actions",
            cookies=test_user_cookies,
            json={
                "action_id": str(sheets_action.id),
                "secrets": [{"name": "Credentials", "value": "forged"}],
            },
        )

        assert refused.status_code == 422
        assert (await _form(workspace_form.form_id)).secrets == before

    async def test_other_actions_still_take_secrets(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies
    ):
        other = await container.action_repository().create_global_action(
            ActionDto(name="send_webhook", action_code=""), testUser
        )
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/actions",
            cookies=test_user_cookies,
            json={
                "action_id": str(other.id),
                "secrets": [{"name": "Signing key", "value": "k"}],
            },
        )
        assert response.status_code == 200, response.text


@pytest.fixture(params=["google_service", "backend"])
def mode(request, monkeypatch, sheets_client, google_service, fake_google):  # noqa: F811
    """Both ways the flow runs; the state is checked the same in each."""
    monkeypatch.setattr(sheets_client, "SHEETS_OAUTH", request.param)
    return request.param


async def _started_state(client, cookies, mode, google_service) -> str:
    """The state ``GET .../oauth`` handed to this session."""
    response = await client.get(OAUTH_URL, cookies=cookies)
    assert response.status_code == 200, response.text
    if mode == "backend":
        return parse_qs(urlparse(response.json()).query)["state"][0]
    return google_service.get.call_args.kwargs["params"]["state"]


async def _callback(client, cookies, state, form_id, action_id):
    return await client.post(
        f"{OAUTH_URL}/callback",
        cookies=cookies,
        json={
            "state": state,
            "code": "the-code",
            "form_id": form_id,
            "action_id": action_id,
        },
    )


def _exchanges(mode, google_service, fake_google) -> int:
    """How many codes went on to be exchanged."""
    if mode == "backend":
        return len(fake_google.token_requests())
    return google_service.post.await_count


class TestStateBinding:
    """The state is bound to the session that started the connection, expires,
    and is accepted once."""

    async def test_the_started_connection_completes(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service,
        fake_google,  # noqa: F811
        mode,
    ):
        state = await _started_state(client, test_user_cookies, mode, google_service)

        response = await _callback(
            client, test_user_cookies, state, workspace_form.form_id, str(sheets_action.id)
        )

        assert response.status_code == 200, response.text
        assert _exchanges(mode, google_service, fake_google) == 1
        assert (await _form(workspace_form.form_id)).secrets[str(sheets_action.id)]

    async def test_a_state_started_in_another_session_is_refused(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service,
        fake_google,  # noqa: F811
        mode,
    ):
        # a state handed out to another session, completed in this one
        other_session = access_token(testUser)
        state = await _started_state(
            client,
            {"Authorization": other_session, "RefreshToken": other_session},
            mode,
            google_service,
        )

        response = await _callback(
            client, test_user_cookies, state, workspace_form.form_id, str(sheets_action.id)
        )

        assert response.status_code == 403
        assert _exchanges(mode, google_service, fake_google) == 0
        assert not (await _form(workspace_form.form_id)).secrets

    async def test_another_users_state_with_this_sessions_code_is_refused(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        test_user_cookies_1,
        google_service,
        fake_google,  # noqa: F811
        mode,
    ):
        state = await _started_state(client, test_user_cookies_1, mode, google_service)

        response = await _callback(
            client, test_user_cookies, state, workspace_form.form_id, str(sheets_action.id)
        )

        assert response.status_code == 403
        assert _exchanges(mode, google_service, fake_google) == 0
        assert not (await _form(workspace_form.form_id)).secrets

    async def test_a_state_is_accepted_once(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service,
        fake_google,  # noqa: F811
        mode,
    ):
        state = await _started_state(client, test_user_cookies, mode, google_service)
        first = await _callback(
            client, test_user_cookies, state, workspace_form.form_id, str(sheets_action.id)
        )
        assert first.status_code == 200, first.text
        stored = (await _form(workspace_form.form_id)).secrets

        again = await _callback(
            client, test_user_cookies, state, workspace_form.form_id, str(sheets_action.id)
        )

        assert again.status_code == 400
        assert _exchanges(mode, google_service, fake_google) == 1
        assert (await _form(workspace_form.form_id)).secrets == stored

    async def test_an_expired_state_is_refused(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service,
        fake_google,  # noqa: F811
        mode,
    ):
        state = await _started_state(client, test_user_cookies, mode, google_service)
        content = container.crypto().decrypt(state).encode()
        expired = (
            container.crypto()
            .encrypt_at_time(content, int(time.time()) - STATE_MAX_AGE_SECONDS - 60)
            .decode()
        )

        response = await _callback(
            client, test_user_cookies, expired, workspace_form.form_id, str(sheets_action.id)
        )

        assert response.status_code == 400
        assert _exchanges(mode, google_service, fake_google) == 0
        assert not (await _form(workspace_form.form_id)).secrets

    async def test_a_state_without_a_nonce_is_refused(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service,
        fake_google,  # noqa: F811
        mode,
    ):
        # the shape handed out before states were bound to a session
        user = user_from_access_token(test_user_cookies["Authorization"])
        state = container.crypto().encrypt(
            json.dumps({"client_referer_uri": None, "user_id": user.id})
        )

        response = await _callback(
            client, test_user_cookies, state, workspace_form.form_id, str(sheets_action.id)
        )

        assert response.status_code == 400
        assert _exchanges(mode, google_service, fake_google) == 0
