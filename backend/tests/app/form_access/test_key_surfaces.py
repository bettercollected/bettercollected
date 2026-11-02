"""The surfaces a key reaches: a key limited to a list of forms creates no form
(the public API's ``POST /forms`` and the four MCP tools that make one), and
the MCP server counts a key's calls against the public API's budgets. Stored
limits are enforced whatever ``API_KEY_ROLES_ENABLED`` says. Everything here is
synthetic."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.public_api import auth as public_auth
from backend.config import settings
from tests.app.controllers.submission_cases import SPEC
from tests.app.controllers.test_mcp_server import _call_tool
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import create_form
from tests.app.form_access.test_key_roles import (
    BASE,
    TOKENS,
    _auth,
    admin_creator,
    make_key,
    roles_off,  # noqa: F401
    roles_on,  # noqa: F401
)

pytestmark = pytest.mark.asyncio

REFUSED = "limited to certain forms"
CREATING_TOOLS = {
    "create_form": {"title": "A form"},
    "create_form_with_ai": {"prompt": "A short event sign-up form"},
    "create_form_outline": {"prompt": "A short event sign-up form"},
    "build_form_from_outline": {"outline": {"title": "A form", "pages": []}},
}


async def listed_key(workspace, forms=(), **kw):
    admin = await admin_creator(workspace)
    return await make_key(
        workspace,
        admin,
        scopes=("forms:read", "forms:write"),
        form_scope="listed",
        forms=[str(f.form_id) for f in forms],
        **kw,
    )


async def form_count(workspace) -> int:
    return len(await container.workspace_form_repo().list_in_workspace(workspace.id))


def token(key) -> str:
    return TOKENS[str(key.id)]


async def audit_of(workspace, tool):
    return [
        log
        for log in await container.mcp_audit_log_repo().list_by_workspace(workspace.id)
        if log.tool == tool
    ]


# =========================================================================== public API
@pytest.mark.parametrize("switch", ["on", "off"])
async def test_a_listed_key_cannot_create_a_form_through_the_public_api(
    client: AsyncClient, workspace, request, switch
):
    # a stored limit is enforced with the switch on or off
    request.getfixturevalue("roles_on" if switch == "on" else "roles_off")
    form = await create_form(workspace, testUser)
    key = await listed_key(workspace, [form])
    before = await form_count(workspace)
    refused = await client.post(f"{BASE}/forms", json=SPEC, headers=_auth(key))
    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "key_form_scope"
    assert REFUSED in refused.json()["message"]
    assert await form_count(workspace) == before
    # the validate endpoint (no form data) and the key's own list stay open
    assert (await client.post(f"{BASE}/forms/validate", json=SPEC, headers=_auth(key))).status_code == 200
    assert (await client.get(f"{BASE}/forms", headers=_auth(key))).status_code == 200


async def test_the_refusal_comes_before_any_budget_is_spent(
    client: AsyncClient, workspace, roles_on, monkeypatch
):
    key = await listed_key(workspace)
    spent = []

    async def record(*args, **kwargs):
        spent.append(args)

    monkeypatch.setattr(public_auth, "_hit", record)
    refused = await client.post(f"{BASE}/forms", json=SPEC, headers=_auth(key))
    assert refused.status_code == 403 and refused.json()["code"] == "key_form_scope"
    assert spent == []


async def test_a_listed_key_without_the_scope_is_told_the_scope_first(
    client: AsyncClient, workspace, roles_on
):
    admin = await admin_creator(workspace)
    key = await make_key(
        workspace, admin, scopes=("forms:read",), form_scope="listed"
    )
    refused = await client.post(f"{BASE}/forms", json=SPEC, headers=_auth(key))
    assert refused.status_code == 403 and refused.json()["code"] == "missing_scope"


async def test_keys_that_are_not_limited_to_forms_still_create_forms(
    client: AsyncClient, workspace, roles_on
):
    plain = await make_key(workspace, testUser)
    editor = await make_key(
        workspace, await admin_creator(workspace), role="EDITOR", scopes=("forms:read", "forms:write")
    )
    for key in (plain, editor):
        made = await client.post(f"{BASE}/forms", json=SPEC, headers=_auth(key))
        assert made.status_code == 201, made.text


# =========================================================================== MCP
@pytest.mark.parametrize("tool", sorted(CREATING_TOOLS))
@pytest.mark.parametrize("switch", ["on", "off"])
async def test_a_listed_key_cannot_create_a_form_through_mcp(
    client: AsyncClient, workspace, request, tool, switch
):
    request.getfixturevalue("roles_on" if switch == "on" else "roles_off")
    form = await create_form(workspace, testUser)
    key = await listed_key(workspace, [form])
    before = await form_count(workspace)
    result = await _call_tool(client, token(key), tool, CREATING_TOOLS[tool])
    assert result.get("isError") is True, result
    assert REFUSED in result["content"][0]["text"]
    assert await form_count(workspace) == before
    # the refusal is audited against the key under the tool's name
    logs = await audit_of(workspace, tool)
    assert [(log.ok, str(log.key_id)) for log in logs] == [(False, str(key.id))]


async def test_a_listed_key_keeps_the_tools_that_name_no_form(
    client: AsyncClient, workspace, roles_on
):
    form = await create_form(workspace, testUser)
    key = await listed_key(workspace, [form])
    profile = await _call_tool(client, token(key), "get_ai_profile", {})
    assert not profile.get("isError"), profile
    listing = await _call_tool(client, token(key), "list_forms", {})
    assert not listing.get("isError"), listing
    assert str(form.form_id) in listing["content"][0]["text"]


async def test_a_key_that_is_not_limited_to_forms_still_creates_through_mcp(
    client: AsyncClient, workspace, roles_on
):
    plain = await make_key(workspace, testUser)
    before = await form_count(workspace)
    made = await _call_tool(client, token(plain), "create_form", {"title": "Plain"})
    assert not made.get("isError"), made
    assert await form_count(workspace) == before + 1


# =========================================================================== MCP rate limit
def _limits(monkeypatch, per_key, per_workspace, window=3600):
    api = settings.api_settings
    monkeypatch.setattr(api, "PUBLIC_API_REQUESTS_PER_WINDOW", per_key)
    monkeypatch.setattr(api, "PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW", per_workspace)
    monkeypatch.setattr(api, "PUBLIC_API_WINDOW_SECONDS", window)


async def tool_keys(workspace, count):
    return [
        await make_key(workspace, testUser, scopes=("forms:read",)) for _ in range(count)
    ]


async def test_mcp_calls_are_limited_per_key(
    client: AsyncClient, workspace, monkeypatch
):
    _limits(monkeypatch, 2, 100)
    one, other = await tool_keys(workspace, 2)
    for _ in range(2):
        assert not (await _call_tool(client, token(one), "list_forms", {})).get("isError")
    limited = await _call_tool(client, token(one), "list_forms", {})
    assert limited.get("isError") is True
    text = limited["content"][0]["text"]
    assert "Too many requests with this API key" in text and "Retry after" in text
    # counted per key
    assert not (await _call_tool(client, token(other), "list_forms", {})).get("isError")
    # and apart from the REST API's budget: the same key still reads there
    assert (await client.get(f"{BASE}/forms", headers=_auth(one))).status_code == 200


async def test_mcp_calls_have_a_ceiling_for_all_of_a_workspaces_keys(
    client: AsyncClient, workspace, monkeypatch
):
    _limits(monkeypatch, 100, 3)
    keys = await tool_keys(workspace, 4)
    for key in keys[:3]:
        assert not (await _call_tool(client, token(key), "list_forms", {})).get("isError")
    limited = await _call_tool(client, token(keys[3]), "list_forms", {})
    assert limited.get("isError") is True
    assert "workspace" in limited["content"][0]["text"]


async def test_mcp_zero_turns_the_limit_off(
    client: AsyncClient, workspace, monkeypatch
):
    _limits(monkeypatch, 0, 0)
    (key,) = await tool_keys(workspace, 1)
    for _ in range(4):
        assert not (await _call_tool(client, token(key), "list_forms", {})).get("isError")


async def test_the_rest_apis_budget_does_not_use_up_mcps(
    client: AsyncClient, workspace, monkeypatch
):
    _limits(monkeypatch, 2, 100)
    (key,) = await tool_keys(workspace, 1)
    for _ in range(2):
        assert (await client.get(f"{BASE}/forms", headers=_auth(key))).status_code == 200
    assert (await client.get(f"{BASE}/forms", headers=_auth(key))).status_code == 429
    assert not (await _call_tool(client, token(key), "list_forms", {})).get("isError")


async def test_a_rate_limited_call_does_nothing(
    client: AsyncClient, workspace, roles_on, monkeypatch
):
    """Over the budget a creating tool is refused before it makes anything."""
    _limits(monkeypatch, 1, 100)
    key = await make_key(workspace, testUser, scopes=("forms:read", "forms:write"))
    assert not (await _call_tool(client, token(key), "get_ai_profile", {})).get("isError")
    before = await form_count(workspace)
    limited = await _call_tool(client, token(key), "create_form", {"title": "Over"})
    assert limited.get("isError") is True
    assert "Too many requests" in limited["content"][0]["text"]
    assert await form_count(workspace) == before
    assert "Over" not in limited["content"][0]["text"]
