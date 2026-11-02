"""The route matrix of form-level access for API keys: the public REST API and
the MCP server, each driven by its own registry (the public router's route table,
the MCP server's tool list), so a new route or tool that is not classified here
fails, naming it.

A key acts as the person who made it. Each classified call is made with the key
of every kind of member, against a form in each access mode, with the switch on
and off; the expectations are written from the access model, not read from the
services:

* a key whose creator lacks, in their role, a permission the call's scope stands
  for: 403 (the creator no longer has it), whatever the form;
* a key of a member the form is closed to: the status and the body of a form that
  is not there, byte for byte;
* a key of a grantee: what the grant gives, a 403 for the rest;
* a key of an Owner or an Admin: every form.
"""

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional, Tuple

import pytest
from common.ids import RecordId
from fastapi.routing import iter_route_contexts
from httpx import AsyncClient

from backend.app.mcp.server import mcp
from backend.app.models.enum.permission import Permission
from backend.app.public_api.routes import router as public_router
from backend.app.services.form_access.model import MODE_RESTRICTED, MODE_WORKSPACE
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.controllers.submission_cases import SPEC
from tests.app.controllers.test_mcp_server import _call_tool
from tests.app.form_access.helpers import add_member, grant, set_mode, team_with
from tests.app.form_access.test_key_enforcement import (
    OPS,
    _call,
    _published_form,
    _routes,
    _set_roles,
    _token,
)
from tests.app.form_access.test_route_matrix import (
    ADMIN,
    EDITOR,
    NON_CREATORS,
    OWNER,
    PRINCIPALS,
    PRIVACY,
    REVIEWER,
    VIEWER,
    Principal,
    base_permissions,
    closed_to,
    held_on_form,
)

P = Permission

# the scopes, and the permissions the key's creator must hold for each (doc, the
# API keys section: a key never does more than the person who made it may)
SCOPES: Dict[str, Tuple[Permission, ...]] = {
    "forms:read": (P.FORM_READ,),
    "forms:write": (P.FORM_EDIT,),
    "forms:delete": (P.FORM_DELETE,),
    # a bulk read of answers is an export
    "responses:read": (P.RESPONSE_READ, P.RESPONSE_EXPORT),
    "deletion_requests:read": (P.PRIVACY_MANAGE,),
    "deletion_requests:write": (P.PRIVACY_MANAGE,),
    # a write key: its creator must still be able to edit forms
    "submissions:write": (P.FORM_EDIT,),
}

STORED_ROLE = {
    OWNER: None,  # the billing owner (the matrix's owner)
    ADMIN: "ADMIN",
    EDITOR: "COLLABORATOR",
    REVIEWER: "REVIEWER",
    VIEWER: "VIEWER",
    PRIVACY: "PRIVACY_OFFICER",
}
CREATOR_LACKS = "key_creator_lacks_permission"


def decide_key(principal: Principal, scope: str, mode: str, switch_on: bool):
    """What a call with ``scope`` on the form answers for a key made by
    ``principal``: the creator's workspace-level permissions first (every one of
    the scope's: 403), then the form (404 closed, 403 lacking), as the key
    checks run."""
    chain = SCOPES[scope]
    base = base_permissions(principal)
    if any(p not in base for p in chain):
        return 403
    if closed_to(principal, mode, switch_on):
        return 404
    held = held_on_form(principal, mode, switch_on)
    if any(p not in held for p in chain):
        return 403
    return "allowed"


# -- the public API ---------------------------------------------------------------------


@dataclass(frozen=True)
class PublicRoute:
    name: Optional[str]  # the call in test_key_enforcement._routes (None: no form)
    scope: str
    kind: str = "form"  # form | list | none
    destructive: bool = False
    # the call is on a response the principal's key did not make, so an allowed
    # key is answered with the response's own 404: only refusals are asserted
    soft: bool = False
    # the statuses a key let through is answered with, and a check of its data
    # (``check(world, response)`` is true when the data is right)
    ok: Tuple[int, ...] = ()
    check: Optional[Callable] = None


