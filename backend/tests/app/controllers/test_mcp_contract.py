"""The MCP server's public contract, held still across SDK upgrades.

MCP clients must not notice a change of the ``mcp`` SDK: the tool names,
inputs and outputs (tests/fixtures/mcp/tools_list.json), the scope each tool
needs, the audit entry of each call, the ``responses:read`` acknowledgement
and the workspace AI opt-in. Every call goes through the real
/api/v1/mcp transport with a real Bearer API key; one test drives it with
the SDK's own client, as an MCP client would.

The snapshot is the tools/list reply as mcp 1.x served it. Change it only
for a deliberate change to a tool: copy the new reply's
``result.tools`` (and the initialize reply's ``instructions``) into it.
"""

import json
from pathlib import Path
from typing import Any, Coroutine

import pytest
from httpx import AsyncClient

from common.models.standard_form import StandardFormResponse

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from tests.app.ai_helpers import (
    OUTLINE,
    OUTLINE_REPLY,
    FakeProvider,
    enable_ai,
    use_fake_provider,
)
from tests.app.controllers.data import formResponse, testUser, testUser2
from tests.app.controllers.test_mcp_server import (
    MCP_HEADERS,
    MCP_URL,
    _call_tool,
    _make_key,
    _make_v2,
    _parse_rpc,
    _tool_text,
)

SNAPSHOT = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "mcp" / "tools_list.json").read_text()
)

# The scope each tool needs; a key without it is refused before anything runs.
TOOL_SCOPES = {
    "list_forms": "forms:read",
    "get_form": "forms:read",
    "get_form_spec": "forms:read",
    "validate_form": "forms:read",
    "get_ai_profile": "forms:read",
    "create_form": "forms:write",
    "create_form_with_ai": "forms:write",
    "create_form_outline": "forms:write",
    "build_form_from_outline": "forms:write",
    "update_form": "forms:write",
    "dry_run_ops": "forms:write",
    "publish_form": "forms:write",
    "list_responses": "responses:read",
    "get_response": "responses:read",
    "list_deletion_requests": "deletion_requests:read",
}
ALL_SCOPES = [
    "forms:read",
    "forms:write",
    "responses:read",
    "deletion_requests:read",
    "deletion_requests:write",
]
AI_TOOLS = ("create_form_with_ai", "create_form_outline", "build_form_from_outline")
PROTOCOL_VERSION = "2025-06-18"


def _arguments(tool: str, form_id: str) -> dict:
    """Arguments that pass the tool's input schema."""
    return {
        "list_forms": {},
        "get_form": {"form_id": form_id},
        "get_form_spec": {"form_id": form_id},
        "validate_form": {"spec": {}},
        "get_ai_profile": {},
        "create_form": {"title": "Contract"},
        "create_form_with_ai": {"prompt": "a contact form"},
        "create_form_outline": {"prompt": "a contact form"},
        "build_form_from_outline": {"outline": OUTLINE},
        "update_form": {"form_id": form_id, "ops": []},
        "dry_run_ops": {"form_id": form_id, "ops": []},
        "publish_form": {"form_id": form_id},
        "list_responses": {"form_id": form_id},
        "get_response": {"response_id": "0" * 24},
        "list_deletion_requests": {},
    }[tool]


async def _rpc(client: AsyncClient, token: str, method: str, params=None, id=1):
    body = {"jsonrpc": "2.0", "method": method}
    if id is not None:
        body["id"] = id
    if params is not None:
        body["params"] = params
    return await client.post(
        MCP_URL,
        headers={
            **MCP_HEADERS,
            "Authorization": f"Bearer {token}",
            "Mcp-Protocol-Version": PROTOCOL_VERSION,
        },
        json=body,
        follow_redirects=True,
    )


async def _audit_rows(workspace_id, key_id: str):
    logs = await container.mcp_audit_log_repo().list_by_workspace(workspace_id)
    return [log for log in logs if log.key_id == key_id]


@pytest.fixture()
def fake(monkeypatch):
    fake = FakeProvider()
    use_fake_provider(monkeypatch, fake)
    return fake


