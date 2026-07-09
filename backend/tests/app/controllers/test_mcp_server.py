"""MCP server — auth middleware + tool round-trips over streamable HTTP.

The session-scoped app fixture runs the real lifespan, so the MCP session
manager is live and these tests exercise the actual /api/v1/mcp transport
with real Bearer API keys — no mocking of the auth path.
"""

import json
from typing import Any, Coroutine

from httpx import AsyncClient

from common.models.standard_form import (
    StandardFieldProperty,
    StandardFormField,
    StandardFormFieldType,
)

from backend.app.container import container
from backend.app.schemas.mcp_audit_log import MCPAuditLogDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from tests.app.controllers.data import testUser, testUser1

MCP_URL = "/api/v1/mcp"
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


async def _make_key(workspace_id, scopes, user=testUser):
    created = await container.api_key_service().create_key(
        workspace_id, CreateAPIKeyDto(name="test key", scopes=scopes), user
    )
    return created.token


def _parse_rpc(response):
    """The streamable-HTTP transport answers JSON or a one-event SSE stream."""
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        raise AssertionError(f"No data event in SSE reply: {response.text!r}")
    return response.json()


async def _call_tool(client: AsyncClient, token: str, name: str, arguments: dict):
    response = await client.post(
        MCP_URL,
        headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        follow_redirects=True,
    )
    assert response.status_code == 200, response.text
    return _parse_rpc(response)["result"]


def _tool_text(result):
    assert not result.get("isError"), result
    return json.loads(result["content"][0]["text"])


async def _make_v2(form_doc: FormDocument) -> str:
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
    await form_doc.save()
    return "page-1"


class TestMCPServer:
    async def test_rejects_missing_and_bad_tokens(self, client: AsyncClient):
        for headers in (
            MCP_HEADERS,
            {**MCP_HEADERS, "Authorization": "Bearer bc_not_a_real_key"},
            {**MCP_HEADERS, "Authorization": "Basic dXNlcjpwYXNz"},
        ):
            response = await client.post(
                MCP_URL,
                headers=headers,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                follow_redirects=True,
            )
            assert response.status_code == 401, response.text
            assert "API key" in response.json()["error"]

    async def test_list_and_get_form(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        token = await _make_key(workspace.id, ["forms:read"])
        forms = _tool_text(await _call_tool(client, token, "list_forms", {}))
        assert [f["formId"] for f in forms] == [workspace_form.form_id]

        form = _tool_text(
            await _call_tool(client, token, "get_form", {"form_id": workspace_form.form_id})
        )
        assert form["formId"] == workspace_form.form_id
        assert "fields" in form

    async def test_update_form_persists_and_audits(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        form_doc = await FormDocument.find_one({"form_id": workspace_form.form_id})
        page_id = await _make_v2(form_doc)
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
                            "op": "add_field",
                            "pageId": page_id,
                            "field": {"title": "Work email", "type": "email"},
                        }
                    ],
                },
            )
        )
        assert all(r["ok"] for r in result["results"]), result

        # The edit is persisted through the same write path as builder chat.
        refreshed = await FormDocument.find_one({"form_id": workspace_form.form_id})
        titles = [
            f.title
            for f in (refreshed.fields[0].properties.fields or [])
        ]
        assert "Work email" in titles

        # Every tool call is audited against the key.
        logs = await MCPAuditLogDocument.find(
            MCPAuditLogDocument.workspace_id == workspace.id
        ).to_list()
        assert any(log.tool == "update_form" and log.ok for log in logs)

    async def test_scope_is_enforced_per_tool(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        token = await _make_key(workspace.id, ["forms:read"])
        result = await _call_tool(
            client,
            token,
            "update_form",
            {"form_id": workspace_form.form_id, "ops": []},
        )
        assert result.get("isError") is True
        assert "forms:write" in result["content"][0]["text"]

    async def test_cross_workspace_form_is_invisible(
        self,
        client: AsyncClient,
        workspace_1: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        # Key belongs to workspace_1; the form lives in the other workspace.
        token = await _make_key(workspace_1.id, ["forms:read"], user=testUser1)
        result = await _call_tool(
            client, token, "get_form", {"form_id": workspace_form.form_id}
        )
        assert result.get("isError") is True
        assert "does not exist in this workspace" in result["content"][0]["text"]