PUBLIC_ROUTES: Dict[Tuple[str, str], PublicRoute] = {
    ("GET", "/forms"): PublicRoute(None, "forms:read", "list"),
    ("POST", "/forms"): PublicRoute(None, "forms:write", "none"),
    ("POST", "/forms/validate"): PublicRoute(None, "forms:read", "none"),
    ("GET", "/forms/{form_id}"): PublicRoute(
        "getForm",
        "forms:read",
        ok=(200,),
        check=lambda w, r: r.json().get("specVersion") == "1" and bool(r.json().get("pages")),
    ),
    ("PUT", "/forms/{form_id}"): PublicRoute("replaceForm", "forms:write", ok=(412, 428)),
    ("POST", "/forms/{form_id}/replace/dry-run"): PublicRoute(
        "previewReplaceForm", "forms:write", ok=(200,)
    ),
    ("POST", "/forms/{form_id}/publish"): PublicRoute("publishForm", "forms:write", ok=(200,)),
    ("DELETE", "/forms/{form_id}"): PublicRoute(
        "deleteForm", "forms:delete", destructive=True, ok=(204,)
    ),
    ("POST", "/forms/{form_id}/ops"): PublicRoute("applyFormOps", "forms:write", ok=(200,)),
    ("POST", "/forms/{form_id}/ops/dry-run"): PublicRoute(
        "dryRunFormOps", "forms:write", ok=(200,)
    ),
    ("GET", "/forms/{form_id}/responses"): PublicRoute(
        "listResponses",
        "responses:read",
        ok=(200,),
        check=lambda w, r: w.response_id in r.text,
    ),
    ("GET", "/forms/{form_id}/responses/{response_id}"): PublicRoute(
        "getResponse",
        "responses:read",
        ok=(200,),
        check=lambda w, r: w.response_id in r.text,
    ),
    ("POST", "/forms/{form_id}/responses/{response_id}/deletion-request/close"): PublicRoute(
        "closeDeletionRequest", "deletion_requests:write", ok=(200, 409)
    ),
    ("POST", "/forms/{form_id}/submissions"): PublicRoute(
        "createSubmission",
        "submissions:write",
        ok=(201,),
        check=lambda w, r: bool(r.json()["responseId"]),
    ),
    ("PATCH", "/forms/{form_id}/submissions/{response_id}"): PublicRoute(
        "updateSubmission", "submissions:write", soft=True
    ),
}


def public_routes() -> set:
    found = set()
    for context in iter_route_contexts(public_router.routes):
        for method in context.methods or ():
            if method not in ("HEAD", "OPTIONS") and context.path:
                found.add((method, context.path))
    return found


def test_every_public_api_route_is_classified():
    live = public_routes()
    assert len(live) >= 14, live
    missing = sorted(live - set(PUBLIC_ROUTES))
    assert not missing, (
        "public API routes missing from PUBLIC_ROUTES (classify each with the "
        "scope it needs):\n" + "\n".join(f"  {m} {p}" for m, p in missing)
    )
    gone = sorted(set(PUBLIC_ROUTES) - live)
    assert not gone, f"classified public API routes that no longer exist: {gone}"
    for (method, path), route in PUBLIC_ROUTES.items():
        assert route.scope in SCOPES, (method, path)
        if "{form_id}" in path:
            assert route.kind == "form" and route.name, (method, path)


# -- the MCP server ---------------------------------------------------------------------


@dataclass(frozen=True)
class Tool:
    kind: str  # form | response | list | none
    scope: Optional[str] = None


MCP_TOOLS: Dict[str, Tool] = {
    "list_forms": Tool("list", "forms:read"),
    "get_form": Tool("form", "forms:read"),
    "get_form_spec": Tool("form", "forms:read"),
    "update_form": Tool("form", "forms:write"),
    "dry_run_ops": Tool("form", "forms:write"),
    "publish_form": Tool("form", "forms:write"),
    "list_responses": Tool("form", "responses:read"),
    "get_response": Tool("response", "responses:read"),
    "list_deletion_requests": Tool("list", "deletion_requests:read"),
    # workspace level: no form exists yet, or nothing is read of one
    "create_form": Tool("none"),
    "create_form_with_ai": Tool("none"),
    "create_form_outline": Tool("none"),
    "build_form_from_outline": Tool("none"),
    "validate_form": Tool("none"),
    "get_ai_profile": Tool("none"),
}


