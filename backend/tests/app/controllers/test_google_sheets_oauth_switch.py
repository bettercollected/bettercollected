"""The Google Sheets action's endpoints follow GOOGLE_SHEETS_OAUTH: by default
the Google Forms service runs the flow as before; with ``backend`` the backend
runs it with the sign-in client and never calls that service. Google itself
is faked (tests/app/sheets_helpers.py)."""

import json
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
from backend.app.services.google_sheets_oauth import DRIVE_FILE_SCOPE
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.sheets_helpers import (
    AUTH_URI,
    CLIENT_ID,
    SPREADSHEET_ID,
    backend_sheets_oauth,  # noqa: F401 (fixture)
    credential_dict,
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


def _state_for(user) -> str:
    return container.crypto().encrypt(
        json.dumps({"client_referer_uri": None, "user_id": user.id})
    )


async def _connect(client, cookies, form_id, action_id, user=testUser):
    return await client.post(
        f"{OAUTH_URL}/callback",
        cookies=cookies,
        json={
            "state": _state_for(user),
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
