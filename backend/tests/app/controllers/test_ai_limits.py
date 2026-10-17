"""Rate limits and the daily budget of the AI endpoints (backend/AGENTS.md
"AI limits"): per user and per workspace, 429 with a plain message, checked
after the membership and AI opt-in checks and before any provider call.
Fake providers only."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.ai.usage import record_tokens
from backend.config import settings
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.controllers.data import testUser
from tests.app.controllers.test_ai_consent import GENERATED_FORM, _ai_endpoints
from tests.app.controllers.test_form_ai_review import _make_v2
from tests.app.controllers.test_mcp_server import _call_tool, _make_key
from tests.app.pdf_import import documents


class TokenReportingProvider(FakeProvider):
    """Reports ``tokens`` for each call, as a real provider's usage would."""

    tokens = 150

    async def generate_form(self, prompt: str) -> dict:
        await record_tokens(self.tokens)
        return await super().generate_form(prompt)

    async def chat(self, system: str, messages: list, **options) -> str:
        await record_tokens(self.tokens)
        return await super().chat(system, messages, **options)


@pytest.fixture()
def fake(monkeypatch):
    fake = TokenReportingProvider()
    use_fake_provider(monkeypatch, fake)
    return fake


@pytest.fixture()
def limits(monkeypatch):
    def set_(**values):
        for key, value in values.items():
            monkeypatch.setattr(settings.ai, key, value)

    return set_


def _generate_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/forms/ai"


async def _generate(client, workspace, cookies, fake):
    fake.replies.append(GENERATED_FORM)
    return await client.post(
        _generate_url(workspace), cookies=cookies, json={"prompt": "a contact form"}
    )


def _is_429(response, code: str) -> bool:
    return (
        response.status_code == 429
        and response.json().get("code") == code
        and int(response.headers["Retry-After"]) >= 1
        and response.json().get("message")
    )


class TestRateLimits:
    async def test_per_user_limit(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
        limits,
    ):
        limits(RATE_LIMIT_PER_USER=2, RATE_LIMIT_PER_WORKSPACE=0)
        await enable_ai(workspace)
        for _ in range(2):
            response = await _generate(client, workspace, test_user_cookies, fake)
            assert response.status_code == 200, response.text
        response = await _generate(client, workspace, test_user_cookies, fake)
        assert _is_429(response, "ai_rate_limited"), response.text
        assert len(fake.calls) == 2

    async def test_per_workspace_limit(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
        limits,
    ):
        limits(RATE_LIMIT_PER_USER=0, RATE_LIMIT_PER_WORKSPACE=1)
        await enable_ai(workspace)
        assert (
            await _generate(client, workspace, test_user_cookies, fake)
        ).status_code == 200
        response = await _generate(client, workspace, test_user_cookies, fake)
        assert _is_429(response, "ai_rate_limited"), response.text
        assert len(fake.calls) == 1

    async def test_the_opt_in_is_checked_first_and_costs_nothing(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
        limits,
    ):
        limits(RATE_LIMIT_PER_USER=1)
        response = await _generate(client, workspace, test_user_cookies, fake)
        assert response.status_code == 403
        assert await container.ai_usage_guard().usage_today(workspace.id) == (0, 0)
        await enable_ai(workspace)
        response = await _generate(client, workspace, test_user_cookies, fake)
        assert response.status_code == 200, response.text

    @pytest.mark.parametrize("endpoint", range(5))
    async def test_every_ai_endpoint_is_limited_before_the_provider(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
        limits,
        endpoint: int,
    ):
        limits(RATE_LIMIT_PER_USER=1)
        await enable_ai(workspace)
        # the user's one request of this window is already spent
        await container.ai_usage_guard().admit(workspace.id, testUser.id)
        url, body = _ai_endpoints(workspace, workspace_form.form_id)[endpoint]
        response = await client.post(url, cookies=test_user_cookies, json=body)
        assert _is_429(response, "ai_rate_limited"), (url, response.text)
        assert fake.calls == []

    async def test_mcp_create_form_with_ai_is_limited(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        fake: FakeProvider,
        limits,
    ):
        limits(RATE_LIMIT_PER_WORKSPACE=1)
        await enable_ai(workspace)
        token = await _make_key(workspace.id, ["forms:write"])
        await container.ai_usage_guard().admit(workspace.id, None)
        result = await _call_tool(
            client, token, "create_form_with_ai", {"prompt": "a contact form"}
        )
        assert result.get("isError"), result
        assert "Too many AI requests" in result["content"][0]["text"]
        assert fake.calls == []

    async def test_mcp_prompt_length_is_bounded(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        fake: FakeProvider,
    ):
        await enable_ai(workspace)
        token = await _make_key(workspace.id, ["forms:write"])
        result = await _call_tool(
            client, token, "create_form_with_ai", {"prompt": "x" * 9000}
        )
        assert result.get("isError"), result
        assert fake.calls == []

    async def test_document_import_with_ai_is_limited_at_upload(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        limits,
    ):
        limits(RATE_LIMIT_PER_USER=1)
        await enable_ai(workspace)
        await container.ai_usage_guard().admit(workspace.id, testUser.id)
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/form-imports",
            cookies=test_user_cookies,
            files={"file": ("form.pdf", documents.form_pdf(), "application/pdf")},
            data={"ai_consent": "true"},
        )
        assert _is_429(response, "ai_rate_limited"), response.text
        # nothing was created for the refused upload
        assert await container.form_import_repo().list_by_workspace(workspace.id) == []

    async def test_applying_review_fixes_has_its_own_allowance(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        limits,
    ):
        limits(RATE_LIMIT_FIX_PER_USER=1)
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        await _make_v2(form_doc)
        url = (
            f"/api/v1/workspaces/{workspace.id}/forms/"
            f"{workspace_form.form_id}/ai/review/apply"
        )
        body = {"ops": [{"op": "update_form_info", "title": "Renamed"}]}
        response = await client.post(url, cookies=test_user_cookies, json=body)
        assert response.status_code == 200, response.text
        response = await client.post(url, cookies=test_user_cookies, json=body)
        assert _is_429(response, "ai_rate_limited"), response.text