def mcp_arguments(tool: str, form_id: str, response_id: str) -> dict:
    return {
        "get_form": {"form_id": form_id},
        "get_form_spec": {"form_id": form_id},
        "update_form": {"form_id": form_id, "ops": OPS["ops"]},
        "dry_run_ops": {"form_id": form_id, "ops": OPS["ops"]},
        "publish_form": {"form_id": form_id},
        "list_responses": {"form_id": form_id},
        "get_response": {"response_id": response_id},
    }[tool]


async def test_every_mcp_tool_is_classified():
    """The tools come from the server's own registry; one that names a form or a
    response is decided on it, so it cannot be classified as workspace-level."""
    registered = {tool.name: tool for tool in await mcp.list_tools()}
    assert len(registered) >= 14, sorted(registered)
    missing = sorted(set(registered) - set(MCP_TOOLS))
    assert not missing, (
        "MCP tools missing from MCP_TOOLS (classify each: the scope it needs and "
        "whether it names a form or a response):\n" + "\n".join(f"  {n}" for n in missing)
    )
    gone = sorted(set(MCP_TOOLS) - set(registered))
    assert not gone, f"classified MCP tools that no longer exist: {gone}"
    for name, tool in registered.items():
        properties = set((tool.input_schema or {}).get("properties", {}))
        entry = MCP_TOOLS[name]
        if "form_id" in properties:
            assert entry.kind == "form", f"{name} takes a form_id"
        if "response_id" in properties:
            assert entry.kind == "response", f"{name} takes a response_id"
        if entry.kind != "none":
            assert entry.scope in SCOPES, name


# -- the world ---------------------------------------------------------------------------


@pytest.fixture()
async def kworld(client: AsyncClient, workspace, monkeypatch):
    """One published form with an answer that has a deletion request, and an API
    key (every scope) of each kind of member: made while an Admin, then given the
    member's role and grant, as a creator who was demoted since."""
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    owner_token = await _token(workspace, testUser)
    form_id, response_id = await _published_form(client, owner_token, SPEC, "Key matrix form")
    tokens = {"owner": owner_token}
    for name in NON_CREATORS:
        if name == "owner":
            continue
        principal = PRINCIPALS[name]
        user = await add_member(workspace, "ADMIN")
        tokens[name] = await _token(workspace, user)
        await _set_roles(workspace, user, STORED_ROLE[principal.role])
        if principal.grant and principal.team:
            team = await team_with(workspace, user)
            await grant(
                workspace, form_id, team.id, principal.grant,
                export=principal.export, subject_type="group",
            )
        elif principal.grant:
            await grant(
                workspace, form_id, user.id, principal.grant, export=principal.export
            )
    return SimpleNamespace(
        workspace=workspace, form_id=form_id, response_id=response_id, tokens=tokens
    )


def _body(response):
    try:
        return response.json()
    except ValueError:
        return response.text


def _normal(text: str, *ids) -> str:
    for i in ids:
        text = text.replace(i, "<id>")
    return text


def public_request(name: str, form_id: str, response_id: str):
    for n, method, path, kw in _routes(form_id, response_id):
        if n == name:
            return method, path, kw
    raise KeyError(name)


