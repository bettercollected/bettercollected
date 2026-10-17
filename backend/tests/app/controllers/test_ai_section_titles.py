"""Section titles set by the AI: chat edit, review fixes, MCP ``update_form``
and form generation, end to end through the store (a fake provider, never a
real model)."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from common.models.standard_form import (
    StandardFieldProperty,
    StandardFormField,
    StandardFormFieldType,
)

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from tests.app.controllers.test_mcp_server import _call_tool, _make_key, _tool_text


@pytest.fixture()
async def fake_provider(monkeypatch, workspace):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


def _page(page_id: str, index: int, title: str) -> StandardFormField:
    return StandardFormField(
        id=page_id,
        index=index,
        type=StandardFormFieldType.SLIDE,
        properties=StandardFieldProperty(
            fields=[
                StandardFormField(
                    id=f"{page_id}-q",
                    index=0,
                    type=StandardFormFieldType.SHORT_TEXT,
                    title=title,
                    properties=StandardFieldProperty(fields=[]),
                )
            ]
        ),
    )


async def _two_pages(form_id: str) -> None:
    form_doc = await container.form_repo().get_form_document_by_id(form_id)
    form_doc.fields = [_page("page-1", 0, "Your name"), _page("page-2", 1, "When?")]
    await container.form_repo().save_form(form_doc)


async def _stored_titles(form_id: str):
    form_doc = await container.form_repo().get_form_document_by_id(form_id)
    return [
        page.properties.section_title if page.properties else None
        for page in form_doc.fields or []
    ]


class TestChatEdit:
    async def test_a_chat_turn_sets_and_clears_a_section_title(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        await _two_pages(workspace_form.form_id)
        url = f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat"
        fake_provider.replies = [
            json.dumps(
                {
                    "reply": "I named the second section.",
                    "ops": [
                        {
                            "op": "set_section_title",
                            "pageId": "page-2",
                            "title": "About your visit",
                        },
                        {"op": "set_section_title", "pageId": "welcome", "title": "Hi"},
                        {
                            "op": "set_section_title",
                            "pageIndex": 0,
                            "title": "x" * 121,
                        },
                    ],
                }
            )
        ]
        response = await client.post(
            url, cookies=test_user_cookies, json={"message": "name page 2"}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert [r["ok"] for r in body["results"]] == [True, False, False]
        assert body["results"][0]["message"] == (
            "Section title of page 2: 'About your visit'"
        )
        assert body["form"]["fields"][1]["properties"]["sectionTitle"] == (
            "About your visit"
        )
        assert await _stored_titles(workspace_form.form_id) == [None, "About your visit"]
        # the model saw how to use the op
        assert "set_section_title" in fake_provider.calls[0]["system"]

        # the next turn sees the title in the snapshot, and clears it
        fake_provider.replies = [
            json.dumps(
                {
                    "reply": "Cleared.",
                    "ops": [
                        {"op": "set_section_title", "pageId": "page-2", "title": None}
                    ],
                }
            )
        ]
        response = await client.post(
            url,
            cookies=test_user_cookies,
            json={"message": "remove it", "sessionId": body["sessionId"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["ok"] is True
        assert '"sectionTitle": "About your visit"' in fake_provider.calls[1]["system"]
        assert await _stored_titles(workspace_form.form_id) == [None, None]

    async def test_a_review_fix_can_set_a_section_title(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        await _two_pages(workspace_form.form_id)
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}"
            "/ai/review/apply",
            cookies=test_user_cookies,
            json={
                "ops": [
                    {"op": "set_section_title", "pageIndex": 0, "title": "About you"}
                ]
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["results"][0]["ok"] is True
        assert await _stored_titles(workspace_form.form_id) == ["About you", None]

    async def test_someone_outside_the_workspace_cannot(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies_1: dict[str, str],
        fake_provider: FakeProvider,
    ):
        await _two_pages(workspace_form.form_id)
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}"
            "/ai/review/apply",
            cookies=test_user_cookies_1,
            json={
                "ops": [
                    {"op": "set_section_title", "pageIndex": 0, "title": "About you"}
                ]
            },
        )
        assert response.status_code == 403
        assert await _stored_titles(workspace_form.form_id) == [None, None]


class TestMCP:
    async def test_update_form_sets_a_section_title(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        await _two_pages(workspace_form.form_id)
        token = await _make_key(workspace.id, ["forms:read", "forms:write"])
        result = _tool_text(
            await _call_tool(
                client,
                token,
                "update_form",
                {
                    "form_id": workspace_form.form_id,
                    "ops": [
                        {
                            "op": "set_section_title",
                            "pageId": "page-1",
                            "title": "Your contact details",
                        },
                        {"op": "set_section_title", "pageId": "ending", "title": "Bye"},
                    ],
                },
            )
        )
        assert [r["ok"] for r in result["results"]] == [True, False]
        assert await _stored_titles(workspace_form.form_id) == [
            "Your contact details",
            None,
        ]
        form = _tool_text(
            await _call_tool(
                client, token, "get_form", {"form_id": workspace_form.form_id}
            )
        )
        assert form["fields"][0]["properties"]["sectionTitle"] == "Your contact details"
        logs = await container.mcp_audit_log_repo().list_by_workspace(workspace.id)
        assert any(log.tool == "update_form" and not log.ok for log in logs)

    async def test_a_read_only_key_cannot(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        await _two_pages(workspace_form.form_id)
        token = await _make_key(workspace.id, ["forms:read"])
        result = await _call_tool(
            client,
            token,
            "update_form",
            {
                "form_id": workspace_form.form_id,
                "ops": [{"op": "set_section_title", "pageIndex": 0, "title": "X"}],
            },
        )
        assert result.get("isError") is True
        assert "forms:write" in result["content"][0]["text"]
        assert await _stored_titles(workspace_form.form_id) == [None, None]


GENERATED = {
    "title": "Community centre visit",
    "description": "Tell us about your visit.",
    "fields": [
        {
            "title": "About you",
            "type": "group",
            "layout": "SINGLE_COLUMN_NO_BACKGROUND",
            "sectionTitle": "About you",
            "properties": {
                "fields": [
                    {"title": "Your name", "type": "short_text"},
                    {"title": "Your age group", "type": "dropdown",
                     "properties": {"choices": ["Under 18", "18 or older"]}},
                ]
            },
        },
        {
            "title": "Your visit",
            "type": "group",
            "layout": "SINGLE_COLUMN_NO_BACKGROUND",
            "sectionTitle": "x" * 121,
            "properties": {
                "fields": [
                    {"title": "When did you come?", "type": "date"},
                    {"title": "What did you do?", "type": "long_text"},
                ]
            },
        },
        {
            "title": "Anything else?",
            "type": "long_text",
            "layout": "SINGLE_COLUMN_NO_BACKGROUND",
        },
    ],
}


class TestGeneration:
    async def test_a_generated_form_keeps_its_section_titles(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        fake_provider.replies = [GENERATED]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/ai",
            cookies=test_user_cookies,
            json={"prompt": "a form about a visit to the community centre"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        form_id = body.get("formId") or body["form_id"]
        # set where given, left out where too long or not given
        assert await _stored_titles(form_id) == ["About you", None, None]

    async def test_mcp_create_form_with_ai_keeps_them_too(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        fake_provider: FakeProvider,
    ):
        fake_provider.replies = [GENERATED]
        token = await _make_key(workspace.id, ["forms:write"])
        created = _tool_text(
            await _call_tool(
                client, token, "create_form_with_ai", {"prompt": "a visit form"}
            )
        )
        assert await _stored_titles(created["formId"]) == ["About you", None, None]
