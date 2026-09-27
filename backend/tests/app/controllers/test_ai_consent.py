"""Workspace AI consent (#715, #717): no AI provider call without the
workspace admin's opt-in, and never for someone outside the workspace.

Every test uses a fake provider that counts calls; the opt-in check itself
is real (only the raw provider lookup is replaced).
"""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.config import settings
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.controllers.data import testUser
from tests.app.controllers.test_form_ai_insights import _seed_form_and_responses
from tests.app.controllers.test_mcp_server import _call_tool, _make_key, _tool_text

GENERATED_FORM = {"title": "Generated", "description": "", "fields": []}


@pytest.fixture()
def fake(monkeypatch):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    return fake


@pytest.fixture()
def openai_configured(monkeypatch):
    monkeypatch.setattr(settings.open_ai, "API_KEY", "sk-test")
    monkeypatch.setattr(settings.ai, "DEFAULT_PROVIDER", "openai")


def _settings_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/ai-settings"


def _ai_endpoints(workspace, form_id):
    base = f"/api/v1/workspaces/{workspace.id}/forms"
    return [
        (f"{base}/{form_id}/ai/chat", {"message": "add an email question"}),
        (f"{base}/{form_id}/ai/review", {}),
        (f"{base}/{form_id}/ai/insights", {}),
        (f"{base}/ai", {"prompt": "a contact form"}),
    ]


def _is_ai_not_enabled(response) -> bool:
    return (
        response.status_code == 403 and response.json().get("code") == "ai_not_enabled"
    )