async def run_public(client, kworld, names: List[str], mode: str, switch_on: bool):
    failures: List[str] = []
    unknown_form, unknown_response = str(RecordId()), str(RecordId())
    ordered = sorted(
        ((k, r) for k, r in PUBLIC_ROUTES.items() if r.name),
        key=lambda item: (item[1].destructive, item[0]),
    )
    for (method, template), route in ordered:
        taken = False
        order = sorted(
            names,
            key=lambda n: decide_key(PRINCIPALS[n], route.scope, mode, switch_on) == "allowed",
        )
        for name in order:
            principal = PRINCIPALS[name]
            want = decide_key(principal, route.scope, mode, switch_on)
            if route.destructive and want == "allowed":
                if taken:
                    continue
                taken = True
            label = f"{method} {template} as {name} [{mode}, switch {'on' if switch_on else 'off'}]"
            _, path, kw = public_request(route.name, kworld.form_id, kworld.response_id)
            got = await _call(client, kworld.tokens[name], method, path, **kw)
            seen = f"{label}: {got.status_code} {str(_body(got))[:110]}"
            if got.status_code >= 500 and got.status_code != 503:
                failures.append(f"server error: {seen}")
                continue
            lacks = got.status_code == 403 and isinstance(_body(got), dict) and (
                _body(got).get("code") == CREATOR_LACKS
            )
            if want == "allowed":
                if lacks:
                    failures.append(f"refused, expected to pass: {seen}")
                    continue
                if got.status_code == 404 and not route.soft:
                    _, gpath, gkw = public_request(route.name, unknown_form, unknown_response)
                    ghost = await _call(client, kworld.tokens[name], method, gpath, **gkw)
                    if (got.status_code, _body(got)) == (ghost.status_code, _body(ghost)):
                        failures.append(f"answered as an unknown form: {seen}")
                if route.ok and got.status_code not in route.ok:
                    failures.append(f"outcome {got.status_code} not in {route.ok}: {seen}")
                if route.check is not None and 200 <= got.status_code < 300:
                    if not route.check(kworld, got):
                        failures.append(f"the data is not what the call returns: {seen}")
            elif want == 403:
                if not lacks:
                    failures.append(f"expected 403 {CREATOR_LACKS}, got: {seen}")
            else:
                _, gpath, gkw = public_request(route.name, unknown_form, unknown_response)
                ghost = await _call(client, kworld.tokens[name], method, gpath, **gkw)
                if got.status_code != 404 or (got.status_code, _body(got)) != (
                    ghost.status_code,
                    _body(ghost),
                ):
                    failures.append(
                        f"expected the answer of an unknown form "
                        f"({ghost.status_code} {str(_body(ghost))[:60]}): {seen}"
                    )
    return failures


async def run_lists(client, kworld, names: List[str], mode: str, switch_on: bool):
    """The key lists: a form the key's creator may not open is not in them."""
    failures: List[str] = []
    for name in names:
        principal = PRINCIPALS[name]
        want = decide_key(principal, "forms:read", mode, switch_on)
        listed = await _call(client, kworld.tokens[name], "GET", "/forms")
        if want == 403:
            if listed.status_code != 403:
                failures.append(f"GET /forms as {name}: expected 403, got {listed.status_code}")
            continue
        if listed.status_code != 200:
            failures.append(f"GET /forms as {name}: {listed.status_code}")
            continue
        body = listed.json()
        ids = {item["formId"] for item in body["items"]}
        sees = want == "allowed"
        if (kworld.form_id in ids) is not sees:
            failures.append(
                f"GET /forms as {name} [{mode}]: the form is "
                f"{'missing' if sees else 'listed'}"
            )
        if body["total"] != len(ids):
            failures.append(f"GET /forms as {name}: total {body['total']} != {len(ids)}")
    return failures


MCP_ERROR = "isError"


async def _mcp_list(client, kworld, tool, entry, names, mode, switch_on) -> List[str]:
    """The MCP list tools: the form (or the form's deletion request) is in the
    list exactly when the key's creator holds the tool's scope permissions on it;
    a creator whose role lacks them gets the 403 text."""
    failures: List[str] = []
    for name in names:
        want = decide_key(PRINCIPALS[name], entry.scope, mode, switch_on)
        got = await _call_tool(client, kworld.tokens[name], tool, {})
        text = got["content"][0]["text"] if got.get("content") else ""
        label = f"mcp {tool} as {name} [{mode}, switch {'on' if switch_on else 'off'}]"
        if want == 403:
            if not got.get(MCP_ERROR):
                failures.append(f"expected the 403 text: {label}")
            continue
        if got.get(MCP_ERROR):
            failures.append(f"a list is refused: {label}: {text[:100]}")
            continue
        items = json.loads(text)
        ids = {str(i.get("formId")) for i in items}
        sees = want == "allowed"
        if (kworld.form_id in ids) is not sees:
            failures.append(
                f"{label}: the form is {'missing from' if sees else 'in'} the list"
            )
        if tool == "list_deletion_requests":
            responses = {str(i.get("responseId")) for i in items}
            if (kworld.response_id in responses) is not sees:
                failures.append(f"{label}: the deletion request is wrongly "
                                f"{'missing' if sees else 'listed'}")
    return failures


