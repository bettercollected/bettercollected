"""MCP tools of the form spec: get_form_spec, validate_form, dry_run_ops,
and update_form's atomic mode — scopes, audit, nothing stored on a dry run."""

import json
from typing import Any, Coroutine

from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from tests.app.controllers.test_mcp_server import (
    MCP_HEADERS,
    MCP_URL,
    _call_tool,
    _make_key,
    _make_v2,
    _parse_rpc,
    _tool_text,
)


async def _v2(form_id: str) -> FormDocument:
    doc = await container.form_repo().get_form_document_by_id(form_id)
    await _make_v2(doc)
    return await container.form_repo().get_form_document_by_id(form_id)


async def _audited(workspace_id, tool: str):
    logs = await container.mcp_audit_log_repo().list_by_workspace(workspace_id)
    return [log for log in logs if log.tool == tool]


def _error_text(result) -> str:
    assert result.get("isError") is True, result
    return result["content"][0]["text"]


class TestMCPFormSpec:
    async def test_the_new_tools_are_listed(
        self, client: AsyncClient, workspace: Coroutine[Any, Any, WorkspaceDocument]
    ):
        token = await _make_key(workspace.id, ["forms:read"])
        response = await client.post(
            MCP_URL,
            headers={**MCP_HEADERS, "Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            follow_redirects=True,
        )
        tools = {t["name"]: t for t in _parse_rpc(response)["result"]["tools"]}
        assert {"get_form_spec", "validate_form", "dry_run_ops"} <= set(tools)
        assert "atomic" in tools["update_form"]["inputSchema"]["properties"]

    async def test_get_form_spec_with_a_read_key(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        token = await _make_key(workspace.id, ["forms:read"])
        # a form not built from pages has no spec document
        result = await _call_tool(
            client, token, "get_form_spec", {"form_id": workspace_form.form_id}
        )
        assert "not built from pages" in _error_text(result)

        await _v2(workspace_form.form_id)
        spec = _tool_text(
            await _call_tool(
                client, token, "get_form_spec", {"form_id": workspace_form.form_id}
            )
        )
        assert spec["specVersion"] == "1"
        assert spec["pages"][0]["fields"][0]["title"] == "Your name"
        assert "formId" not in spec
        assert [log.ok for log in await _audited(workspace.id, "get_form_spec")] in (
            [False, True],
            [True, False],
        )

    async def test_validate_form_with_a_read_key(
        self, client: AsyncClient, workspace: Coroutine[Any, Any, WorkspaceDocument]
    ):
        token = await _make_key(workspace.id, ["forms:read"])
        good = {
            "specVersion": "1",
            "pages": [{"id": "p", "fields": [{"id": "q", "type": "short_text"}]}],
        }
        result = _tool_text(
            await _call_tool(client, token, "validate_form", {"spec": good})
        )
        assert result["valid"] is True
        bad = {"specVersion": "1", "pages": [{"id": "p", "jumps": [{"target": "x"}]}]}
        result = _tool_text(
            await _call_tool(client, token, "validate_form", {"spec": bad})
        )
        assert result["valid"] is False
        assert result["errors"][0]["path"] == "/pages/0/jumps/0/target"
        assert result["compliance"]["checked"] is False
        assert len(await _audited(workspace.id, "validate_form")) == 2

    async def test_dry_run_needs_the_write_scope_and_stores_nothing(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        form = await _v2(workspace_form.form_id)
        ops = [
            {"op": "add_page", "ref": "pg"},
            {
                "op": "add_field",
                "pageId": "$ref:pg",
                "field": {"title": "City", "type": "short_text"},
            },
        ]
        read_only = await _make_key(workspace.id, ["forms:read"])
        result = await _call_tool(
            client, read_only, "dry_run_ops", {"form_id": form.form_id, "ops": ops}
        )
        assert "forms:write" in _error_text(result)

        token = await _make_key(workspace.id, ["forms:read", "forms:write"])
        preview = _tool_text(
            await _call_tool(
                client, token, "dry_run_ops", {"form_id": form.form_id, "ops": ops}
            )
        )
        assert preview["ok"] is True and preview["applied"] is True
        assert len(preview["form"]["pages"]) == 2
        assert preview["diff"]["pages"]["added"][0]["path"] == "/pages/1"
        assert preview["results"][0]["createdId"]

        stored = await container.form_repo().get_form_document_by_id(form.form_id)
        assert stored.model_dump() == form.model_dump()
        logs = await _audited(workspace.id, "dry_run_ops")
        assert len(logs) == 1 and "dry run" in logs[0].detail

    async def test_update_form_atomic_is_all_or_nothing(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        form = await _v2(workspace_form.form_id)
        token = await _make_key(workspace.id, ["forms:read", "forms:write"])
        failing = [
            {"op": "update_form_info", "title": "Should not stick"},
            {"op": "update_form_settings", "patch": {"purpose": "Should not stick"}},
            {"op": "remove_field", "fieldId": "ghost"},
        ]
        result = _tool_text(
            await _call_tool(
                client,
                token,
                "update_form",
                {"form_id": form.form_id, "ops": failing, "atomic": True},
            )
        )
        assert result["applied"] is False and result["settings"] is None
        assert [r["ok"] for r in result["results"]] == [True, True, False]
        stored = await container.form_repo().get_form_document_by_id(form.form_id)
        assert stored.title == form.title
        association = await container.workspace_form_repo().find_workspace_form(
            workspace.id, form.form_id
        )
        assert association.settings.purpose is None

        clean = [
            {
                "op": "add_page",
                "ref": "pg",
                "fields": [{"title": "Q", "type": "yes_no", "ref": "q"}],
            },
            {
                "op": "add_field",
                "pageId": "$ref:pg",
                "ref": "r",
                "field": {"title": "R", "type": "short_text"},
            },
            {
                "op": "set_field_logic",
                "fieldId": "$ref:r",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {"fieldId": "$ref:q", "comparison": "IS_EQUAL", "value": "Yes"}
                    ],
                },
            },
        ]
        result = _tool_text(
            await _call_tool(
                client,
                token,
                "update_form",
                {"form_id": form.form_id, "ops": clean, "atomic": True},
            )
        )
        assert result["applied"] is True, result
        stored = await container.form_repo().get_form_document_by_id(form.form_id)
        new_page = stored.fields[1]
        q, r = new_page.properties.fields
        assert r.properties.logic.conditions[0].field_id == q.id
        logs = await _audited(workspace.id, "update_form")
        assert any("(atomic)" in log.detail for log in logs)
        assert json.dumps(result)  # serialisable as sent
