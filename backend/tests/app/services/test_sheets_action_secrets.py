"""Only the OAuth callback writes the Google Sheets action's credential, and
the credential travels to the Google Forms service in a request body, never
in a URL (URLs end up in access logs)."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest
from common.models.standard_form import ParameterValue
from common.services.http_client import HttpClient
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.enum.form_integration import FormIntegrationType
from tests.app.controllers.data import testUser

FORGED_TOKEN_URI = "http://10.0.0.1:6379/internal"
CONNECTED = "encrypted-connected-credential"
PROVIDER_URL = "http://google-forms.internal"


def _forged_credential():
    return json.dumps(
        {
            "token": "x",
            "refresh_token": "x",
            "token_uri": FORGED_TOKEN_URI,
            "client_id": "x",
            "client_secret": "x",
            "expiry": "2000-01-01T00:00:00Z",
        }
    )


async def _form(form_id):
    return await container.form_repo().get_form_document_by_id(form_id)


@pytest.fixture()
async def sheets_action():
    return await container.action_repository().create_global_action(
        ActionDto(
            name=FormIntegrationType.GOOGLE_SHEET.value,
            action_code="",
            type="External",
            parameters=[ParameterValue(name="Title", value="", required=True)],
        ),
        testUser,
    )


@pytest.fixture()
def google_service_requests(monkeypatch):
    """Every request the backend sends to the Google Forms service."""
    sent = []

    async def fake_send(self, request, *args, **kwargs):
        sent.append(request)
        return httpx.Response(200, json="sheet-id", request=request)

    monkeypatch.setattr(HttpClient, "send", fake_send)
    provider = container.integration_provider().google_integration_provider
    monkeypatch.setattr(
        provider.form_provider_service,
        "get_provider_url",
        AsyncMock(return_value=PROVIDER_URL),
    )
    return sent


def _actions_url(workspace, workspace_form):
    return f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/actions"


class TestCallerSuppliedSecrets:
    @pytest.mark.parametrize("name", ["Credentials", "Other"])
    async def test_adding_the_sheets_action_with_secrets_is_refused(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service_requests,
        name,
    ):
        for _ in range(2):  # adding, then adding again
            response = await client.post(
                _actions_url(workspace, workspace_form),
                cookies=test_user_cookies,
                json={
                    "action_id": str(sheets_action.id),
                    "parameters": [{"name": "Title", "value": "Sheet"}],
                    "secrets": [{"name": name, "value": _forged_credential()}],
                },
            )
            assert response.status_code == 422, response.text
            assert response.json()["code"] == "action_secrets_not_allowed"

        form = await _form(workspace_form.form_id)
        assert not form.secrets
        assert not form.parameters
        assert not (form.actions or {}).get("on_submit")
        assert google_service_requests == []
        workspace_copy = await container.action_repository().get_workspace_action(
            workspace.id, sheets_action.id
        )
        assert workspace_copy is None

    async def test_a_connected_credential_survives_a_refused_attempt(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service_requests,
    ):
        action_id = str(sheets_action.id)
        await container.integration_action_service().add_credentials_to_form_action(
            form_id=workspace_form.form_id, action_id=action_id, credentials=CONNECTED
        )
        before = (await _form(workspace_form.form_id)).secrets

        refused = await client.post(
            _actions_url(workspace, workspace_form),
            cookies=test_user_cookies,
            json={
                "action_id": action_id,
                "parameters": [{"name": "Title", "value": "Sheet"}],
                "secrets": [{"name": "Credentials", "value": _forged_credential()}],
            },
        )

        assert refused.status_code == 422
        assert (await _form(workspace_form.form_id)).secrets == before
        assert google_service_requests == []

    async def test_other_actions_still_take_secrets(
        self, client: AsyncClient, workspace, workspace_form, test_user_cookies
    ):
        other = await container.action_repository().create_global_action(
            ActionDto(name="send_webhook", action_code=""), testUser
        )
        response = await client.post(
            _actions_url(workspace, workspace_form),
            cookies=test_user_cookies,
            json={
                "action_id": str(other.id),
                "secrets": [{"name": "Signing key", "value": "k"}],
            },
        )
        assert response.status_code == 200, response.text
        assert (await _form(workspace_form.form_id)).secrets[str(other.id)]


class TestCredentialNotInUrl:
    async def test_create_sheet_sends_the_credential_in_the_body(
        self,
        client: AsyncClient,
        workspace,
        workspace_form,
        sheets_action,
        test_user_cookies,
        google_service_requests,
    ):
        action_id = str(sheets_action.id)
        await container.integration_action_service().add_credentials_to_form_action(
            form_id=workspace_form.form_id, action_id=action_id, credentials=CONNECTED
        )

        response = await client.post(
            _actions_url(workspace, workspace_form),
            cookies=test_user_cookies,
            json={
                "action_id": action_id,
                "parameters": [{"name": "Title", "value": "Sheet"}],
            },
        )

        assert response.status_code == 200, response.text
        assert len(google_service_requests) == 1
        request = google_service_requests[0]
        assert request.method == "POST"
        assert str(request.url).startswith(PROVIDER_URL)
        assert request.url.path.endswith("/forms/create_google_sheet")
        assert request.url.query == b""
        assert CONNECTED not in str(request.url)
        assert json.loads(request.content) == {
            "title": "Sheet",
            "credential": CONNECTED,
        }
        stored = (await _form(workspace_form.form_id)).parameters[action_id]
        assert {"name": "Google Sheet Id", "value": "sheet-id"} in [
            {"name": p.name, "value": p.value} for p in stored
        ]