class TestToolList:
    def test_every_tool_has_a_scope(self):
        assert set(TOOL_SCOPES) == {t["name"] for t in SNAPSHOT["tools"]}

    async def test_the_tool_list_is_the_snapshot(
        self, client: AsyncClient, workspace: Coroutine[Any, Any, WorkspaceDocument]
    ):
        token = await _make_key(workspace.id, ["forms:read"])
        initialize = await _rpc(
            client,
            token,
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "contract-test", "version": "0"},
            },
        )
        assert initialize.status_code == 200, initialize.text
        result = _parse_rpc(initialize)["result"]
        assert result["protocolVersion"] == PROTOCOL_VERSION
        assert result["serverInfo"]["name"] == "bettercollected"
        assert result["instructions"] == SNAPSHOT["instructions"]
        assert result["capabilities"]["tools"] == {"listChanged": False}

        listed = await _rpc(client, token, "tools/list", id=2)
        assert listed.status_code == 200, listed.text
        tools = _parse_rpc(listed)["result"]["tools"]
        assert [t["name"] for t in tools] == [t["name"] for t in SNAPSHOT["tools"]]
        for tool, expected in zip(tools, SNAPSHOT["tools"]):
            assert tool == expected, tool["name"]

    async def test_errors_read_as_before(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        monkeypatch,
    ):
        token = await _make_key(workspace.id, ["forms:read", "forms:write"])
        unknown = await _call_tool(client, token, "no_such_tool", {})
        assert unknown == {
            "content": [{"type": "text", "text": "Unknown tool: no_such_tool"}],
            "isError": True,
        }
        missing = await _call_tool(client, token, "get_form", {})
        assert missing["isError"] is True
        assert missing["content"][0]["text"].startswith(
            "Error executing tool get_form: 1 validation error for get_formArguments\n"
            "form_id\n  Field required"
        )
        # a refusal of the product's services is an error result with its
        # text (empty here, as before), not a hidden crash
        async def refuse(*args, **kwargs):
            raise HTTPException(status_code=409, content={"message": "Not now"})

        monkeypatch.setattr(
            container.workspace_form_service(), "publish_form", refuse
        )
        refused = await _call_tool(
            client, token, "publish_form", {"form_id": workspace_form.form_id}
        )
        assert refused == {
            "content": [{"type": "text", "text": "Error executing tool publish_form: "}],
            "isError": True,
        }

    async def test_a_refusal_is_not_logged_with_the_callers_input(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        caplog,
    ):
        token = await _make_key(workspace.id, ["forms:read", "forms:write"])
        marker = "Marker-title-7f3a"
        with caplog.at_level("INFO"):
            result = await _call_tool(
                client,
                token,
                "update_form",
                {
                    "form_id": workspace_form.form_id,
                    "ops": [
                        {
                            "op": "add_field",
                            "pageId": "page",
                            "field": {"title": "Name", "type": marker},
                        }
                    ],
                },
            )
        assert result["isError"] is True
        # the caller is told why, quoting its input, as before
        assert result["content"][0]["text"].startswith(
            "Error executing tool update_form: "
        )
        assert marker in result["content"][0]["text"]
        assert not [r for r in caplog.records if marker in r.getMessage()]

    async def test_a_result_carries_text_and_structured_content(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        token = await _make_key(workspace.id, ["forms:read"])
        result = await _call_tool(client, token, "list_forms", {})
        assert set(result) == {"content", "structuredContent", "isError"}
        assert result["isError"] is False
        text = result["content"][0]["text"]
        assert result["content"] == [{"type": "text", "text": text}]
        assert result["structuredContent"] == {"result": text}
        assert [f["formId"] for f in json.loads(text)] == [workspace_form.form_id]


class TestScopes:
    @pytest.mark.parametrize("tool", sorted(TOOL_SCOPES))
    async def test_a_key_without_the_scope_is_refused(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        fake: FakeProvider,
        tool: str,
    ):
        scope = TOOL_SCOPES[tool]
        token = await _make_key(workspace.id, [s for s in ALL_SCOPES if s != scope])
        result = await _call_tool(
            client, token, tool, _arguments(tool, workspace_form.form_id)
        )
        assert result == {
            "content": [
                {
                    "type": "text",
                    "text": f"Error executing tool {tool}: "
                    f"This API key lacks the '{scope}' scope.",
                }
            ],
            "isError": True,
        }
        assert fake.calls == []

    @pytest.mark.parametrize("tool", sorted(TOOL_SCOPES))
    async def test_the_scope_alone_is_enough(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        fake: FakeProvider,
        tool: str,
    ):
        await enable_ai(workspace)
        fake.replies = [OUTLINE_REPLY] * 3
        token = await _make_key(workspace.id, [TOOL_SCOPES[tool]])
        result = await _call_tool(
            client, token, tool, _arguments(tool, workspace_form.form_id)
        )
        # get_response asks for a response that doesn't exist and get_form_spec
        # for a form that isn't page-based; neither is a scope refusal.
        text = result["content"][0]["text"]
        assert "lacks the" not in text and "Forbidden" not in text, text


class TestAudit:
    async def test_every_call_is_audited_with_its_key(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        form_id = workspace_form.form_id
        created = await container.api_key_service().create_key(
            workspace.id,
            CreateAPIKeyDto(
                name="audit",
                scopes=ALL_SCOPES,
                acknowledge_unredacted_responses=True,
            ),
            testUser,
        )
        token = created.token

        async def call(tool, arguments):
            return _tool_text(await _call_tool(client, token, tool, arguments))

        await call("publish_form", {"form_id": form_id})
        response = await container.workspace_form_service().submit_response(
            workspace.id,
            form_id,
            StandardFormResponse(**formResponse),
            testUser2,
        )
        form_doc = await container.form_repo().get_form_document_by_id(form_id)
        page_id = await _make_v2(form_doc)

        assert len(await call("list_forms", {})) == 1
        await call("get_form", {"form_id": form_id})
        spec = await call("get_form_spec", {"form_id": form_id})
        assert (await call("validate_form", {"spec": spec}))["valid"] is True
        add = [
            {
                "op": "add_field",
                "pageId": page_id,
                "field": {"title": "Work email", "type": "email"},
            }
        ]
        await call("dry_run_ops", {"form_id": form_id, "ops": add})
        await call("update_form", {"form_id": form_id, "ops": add, "atomic": True})
        assert len(await call("list_responses", {"form_id": form_id})) == 1
        await call("get_response", {"response_id": response.response_id})
        assert await call("list_deletion_requests", {}) == []
        await call("get_ai_profile", {})
        new_form = await call("create_form", {"title": "Audited"})
        refused = await _call_tool(
            client, token, "create_form_with_ai", {"prompt": " "}
        )
        assert refused["isError"] is True

        rows = await _audit_rows(workspace.id, created.id)
        assert {r.workspace_id for r in rows} == {workspace.id}
        assert all(r.at is not None for r in rows)
        assert sorted((r.tool, r.ok, r.detail) for r in rows) == sorted(
            [
                ("list_forms", True, "1 forms"),
                ("get_form", True, form_id),
                ("get_form_spec", True, form_id),
                ("validate_form", True, "0 errors"),
                ("dry_run_ops", True, f"{form_id}: 1 ops (dry run)"),
                ("update_form", True, f"{form_id}: 1 ops (atomic)"),
                ("publish_form", True, form_id),
                ("list_responses", True, f"{form_id}: 1"),
                ("get_response", True, response.response_id),
                ("list_deletion_requests", True, "0 requests"),
                ("get_ai_profile", True, ""),
                ("create_form", True, new_form["formId"]),
                ("create_form_with_ai", False, "prompt length"),
            ]
        )


class TestAcknowledgement:
    async def test_responses_read_needs_the_acknowledgement(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        published_form,
    ):
        with pytest.raises(HTTPException) as refused:
            await container.api_key_service().create_key(
                workspace.id,
                CreateAPIKeyDto(name="reader", scopes=["responses:read"]),
                testUser,
            )
        assert refused.value.status_code == 400
        assert "unredacted" in refused.value.content

        created = await container.api_key_service().create_key(
            workspace.id,
            CreateAPIKeyDto(
                name="reader",
                scopes=["responses:read"],
                acknowledge_unredacted_responses=True,
            ),
            testUser,
        )
        assert created.responses_read_acknowledged_by == testUser.id
        assert created.responses_read_acknowledged_at is not None
        listed = _tool_text(
            await _call_tool(
                client,
                created.token,
                "list_responses",
                {"form_id": published_form.form_id},
            )
        )
        assert listed == []


class TestAIOptIn:
    @pytest.mark.parametrize("tool", AI_TOOLS)
    async def test_ai_tools_need_the_workspace_opt_in(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        fake: FakeProvider,
        tool: str,
    ):
        created = await container.api_key_service().create_key(
            workspace.id,
            CreateAPIKeyDto(name="ai", scopes=["forms:write"]),
            testUser,
        )
        arguments = _arguments(tool, "")
        refused = await _call_tool(client, created.token, tool, arguments)
        assert refused["isError"] is True
        assert "AI features are off" in refused["content"][0]["text"]
        assert fake.calls == []
        rows = await _audit_rows(workspace.id, created.id)
        assert [(r.tool, r.ok) for r in rows] == [(tool, False)]
        assert "AI features are off" in rows[0].detail

        await enable_ai(workspace)
        fake.replies = [OUTLINE_REPLY] * 3
        done = _tool_text(await _call_tool(client, created.token, tool, arguments))
        assert done.get("formId") or done.get("outline")
        rows = await _audit_rows(workspace.id, created.id)
        assert sorted((r.tool, r.ok) for r in rows) == [(tool, False), (tool, True)]


class TestTransport:
    async def test_a_session_as_a_client_runs_it(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
    ):
        """initialize, the initialized notification, tools/list and
        tools/call over streamable HTTP, with the headers clients send."""
        token = await _make_key(workspace.id, ["forms:read"])
        initialize = await _rpc(
            client,
            token,
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "contract-test", "version": "0"},
            },
        )
        assert initialize.status_code == 200
        # stateless: no session to resume
        assert "mcp-session-id" not in initialize.headers
        initialized = await _rpc(
            client, token, "notifications/initialized", id=None
        )
        assert initialized.status_code == 202, initialized.text
        listed = await _rpc(client, token, "tools/list", id=2)
        assert len(_parse_rpc(listed)["result"]["tools"]) == len(SNAPSHOT["tools"])
        called = await _rpc(
            client,
            token,
            "tools/call",
            {"name": "get_form", "arguments": {"form_id": workspace_form.form_id}},
            id=3,
        )
        reply = _parse_rpc(called)
        assert reply["id"] == 3
        assert json.loads(reply["result"]["content"][0]["text"])["formId"] == (
            workspace_form.form_id
        )

    async def test_the_endpoint_and_its_auth(self, client: AsyncClient):
        for path in (MCP_URL, MCP_URL + "/"):
            response = await client.post(
                path,
                headers=MCP_HEADERS,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                follow_redirects=True,
            )
            assert response.status_code == 401
            assert response.json() == {
                "error": "Provide a valid workspace API key as a Bearer token."
            }

    @pytest.mark.parametrize("mode", ["legacy", "auto"])
    async def test_the_sdk_client_lists_and_calls_tools(
        self,
        _initialized_app,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        workspace_form: Coroutine[Any, Any, FormDocument],
        mode: str,
    ):
        """The SDK's own client, as an MCP client would connect: the
        handshake era ("legacy") and whatever it negotiates by itself."""
        import httpx2
        from mcp.client import Client
        from mcp.client.streamable_http import streamable_http_client

        token = await _make_key(workspace.id, ["forms:read"])
        http = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=_initialized_app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        )
        async with http:
            transport = streamable_http_client(
                "http://test" + MCP_URL, http_client=http
            )
            async with Client(transport, mode=mode) as session:
                listed = await session.list_tools()
                assert [t.name for t in listed.tools] == [
                    t["name"] for t in SNAPSHOT["tools"]
                ]
                result = await session.call_tool("list_forms", {})
                assert not result.is_error
                forms = json.loads(result.content[0].text)
                assert [f["formId"] for f in forms] == [workspace_form.form_id]
                refused = await session.call_tool(
                    "get_response", {"response_id": "0" * 24}
                )
                assert refused.is_error
                assert "responses:read" in refused.content[0].text