async def run_mcp(client, kworld, names: List[str], mode: str, switch_on: bool):
    failures: List[str] = []
    unknown_form, unknown_response = str(RecordId()), str(RecordId())
    for tool, entry in MCP_TOOLS.items():
        if entry.kind == "list":
            failures += await _mcp_list(client, kworld, tool, entry, names, mode, switch_on)
            continue
        if entry.kind not in ("form", "response"):
            continue
        for name in names:
            principal = PRINCIPALS[name]
            want = decide_key(principal, entry.scope, mode, switch_on)
            if (
                entry.kind == "response"
                and want == 403
                and all(p in base_permissions(principal) for p in SCOPES[entry.scope])
            ):
                # a response is named by its id alone: one its key may open but
                # not use for this is "not found" too (it confirms nothing)
                want = 404
            args = mcp_arguments(tool, kworld.form_id, kworld.response_id)
            got = await _call_tool(client, kworld.tokens[name], tool, args)
            text = got["content"][0]["text"] if got.get("content") else ""
            label = f"mcp {tool} as {name} [{mode}, switch {'on' if switch_on else 'off'}]"
            if want == "allowed":
                if got.get(MCP_ERROR):
                    failures.append(f"refused, expected to pass: {label}: {text[:100]}")
                else:
                    # the data: the form, or the response, the tool is about
                    needle = {
                        "get_form": kworld.form_id,
                        "list_responses": kworld.response_id,
                        "get_response": kworld.response_id,
                    }.get(tool)
                    if needle and needle not in text:
                        failures.append(f"the data lacks {needle}: {label}")
            elif want == 403:
                if not got.get(MCP_ERROR) or "no longer has" not in text and "does not have" not in text:
                    failures.append(f"expected the 403 text: {label}: {text[:100]}")
            else:
                ghost = await _call_tool(
                    client,
                    kworld.tokens[name],
                    tool,
                    mcp_arguments(tool, unknown_form, unknown_response),
                )
                gtext = ghost["content"][0]["text"] if ghost.get("content") else ""
                same = _normal(text, kworld.form_id, kworld.response_id) == _normal(
                    gtext, unknown_form, unknown_response
                )
                if not got.get(MCP_ERROR) or not same:
                    failures.append(
                        f"expected the text of an unknown form: {label}: {text[:100]!r} vs {gtext[:100]!r}"
                    )
    return failures


EVERY = NON_CREATORS  # (a creator's key is the creator's: covered on the REST routes)
OPEN_SET = [
    "admin",
    "editor",
    "viewer",
    "privacy",
    "viewer_editor_grant",
    "viewer_reviewer_grant",
    "viewer_team_grant",
    "viewer_export_grant",
]
OFF_SET = NON_CREATORS


async def _all(client, kworld, names, mode, switch_on):
    # the public API last: its DELETE removes the form the others read
    failures = await run_lists(client, kworld, names, mode, switch_on)
    failures += await run_mcp(client, kworld, names, mode, switch_on)
    failures += await run_public(client, kworld, names, mode, switch_on)
    return failures


def _report(failures):
    assert not failures, "\n".join(failures[:50]) + f"\n({len(failures)} in all)"


async def test_the_key_matrix_on_a_restricted_form(
    client: AsyncClient, kworld, monkeypatch
):
    await set_mode(kworld.workspace, kworld.form_id, MODE_RESTRICTED)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    _report(await _all(client, kworld, EVERY, MODE_RESTRICTED, True))


async def test_the_key_matrix_on_an_open_form(client: AsyncClient, kworld, monkeypatch):
    await set_mode(kworld.workspace, kworld.form_id, MODE_WORKSPACE)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    _report(await _all(client, kworld, OPEN_SET, MODE_WORKSPACE, True))