class TestWorkspaceAISetting:
    async def test_off_by_default_including_existing_workspaces(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        response = await client.get(_settings_url(workspace), cookies=test_user_cookies)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["enabled"] is False and body["provider"] is None
        assert body["canManage"] is True and body["learnPreferences"] is False

        # A workspace stored before the setting existed has no value at all.
        await container.workspace_repo().set_fields(workspace, {"ai_enabled": None})
        response = await client.get(_settings_url(workspace), cookies=test_user_cookies)
        assert response.json()["enabled"] is False

    async def test_only_admins_change_it_and_it_is_recorded(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        test_invited_user_cookies: dict[str, str],
        test_user_cookies_1: dict[str, str],
        openai_configured,
    ):
        # a collaborator sees the setting but cannot change it
        seen = await client.get(
            _settings_url(workspace), cookies=test_invited_user_cookies
        )
        assert seen.status_code == 200 and seen.json()["canManage"] is False
        for cookies in (test_invited_user_cookies, test_user_cookies_1):
            refused = await client.put(
                _settings_url(workspace), cookies=cookies, json={"enabled": True}
            )
            assert refused.status_code == 403
        outsider = await client.get(
            _settings_url(workspace), cookies=test_user_cookies_1
        )
        assert outsider.status_code == 403

        enabled = await client.put(
            _settings_url(workspace), cookies=test_user_cookies, json={"enabled": True}
        )
        assert enabled.status_code == 200, enabled.text
        body = enabled.json()
        assert body["enabled"] is True
        assert body["provider"] == "openai" and body["providerName"] == "OpenAI"
        assert body["enabledBy"] == testUser.id and body["enabledAt"]

        stored = await container.workspace_repo().find_by_id(workspace.id)
        assert stored.ai_enabled is True and stored.ai_provider == "openai"
        assert stored.ai_enabled_by == testUser.id and stored.ai_enabled_at

        disabled = await client.put(
            _settings_url(workspace), cookies=test_user_cookies, json={"enabled": False}
        )
        assert disabled.json()["enabled"] is False
        stored = await container.workspace_repo().find_by_id(workspace.id)
        assert stored.ai_enabled is False and stored.ai_provider is None
        assert stored.ai_disabled_by == testUser.id

    async def test_unconfigured_or_unknown_provider_is_refused(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        monkeypatch,
    ):
        monkeypatch.setattr(settings.google_ai, "API_KEY", "")
        for provider in ("google", "somebody-else"):
            response = await client.put(
                _settings_url(workspace),
                cookies=test_user_cookies,
                json={"enabled": True, "provider": provider},
            )
            assert response.status_code == 400, response.text
        stored = await container.workspace_repo().find_by_id(workspace.id)
        assert not stored.ai_enabled


class TestEnforcement:
    async def test_every_ai_endpoint_is_refused_while_off(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
    ):
        await _seed_form_and_responses(workspace.id, workspace_form.form_id)
        for url, body in _ai_endpoints(workspace, workspace_form.form_id):
            response = await client.post(url, cookies=test_user_cookies, json=body)
            assert _is_ai_not_enabled(response), (url, response.text)
        assert fake.calls == []

    async def test_calls_go_through_once_enabled(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
    ):
        await _seed_form_and_responses(workspace.id, workspace_form.form_id)
        await enable_ai(workspace)
        fake.replies = [
            json.dumps({"reply": "Done.", "ops": []}),
            json.dumps({"summary": "Looks fine.", "findings": []}),
            json.dumps({"summary": "People like it.", "themes": [], "actionable": []}),
            GENERATED_FORM,
        ]
        for url, body in _ai_endpoints(workspace, workspace_form.form_id):
            response = await client.post(url, cookies=test_user_cookies, json=body)
            assert response.status_code == 200, (url, response.text)
        assert len(fake.calls) == 4

    async def test_turning_it_off_again_stops_the_calls(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
        openai_configured,
    ):
        await enable_ai(workspace)
        await client.put(
            _settings_url(workspace), cookies=test_user_cookies, json={"enabled": False}
        )
        url, body = _ai_endpoints(workspace, workspace_form.form_id)[0]
        response = await client.post(url, cookies=test_user_cookies, json=body)
        assert _is_ai_not_enabled(response)
        assert fake.calls == []

    async def test_a_client_chosen_provider_must_be_the_consented_one(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        monkeypatch,
    ):
        fake = FakeProvider()
        asked_for = []

        def lookup(provider=None):
            asked_for.append(str(getattr(provider, "value", provider)))
            return fake

        monkeypatch.setattr(container.openai_service(), "_get_provider", lookup)
        await enable_ai(workspace, provider="openai")
        fake.replies = [json.dumps({"reply": "Done.", "ops": []})]
        url, _ = _ai_endpoints(workspace, workspace_form.form_id)[0]
        response = await client.post(
            url,
            cookies=test_user_cookies,
            json={"message": "hello", "provider": "google"},
        )
        assert response.status_code == 200, response.text
        assert asked_for == ["openai"]

    async def test_mcp_create_form_with_ai_needs_the_opt_in(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        fake: FakeProvider,
    ):
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(
            client, token, "create_form_with_ai", {"prompt": "a contact form"}
        )
        assert result.get("isError"), result
        assert "AI features are off" in result["content"][0]["text"]
        assert fake.calls == []

        await enable_ai(workspace)
        fake.replies = [GENERATED_FORM]
        created = _tool_text(
            await _call_tool(
                client, token, "create_form_with_ai", {"prompt": "a contact form"}
            )
        )
        assert created["formId"] and len(fake.calls) == 1


class TestMembershipFirst:
    async def test_non_member_gets_403_and_no_provider_call(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies_1: dict[str, str],
        fake: FakeProvider,
        monkeypatch,
    ):
        """#717: even with AI on for the target workspace, an outsider is
        refused before the provider is called or the AI profile is loaded."""
        from backend.app.services.ai.profile import AIProfileService

        await enable_ai(workspace)
        profile_loads = []

        async def load_profile(*args, **kwargs):
            profile_loads.append(args)
            return None

        monkeypatch.setattr(AIProfileService, "get_profile_for_prompt", load_profile)
        fake.replies = [GENERATED_FORM]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/ai",
            cookies=test_user_cookies_1,
            json={"prompt": "a contact form"},
        )
        assert response.status_code == 403
        assert fake.calls == [] and profile_loads == []


class TestAPIKeyAcknowledgement:
    async def test_responses_read_needs_an_acknowledgement(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        url = f"/api/v1/workspaces/{workspace.id}/api-keys"
        refused = await client.post(
            url,
            cookies=test_user_cookies,
            json={"name": "agent", "scopes": ["forms:read", "responses:read"]},
        )
        assert refused.status_code == 400
        assert "unredacted" in refused.text

        created = await client.post(
            url,
            cookies=test_user_cookies,
            json={
                "name": "agent",
                "scopes": ["forms:read", "responses:read"],
                "acknowledgeUnredactedResponses": True,
            },
        )
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["responsesReadAcknowledgedBy"] == testUser.id
        assert body["responsesReadAcknowledgedAt"]

        plain = await client.post(
            url,
            cookies=test_user_cookies,
            json={"name": "reader", "scopes": ["forms:read"]},
        )
        assert plain.status_code == 200
        assert plain.json()["responsesReadAcknowledgedAt"] is None