class TestDailyBudget:
    async def test_requests_and_tokens_are_counted_without_a_cap(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
    ):
        assert settings.ai.DAILY_REQUEST_BUDGET == 0
        assert settings.ai.DAILY_TOKEN_BUDGET == 0
        await enable_ai(workspace)
        for _ in range(3):
            response = await _generate(client, workspace, test_user_cookies, fake)
            assert response.status_code == 200, response.text
        assert await container.ai_usage_guard().usage_today(workspace.id) == (3, 450)

    async def test_request_budget(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
        limits,
    ):
        limits(DAILY_REQUEST_BUDGET=2)
        await enable_ai(workspace)
        for _ in range(2):
            response = await _generate(client, workspace, test_user_cookies, fake)
            assert response.status_code == 200, response.text
        response = await _generate(client, workspace, test_user_cookies, fake)
        assert _is_429(response, "ai_daily_limit"), response.text
        assert "midnight UTC" in response.json()["message"]
        assert len(fake.calls) == 2

    async def test_token_budget(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        fake: FakeProvider,
        limits,
    ):
        limits(DAILY_TOKEN_BUDGET=200)
        await enable_ai(workspace)
        # 150 then 300 tokens: the second request was admitted under the
        # budget, the third is refused
        for _ in range(2):
            response = await _generate(client, workspace, test_user_cookies, fake)
            assert response.status_code == 200, response.text
        response = await _generate(client, workspace, test_user_cookies, fake)
        assert _is_429(response, "ai_daily_limit"), response.text
        assert len(fake.calls) == 2

    async def test_budgets_are_per_workspace(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        limits,
    ):
        limits(
            DAILY_REQUEST_BUDGET=1, RATE_LIMIT_PER_USER=0, RATE_LIMIT_PER_WORKSPACE=0
        )
        guard = container.ai_usage_guard()
        await guard.admit(workspace.id, None)
        await guard.admit("another-workspace", None)
        with pytest.raises(Exception) as raised:
            await guard.admit(workspace.id, None)
        assert getattr(raised.value, "code", None) == "ai_daily_limit"


def test_429_bodies_are_plain_json():
    from backend.app.services.ai.errors import ai_daily_limit, ai_rate_limited

    for error in (ai_rate_limited(30), ai_daily_limit(600)):
        assert error.status_code == 429
        assert set(error.content) == {"code", "message"}
        json.dumps(error.content)