async def test_a_closed_form_is_a_missing_form_under_bad_input_for_every_form_route(
    client: AsyncClient, kworld, monkeypatch
):
    """The existence oracle: validation (a bad page, a bad body, a bad header)
    must not tell a closed form from a missing one, on any route of the public
    API (the budget is checked in the test below)."""
    await set_mode(kworld.workspace, kworld.form_id, MODE_RESTRICTED)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    token = kworld.tokens["editor"]
    unknown_form, unknown_response = str(RecordId()), str(RecordId())
    bad = {"content": b"{not json", "headers": {"Content-Type": "application/json"}}
    calls = [
        ("GET", "/forms/{f}/responses", {"params": {"page": 0}}),
        ("GET", "/forms/{f}/responses/{r}", {"params": {"x": "y"}}),
        ("POST", "/forms/{f}/submissions", bad),
        ("PATCH", "/forms/{f}/submissions/{r}", bad),
        ("POST", "/forms/{f}/ops", bad),
        ("POST", "/forms/{f}/ops/dry-run", bad),
        ("PUT", "/forms/{f}", {**bad, "headers": {"Content-Type": "application/json", "If-Match": "nope"}}),
        ("POST", "/forms/{f}/replace/dry-run", bad),
        ("POST", "/forms/{f}/responses/{r}/deletion-request/close", bad),
    ]
    for method, template, kw in calls:
        closed = await _call(
            client, token, method, template.format(f=kworld.form_id, r=kworld.response_id), **kw
        )
        missing = await _call(
            client, token, method, template.format(f=unknown_form, r=unknown_response), **kw
        )
        assert (closed.status_code, _body(closed)) == (
            missing.status_code,
            _body(missing),
        ), (method, template, closed.status_code, missing.status_code)


async def test_a_closed_or_missing_form_never_spends_the_forms_submission_budget(
    client: AsyncClient, kworld, monkeypatch
):
    """The order the submissions routes decide in: the form (404 for a closed or a
    missing one) comes before the form's budget, so a member's key cannot spend,
    or learn from, the budget of a form it cannot open. With the budget set to 2:
    six submissions with the closed-out Editor's key answer the 404 of an unknown
    form each time (never a 429), and the Admin's key, which may submit, still has
    its two."""
    import backend.app.public_api.auth as public_auth

    monkeypatch.setattr(public_auth, "SUBMISSIONS_PER_FORM_PER_WINDOW", 2)
    await set_mode(kworld.workspace, kworld.form_id, MODE_RESTRICTED)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    unknown = str(RecordId())
    body = {"json": {"answers": {}, "consent": True}}
    path = "/forms/{f}/submissions"

    async def allowed_before_429(token, form_id) -> int:
        for taken in range(5):
            got = await _call(client, token, "POST", path.format(f=form_id), **body)
            if got.status_code == 429:
                return taken
        return 5

    # the budget as the Admin's key meets it on a second form (a form that is not
    # there answers 404 before the budget, which is itself the point)
    other, _ = await _published_form(client, kworld.tokens["owner"], SPEC, "Budget control")
    allowance = await allowed_before_429(kworld.tokens["admin"], other)
    assert 1 <= allowance <= 3, allowance
    assert await allowed_before_429(kworld.tokens["admin"], unknown) == 5
    for _ in range(6):
        closed = await _call(
            client, kworld.tokens["editor"], "POST", path.format(f=kworld.form_id), **body
        )
        missing = await _call(
            client, kworld.tokens["editor"], "POST", path.format(f=unknown), **body
        )
        assert (closed.status_code, _body(closed)) == (missing.status_code, _body(missing))
        assert closed.status_code == 404, closed.status_code
    # the Editor's six calls spent none of the closed form's budget: the Admin
    # has all of it
    assert await allowed_before_429(kworld.tokens["admin"], kworld.form_id) == allowance


async def test_the_key_matrix_with_the_switch_off(client: AsyncClient, kworld, monkeypatch):
    """Off: a key reads and writes as its creator's workspace role allows, a
    restricted form and the grants stored on it notwithstanding."""
    await set_mode(kworld.workspace, kworld.form_id, MODE_RESTRICTED)
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    _report(await _all(client, kworld, OFF_SET, MODE_RESTRICTED, False))
