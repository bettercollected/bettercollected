"""AI preference memory — endpoints + extraction through the chat flow."""

import json
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from tests.app.controllers.data import testUser
from backend.app.container import container
from tests.app.ai_helpers import FakeProvider, enable_ai, use_fake_provider
from backend.app.schemas.ai_preference_memory import UserAIPreferenceMemoryDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.services.ai.memory import EXTRACTION_SYSTEM_PROMPT


@pytest.fixture()
async def fake_provider(monkeypatch, workspace):
    # AI on for the fixture workspace (#715); the provider is a fake
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    await enable_ai(workspace)
    return fake


class TestAIMemoryEndpoints:
    async def test_starts_empty(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        response = await client.get(
            f"/api/v1/workspaces/{workspace.id}/ai-memory", cookies=test_user_cookies
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_add_dedupe_and_delete(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        url = f"/api/v1/workspaces/{workspace.id}/ai-memory"
        added = await client.post(
            url, cookies=test_user_cookies, json={"text": "Prefers short pages"}
        )
        assert added.status_code == 200
        assert [e["text"] for e in added.json()] == ["Prefers short pages"]
        assert added.json()[0]["source"] == "manual"

        # Case-insensitive dedupe: no second copy.
        again = await client.post(
            url, cookies=test_user_cookies, json={"text": "prefers SHORT pages"}
        )
        assert len(again.json()) == 1

        entry_id = added.json()[0]["id"]
        deleted = await client.delete(f"{url}/{entry_id}", cookies=test_user_cookies)
        assert deleted.status_code == 200
        assert deleted.json() == []

    async def test_delete_unknown_entry_404(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        response = await client.delete(
            f"/api/v1/workspaces/{workspace.id}/ai-memory/nope",
            cookies=test_user_cookies,
        )
        assert response.status_code == 404

    async def test_rejects_oversized_entry(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/ai-memory",
            cookies=test_user_cookies,
            json={"text": "x" * 500},
        )
        assert response.status_code == 422


async def _learn(client, workspace, cookies, enabled: bool = True):
    response = await client.put(
        f"/api/v1/workspaces/{workspace.id}/ai-memory/settings",
        cookies=cookies,
        json={"learnPreferences": enabled},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"learnPreferences": enabled}


class TestExtractionThroughChat:
    async def test_no_extraction_without_learn_my_preferences(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        """Default off: a chat turn makes exactly one provider call and
        nothing is remembered."""
        fake_provider.replies = [
            json.dumps({"reply": "Done.", "ops": []}),
            json.dumps({"memories": ["Should never be stored"]}),
        ]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "never add placeholder text to my inputs"},
        )
        assert response.status_code == 200, response.text
        assert len(fake_provider.calls) == 1
        assert (
            await container.ai_preference_memory_repo().find(workspace.id, testUser.id)
            is None
        )

        # Turned on and off again: still no extraction.
        await _learn(client, workspace, test_user_cookies, True)
        await _learn(client, workspace, test_user_cookies, False)
        fake_provider.calls.clear()
        fake_provider.replies = [
            json.dumps({"reply": "Done.", "ops": []}),
            json.dumps({"memories": ["Should never be stored"]}),
        ]
        await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "again"},
        )
        assert len(fake_provider.calls) == 1
        document = await container.ai_preference_memory_repo().find(
            workspace.id, testUser.id
        )
        assert document.entries == []

    async def test_extraction_stops_when_workspace_ai_is_off(
        self,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
        client: AsyncClient,
        fake_provider: FakeProvider,
    ):
        from backend.app.services.ai.memory import AIMemoryService
        from tests.app.ai_helpers import disable_ai

        await _learn(client, workspace, test_user_cookies, True)
        await disable_ai(workspace)
        fake_provider.replies = [json.dumps({"memories": ["x"]})]
        await AIMemoryService().extract_from_turn(
            fake_provider, workspace.id, testUser.id, "hi", "ok"
        )
        assert fake_provider.calls == []

    async def test_chat_turn_extracts_memory_in_background(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        await _learn(client, workspace, test_user_cookies)
        fake_provider.replies = [
            json.dumps(
                {"reply": "Done — no placeholders.", "ops": []}
            ),  # the chat turn
            json.dumps(
                {"memories": ["Does not want placeholder text in inputs"]}
            ),  # extraction
        ]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "never add placeholder text to my inputs"},
        )
        assert response.status_code == 200

        # Background task ran after the response; both provider calls happened.
        assert len(fake_provider.calls) == 2
        # The extraction call must use THE extraction prompt, verbatim — a
        # substring check would let a rewired/garbled prompt pass silently.
        extraction_call = fake_provider.calls[1]
        assert extraction_call["system"] == EXTRACTION_SYSTEM_PROMPT.format(
            existing="(empty)"
        )
        # …and it must be fed the actual turn (what the creator said and what
        # the assistant did), or extraction degrades into guessing.
        turn_payload = extraction_call["messages"][0]["content"]
        assert "never add placeholder text to my inputs" in turn_payload
        assert "Done — no placeholders." in turn_payload

        document = await container.ai_preference_memory_repo().find(
            workspace.id, testUser.id
        )
        assert document is not None
        assert [e["text"] for e in document.entries] == [
            "Does not want placeholder text in inputs"
        ]
        assert document.entries[0]["source"] == "extracted"

    async def test_extraction_failure_never_breaks_the_turn(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        await _learn(client, workspace, test_user_cookies)
        # Only ONE reply queued: the extraction call will raise (pop from
        # empty) inside the background task — and must be swallowed.
        fake_provider.replies = [json.dumps({"reply": "Okay.", "ops": []})]
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "hello"},
        )
        assert response.status_code == 200
        assert response.json()["reply"] == "Okay."

    async def test_memory_is_injected_into_the_next_turn(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        test_user_cookies: dict[str, str],
        fake_provider: FakeProvider,
    ):
        await client.post(
            f"/api/v1/workspaces/{workspace.id}/ai-memory",
            cookies=test_user_cookies,
            json={"text": "Prefers British English"},
        )
        fake_provider.replies = [
            json.dumps({"reply": "Noted.", "ops": []}),
            json.dumps({"memories": []}),
        ]
        await client.post(
            f"/api/v1/workspaces/{workspace.id}/forms/{workspace_form.form_id}/ai/chat",
            cookies=test_user_cookies,
            json={"message": "hi"},
        )
        system = fake_provider.calls[0]["system"]
        assert "<creator_preferences>" in system
        assert "Prefers British English" in system
        assert "lowest precedence" in system
