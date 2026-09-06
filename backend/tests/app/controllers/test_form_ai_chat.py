"""Chat-based form editing — endpoint tests with a FAKE provider (no model calls)."""

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
from backend.app.schemas.form_ai_session import FormAISessionDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument


class FakeProvider:
    """Scripted provider: returns queued replies, records what it was asked."""

    def __init__(self):
        self.replies = []
        self.calls = []

    async def chat(self, system: str, messages: list) -> str:
        self.calls.append({"system": system, "messages": messages})
        return self.replies.pop(0)


@pytest.fixture()
def fake_provider(monkeypatch):
    fake = FakeProvider()
    service = container.form_ai_chat_service()
    monkeypatch.setattr(service, "_provider_resolver", lambda name: fake)
    return fake


async def _make_v2(form_doc: FormDocument) -> str:
    """The shared fixture form is v1-flat; the chat flow targets v2 pages."""
    form_doc.fields = [
        StandardFormField(
            id="page-1",
            index=0,
            type=StandardFormFieldType.SLIDE,
            properties=StandardFieldProperty(
                fields=[
                    StandardFormField(
                        id="field-1",
                        index=0,
                        type=StandardFormFieldType.SHORT_TEXT,
                        title="Your name",
                        properties=StandardFieldProperty(fields=[]),
                    )
                ]
            ),
        )
    ]
    await container.form_repo().save_form(form_doc)
    return "page-1"


def _all_titles(form_doc: FormDocument):
    return [
        f.title
        for s in form_doc.fields or []
        if str(getattr(s.type, "value", s.type)) == "slide"
        for f in ((s.properties.fields if s.properties else None) or [])
    ]


class TestFormAIChat:
    async def test_turn_applies_ops_and_persists_draft(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        page_id = await _make_v2(form_doc)
        fake_provider.replies = [
            json.dumps(
                {
                    "reply": "Added an email question for you.",
                    "ops": [
                        {
                            "op": "add_field",
                            "pageId": page_id,
                            "field": {
                                "title": "Work email",
                                "type": "email",
                                "required": True,
                            },
                        }
                    ],
                }
            )
        ]

        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "add a required work email question"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["reply"] == "Added an email question for you."
        assert body["results"][0]["ok"] is True
        assert "Work email" in body["results"][0]["message"]

        # Draft persisted
        saved = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        assert "Work email" in _all_titles(saved)

        # Session recorded with the auditable ops + results
        session = await FormAISessionDocument.get(body["sessionId"])
        assert session is not None
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["ops"][0]["op"] == "add_field"

        # The provider saw the snapshot + guardrails, not the whole document
        system = fake_provider.calls[0]["system"]
        assert "<form_snapshot>" in system and "dark patterns" in system

    async def test_settings_op_updates_purpose_and_retention(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        """The exact user journey that surfaced this gap: 'update the purpose
        and retention for this form' must land in the Form tab's settings."""
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        await _make_v2(form_doc)
        fake_provider.replies = [
            json.dumps(
                {
                    "reply": "Set the purpose and retention.",
                    "ops": [
                        {
                            "op": "update_form_settings",
                            "patch": {
                                "purpose": "To schedule your appointment",
                                "retentionText": "kept for 90 days",
                            },
                        }
                    ],
                }
            ),
            json.dumps({"memories": []}),  # background extraction
        ]

        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "update the purpose and retention for this form"},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["results"][0]["ok"] is True
        assert (
            "purpose" in body["results"][0]["message"]
            and "retention" in body["results"][0]["message"]
        )
        # The response carries the updated settings for the Form tab.
        assert body["settings"]["purpose"] == "To schedule your appointment"
        assert body["settings"]["retentionText"] == "kept for 90 days"

        # Persisted on the workspace-form association (where the Form tab reads).
        from backend.app.schemas.workspace_form import WorkspaceFormDocument

        workspace_form_doc = (
            await container.workspace_form_repo().find_first_by_form_id(
                workspace_form.form_id
            )
        )
        assert workspace_form_doc.settings.purpose == "To schedule your appointment"
        assert workspace_form_doc.settings.retention_text == "kept for 90 days"

        # …and the model could SEE the current settings in its snapshot.
        assert '"settings"' in fake_provider.calls[0]["system"]

    async def test_settings_op_clears_with_empty_string(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        form_doc = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        await _make_v2(form_doc)
        from backend.app.schemas.workspace_form import WorkspaceFormDocument

        workspace_form_doc = (
            await container.workspace_form_repo().find_first_by_form_id(
                workspace_form.form_id
            )
        )
        workspace_form_doc.settings.purpose = "Old purpose"
        await container.workspace_form_repo().save(workspace_form_doc)

        fake_provider.replies = [
            json.dumps(
                {
                    "reply": "Cleared.",
                    "ops": [{"op": "update_form_settings", "patch": {"purpose": ""}}],
                }
            ),
            json.dumps({"memories": []}),
        ]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "remove the purpose text"},
        )
        assert response.status_code == 200
        refreshed = await container.workspace_form_repo().find_first_by_form_id(
            workspace_form.form_id
        )
        assert refreshed.settings.purpose is None

    async def test_second_turn_carries_history(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        # Each turn consumes TWO replies: the chat itself, then the
        # background memory extraction that follows it.
        fake_provider.replies = [
            json.dumps({"reply": "Okay.", "ops": []}),
            json.dumps({"memories": []}),
            json.dumps({"reply": "Done.", "ops": []}),
            json.dumps({"memories": []}),
        ]
        url = (
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat"
        )
        first = await client.post(
            url, cookies=test_user_cookies, json={"message": "hello"}
        )
        session_id = first.json()["sessionId"]
        second = await client.post(
            url,
            cookies=test_user_cookies,
            json={"message": "again", "sessionId": session_id},
        )
        assert second.status_code == 200
        assert second.json()["sessionId"] == session_id
        # Second CHAT call (calls[2]; calls[1] was turn 1's extraction)
        # includes the first exchange.
        second_messages = fake_provider.calls[2]["messages"]
        assert [m["content"] for m in second_messages] == ["hello", "Okay.", "again"]

    async def test_failed_op_reported_not_fatal(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        fake_provider.replies = [
            json.dumps(
                {
                    "reply": "Tried two things.",
                    "ops": [
                        {"op": "remove_field", "fieldId": "does-not-exist"},
                        {"op": "update_form_info", "title": "Renamed by AI"},
                    ],
                }
            )
        ]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "remove something and rename"},
        )
        body = response.json()
        assert body["results"][0]["ok"] is False
        assert body["results"][1]["ok"] is True
        saved = await container.form_repo().get_form_document_by_id(
            workspace_form.form_id
        )
        assert saved.title == "Renamed by AI"

    async def test_unusable_model_reply_changes_nothing(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        before = (
            await container.form_repo().get_form_document_by_id(workspace_form.form_id)
        ).model_dump()
        fake_provider.replies = ["I refuse to speak JSON today."]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "do something"},
        )
        assert response.status_code == 502
        after = (
            await container.form_repo().get_form_document_by_id(workspace_form.form_id)
        ).model_dump()
        assert after == before

    async def test_unknown_form_404(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/000000000000000000000000/ai/chat",
            cookies=test_user_cookies,
            json={"message": "hi"},
        )
        assert response.status_code == 404
