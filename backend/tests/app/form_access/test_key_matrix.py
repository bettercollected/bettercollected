"""The matrix of API key limits: every entry point a key can reach, run as every
shape of key, with the switches on and off.

The public API and the MCP server are mounted ASGI apps outside the root router,
so the route matrix of form-level access (``test_route_matrix.py``) does not see
them. This is its sibling. Its net is each surface's own registry, not a list kept
by hand: ``build_public_api().routes`` and the MCP server's tool list. Every route
and tool has a row in ``PUBLIC`` / ``MCP`` saying what it is (a call on a form, on
a response, a list, a creation, a pure check, ...) and the scope it needs; one
that has no row fails ``test_every_entry_point_is_classified``, naming it.

Each classified call is made with the key of each shape (as its creator; each role;
limited to a list of forms, the form on the list and one off it; a creator
demoted or disabled since; a revoked key), against the form on the list, a form
that exists and is not on it, and an id that is not a form, with
``API_KEY_ROLES_ENABLED`` and ``FORM_ACCESS_ENABLED`` each on and off. What it
answers is checked against an oracle written from the access model
(docs/enterprise-access-model.md and the design of key roles: the role table, the
role ceilings, the ceiling of a row), never read from the services:

* a key never does more than the person who made it does now (a demoted creator
  narrows it; its role and its list never repair that);
* a form off the key's list answers exactly as an id that is not a form (the same
  status and body), and so does a form closed to its creator;
* a key limited to a list of forms creates no form;
* a limit already stored is enforced with ``API_KEY_ROLES_ENABLED`` off too.

A hole found goes in as a test of its own marked ``xfail(strict=True)``.
Everything here is synthetic.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest
from common.ids import RecordId
from fastapi.routing import iter_route_contexts
from httpx import AsyncClient

from backend.app.container import container
from backend.app.mcp.server import mcp
from backend.app.public_api.app import build_public_api
from backend.app.schemas.form_access_grant import (
    ROLE_EDITOR,
    ROLE_REVIEWER,
    ROLE_VIEWER,
)
from backend.app.services.form_access.model import MODE_RESTRICTED
from backend.config import settings
from tests.app.ai_helpers import FakeProvider, OUTLINE, use_fake_provider
from tests.app.controllers.data import testUser
from tests.app.controllers.submission_cases import SPEC
from tests.app.controllers.test_mcp_server import MCP_HEADERS, MCP_URL, _call_tool
from tests.app.form_access.helpers import set_mode
from tests.app.form_access.test_key_enforcement import (
    ALL_SCOPES,
    OPS,
    _call,
    _published_form,
    _routes,
    _token,
)
from tests.app.form_access.test_key_roles import (
    TOKENS,
    admin_creator,
    make_key,
    set_roles,
)

BASE = "/api/v1/public/v1"

# -- what a call can answer --------------------------------------------------------------
PASSED = "passed"  # the key's gate let it through (what follows is the call's own)
NOTFOUND = "not found"  # "Form not found", the answer for a form that is not there
CREATOR = "creator lacks"  # 403 key_creator_lacks_permission
ROLE = "role lacks"  # 403 key_role_lacks_permission
CREATE_REFUSED = "creates no form"  # 403 key_form_scope
MISSING_SCOPE = "scope"  # 403 missing_scope
UNAUTH = "unauthorised"  # 401
RATE = "rate limited"
SERVER = "server error"


# =========================================================================== the table
@dataclass(frozen=True)
class Entry:
    """What a route or tool is, for the oracle.

    ``kind``: ``form_bound`` (names a form), ``response_bound`` (names a response:
    the form is found through it), ``list`` (a list of forms), ``create`` (makes a
    form), ``pure`` (checks a document, stores nothing), ``profile`` (the
    workspace's AI profile), ``privacy_queue`` (deletion requests across the
    workspace), ``document`` (the API's own OpenAPI document: no key)."""

    kind: str
    scope: Optional[str]
    destructive: bool = False


KINDS = {
    "form_bound",
    "response_bound",
    "list",
    "create",
    "pure",
    "profile",
    "privacy_queue",
    "document",
}

# (method, path) -> Entry: every route of the public API
PUBLIC: Dict[Tuple[str, str], Entry] = {
    ("GET", "/openapi.json"): Entry("document", None),
    ("GET", "/forms"): Entry("list", "forms:read"),
    ("POST", "/forms"): Entry("create", "forms:write"),
    ("POST", "/forms/validate"): Entry("pure", "forms:read"),
    ("GET", "/forms/{form_id}"): Entry("form_bound", "forms:read"),
    ("PUT", "/forms/{form_id}"): Entry("form_bound", "forms:write"),
    ("POST", "/forms/{form_id}/replace/dry-run"): Entry("form_bound", "forms:write"),
    ("POST", "/forms/{form_id}/publish"): Entry("form_bound", "forms:write"),
    ("DELETE", "/forms/{form_id}"): Entry("form_bound", "forms:delete", True),
    ("POST", "/forms/{form_id}/ops"): Entry("form_bound", "forms:write"),
    ("POST", "/forms/{form_id}/ops/dry-run"): Entry("form_bound", "forms:write"),
    ("GET", "/forms/{form_id}/responses"): Entry("form_bound", "responses:read"),
    ("GET", "/forms/{form_id}/responses/{response_id}"): Entry(
        "response_bound", "responses:read"
    ),
    ("POST", "/forms/{form_id}/responses/{response_id}/deletion-request/close"): Entry(
        "response_bound", "deletion_requests:write", True
    ),
    ("POST", "/forms/{form_id}/submissions"): Entry("form_bound", "submissions:write"),
    ("PATCH", "/forms/{form_id}/submissions/{response_id}"): Entry(
        "response_bound", "submissions:write"
    ),
}

# tool name -> Entry: every tool of the MCP server
MCP: Dict[str, Entry] = {
    "list_forms": Entry("list", "forms:read"),
    "get_form": Entry("form_bound", "forms:read"),
    "create_form": Entry("create", "forms:write"),
    "create_form_with_ai": Entry("create", "forms:write"),
    "create_form_outline": Entry("create", "forms:write"),
    "build_form_from_outline": Entry("create", "forms:write"),
    "update_form": Entry("form_bound", "forms:write"),
    "get_form_spec": Entry("form_bound", "forms:read"),
    "validate_form": Entry("pure", "forms:read"),
    "dry_run_ops": Entry("form_bound", "forms:write"),
    "publish_form": Entry("form_bound", "forms:write"),
    "list_responses": Entry("form_bound", "responses:read"),
    "get_response": Entry("response_bound", "responses:read"),
    "list_deletion_requests": Entry("privacy_queue", "deletion_requests:read"),
    "get_ai_profile": Entry("profile", "forms:read"),
}

# how each public call that names a form is made (test_key_enforcement._routes)
PUBLIC_CALL = {
    ("GET", "/forms/{form_id}"): "getForm",
    ("PUT", "/forms/{form_id}"): "replaceForm",
    ("POST", "/forms/{form_id}/replace/dry-run"): "previewReplaceForm",
    ("POST", "/forms/{form_id}/publish"): "publishForm",
    ("DELETE", "/forms/{form_id}"): "deleteForm",
    ("POST", "/forms/{form_id}/ops"): "applyFormOps",
    ("POST", "/forms/{form_id}/ops/dry-run"): "dryRunFormOps",
    ("GET", "/forms/{form_id}/responses"): "listResponses",
    ("GET", "/forms/{form_id}/responses/{response_id}"): "getResponse",
    (
        "POST",
        "/forms/{form_id}/responses/{response_id}/deletion-request/close",
    ): "closeDeletionRequest",
    ("POST", "/forms/{form_id}/submissions"): "createSubmission",
    ("PATCH", "/forms/{form_id}/submissions/{response_id}"): "updateSubmission",
}


def mcp_arguments(tool: str, form_id: str, response_id: str) -> dict:
    return {
        "list_forms": {},
        "get_form": {"form_id": form_id},
        "create_form": {"title": "Matrix form"},
        "create_form_with_ai": {"prompt": "A short event sign-up form"},
        "create_form_outline": {"prompt": "A short event sign-up form"},
        "build_form_from_outline": {"outline": OUTLINE, "fill_gaps": False},
        "update_form": {"form_id": form_id, "ops": OPS["ops"]},
        "get_form_spec": {"form_id": form_id},
        "validate_form": {"spec": SPEC},
        "dry_run_ops": {"form_id": form_id, "ops": OPS["ops"]},
        "publish_form": {"form_id": form_id},
        "list_responses": {"form_id": form_id},
        "get_response": {"response_id": response_id},
        "list_deletion_requests": {},
        "get_ai_profile": {},
    }[tool]


def public_routes_found() -> set:
    found = set()
    for context in iter_route_contexts(build_public_api().routes):
        for method in context.methods or ():
            if method not in ("HEAD", "OPTIONS") and context.path:
                found.add((method, context.path))
    return found


# a tool's own name for the entries of both surfaces, in messages
def label(surface: str, key) -> str:
    return f"mcp {key}" if surface == "mcp" else f"{key[0]} {key[1]}"


async def test_every_entry_point_is_classified():
    """The registries are the surfaces' own: a route or a tool nobody classified
    fails here, by name, so a new entry point cannot ship unnoticed."""
    live = public_routes_found()
    assert len(live) >= 15, live
    missing = sorted(live - set(PUBLIC))
    assert not missing, (
        "public API routes with no row in PUBLIC (say what each is and the scope "
        "it needs, then make it go through api_access):\n"
        + "\n".join(f"  {m} {p}" for m, p in missing)
    )
    assert not sorted(set(PUBLIC) - live), "classified routes that no longer exist"

    tools = {tool.name: tool for tool in await mcp.list_tools()}
    assert len(tools) >= 15, sorted(tools)
    missing_tools = sorted(set(tools) - set(MCP))
    assert not missing_tools, (
        "MCP tools with no row in MCP (say what each is and the scope it needs, "
        "then make it go through api_access):\n"
        + "\n".join(f"  {n}" for n in missing_tools)
    )
    assert not sorted(set(MCP) - set(tools)), "classified tools that no longer exist"
    # the contract snapshot names the same tools (a tool is never silently added)
    snapshot = json.loads(
        (Path(__file__).parents[2] / "fixtures" / "mcp" / "tools_list.json").read_text()
    )
    assert {t["name"] for t in snapshot["tools"]} == set(MCP)
    # resources and prompts are entry points too: there are none, and one added
    # has to be classified (and gated) before it can ship
    assert await mcp.list_resources() == []
    assert await mcp.list_resource_templates() == []
    assert await mcp.list_prompts() == []


def test_the_classification_agrees_with_what_each_entry_names():
    for (method, path), entry in PUBLIC.items():
        assert entry.kind in KINDS, (method, path)
        names_form = "{form_id}" in path
        assert names_form == (entry.kind in ("form_bound", "response_bound")), (
            method,
            path,
        )
        assert ("{response_id}" in path) == (entry.kind == "response_bound"), (
            method,
            path,
        )
        assert (entry.scope is None) == (entry.kind == "document"), (method, path)
        assert (method, path) in PUBLIC_CALL or not names_form, (method, path)
    for name, entry in MCP.items():
        assert entry.kind in KINDS and entry.kind != "document", name
        assert entry.scope, name


async def test_a_tool_that_names_a_form_or_a_response_is_not_classified_as_neutral():
    """The kind is checked against the tool's own input schema, so a tool that
    takes a ``form_id`` cannot be filed as a creation or a pure check."""
    for tool in await mcp.list_tools():
        properties = set((tool.input_schema or {}).get("properties", {}))
        kind = MCP[tool.name].kind
        if "form_id" in properties:
            assert kind == "form_bound", tool.name
        if "response_id" in properties:
            assert kind == "response_bound", tool.name
        if kind in ("form_bound", "response_bound"):
            assert properties & {"form_id", "response_id"}, tool.name


# =========================================================================== the oracle
# What each role can carry, from the role table (docs/enterprise-access-model.md
# section 2), as the scopes of the API: forms:read = form.read, forms:write and
# submissions:write = form.edit, forms:delete = form.delete, responses:read =
# response.read + response.export, deletion_requests:* = privacy.manage.
EVERY = frozenset(ALL_SCOPES)
CREATOR_SCOPES = {
    "admin": EVERY,
    "editor": frozenset(
        {"forms:read", "forms:write", "forms:delete", "responses:read", "submissions:write"}
    ),
    # a Viewer reads forms and answers but exports nothing
    "viewer": frozenset({"forms:read"}),
    "disabled": frozenset(),
}
# the ceiling of a key's role (the role's own table, and, for a Reviewer or a
# Viewer, the export of responses:read: the admin acknowledged what it hands out)
ROLE_SCOPES = {
    None: EVERY,
    "EDITOR": CREATOR_SCOPES["editor"],
    "REVIEWER": frozenset({"forms:read", "responses:read"}),
    "VIEWER": frozenset({"forms:read", "responses:read"}),
    "PRIVACY_OFFICER": frozenset(
        {"forms:read", "deletion_requests:read", "deletion_requests:write"}
    ),
}
# the role of the row a listed key holds for a form, by the key's role (a grant
# never carries the privacy programme, so a Privacy officer's row reads)
ROW_ROLE = {
    None: ROLE_EDITOR,
    "EDITOR": ROLE_EDITOR,
    "REVIEWER": ROLE_REVIEWER,
    "VIEWER": ROLE_VIEWER,
    "PRIVACY_OFFICER": ROLE_VIEWER,
}
# what a row allows: an Editor grant edits and reads and exports answers, never
# deletes the form; a Reviewer or Viewer grant reads (export by the key's scope)
ROW_SCOPES = {
    ROLE_EDITOR: frozenset({"forms:read", "forms:write", "responses:read", "submissions:write"}),
    ROLE_REVIEWER: frozenset({"forms:read", "responses:read"}),
    ROLE_VIEWER: frozenset({"forms:read", "responses:read"}),
}
LISTED_NEVER = frozenset({"forms:delete", "deletion_requests:read", "deletion_requests:write"})


@dataclass(frozen=True)
class Shape:
    """A key and who made it. ``creator`` is what its creator is now (an Admin
    when the key was made; ``viewer``, ``editor`` and ``disabled`` mean demoted or
    disabled since). ``listed``: limited to a list of forms; ``in_list``: the list
    names the form the matrix calls "in"; ``restrict_in``: that form is restricted
    (closed to an Editor with no grant)."""

    name: str
    creator: str = "admin"
    role: Optional[str] = None
    listed: bool = False
    in_list: bool = True
    restrict_in: bool = False


SHAPES = [
    Shape("as_creator"),
    Shape("editor_role", role="EDITOR"),
    Shape("reviewer_role", role="REVIEWER"),
    Shape("viewer_role", role="VIEWER"),
    Shape("privacy_officer_role", role="PRIVACY_OFFICER"),
    Shape("listed", listed=True),
    Shape("listed_editor_role", role="EDITOR", listed=True),
    Shape("listed_reviewer_role", role="REVIEWER", listed=True),
    Shape("listed_viewer_role", role="VIEWER", listed=True),
    Shape("listed_privacy_officer_role", role="PRIVACY_OFFICER", listed=True),
    Shape("listed_empty", listed=True, in_list=False),
    Shape("creator_demoted_to_viewer", creator="viewer"),
    Shape("creator_demoted_to_viewer_editor_role", creator="viewer", role="EDITOR"),
    Shape("creator_demoted_to_viewer_listed", creator="viewer", listed=True),
    Shape("creator_demoted_to_editor_restricted_form", creator="editor", restrict_in=True),
    Shape(
        "creator_demoted_to_editor_listed_restricted_form",
        creator="editor",
        listed=True,
        restrict_in=True,
    ),
    Shape("creator_disabled", creator="disabled"),
    Shape("creator_disabled_listed", creator="disabled", listed=True),
]


def expected(
    shape: Shape, entry: Entry, target: str, access_on: bool, surface: str
) -> str:
    """What the key's gate answers (``PASSED``: it lets the call through) for
    ``entry`` against ``target`` (``in``: the form on the key's list, ``out``: a
    form that exists and is not on it, ``unknown``: an id that is not a form).
    Written from the model, in the order the gates run: the key's scope, then
    what its creator holds in the workspace, then what its role allows, then the
    form."""
    scope, kind = entry.scope, entry.kind
    if kind == "create" and shape.listed and surface == "public":
        # the public API refuses a listed key's creation right after the scope
        # check, before anything about its creator is read (the MCP server asks
        # the creator's permissions first)
        return CREATE_REFUSED
    if scope not in CREATOR_SCOPES[shape.creator]:
        return CREATOR
    if scope not in ROLE_SCOPES[shape.role]:
        return ROLE
    if kind == "create":
        return CREATE_REFUSED if shape.listed else PASSED
    if kind in ("list", "pure", "profile", "privacy_queue"):
        return PASSED
    # a call on a form (or, through a response, on the form it belongs to)
    if target == "unknown":
        return NOTFOUND
    if shape.listed and not (target == "in" and shape.in_list):
        return NOTFOUND
    closed = (
        access_on and shape.creator == "editor" and shape.restrict_in and target == "in"
    )
    if closed:
        return NOTFOUND
    if shape.listed:
        if scope in LISTED_NEVER or scope not in ROW_SCOPES[ROW_ROLE[shape.role]]:
            return ROLE
    return PASSED


def lists(shape: Shape, entry: Entry, target: str, access_on: bool) -> bool:
    """Whether a list (of forms, or the privacy queue's) shows what belongs to
    ``target`` (the form's own row, or its deletion request)."""
    surface = "public"
    if expected(shape, entry, "in", access_on, surface) != PASSED:
        return False
    if shape.listed and not (target == "in" and shape.in_list):
        return False
    if entry.kind == "privacy_queue" and shape.listed:
        return False  # a grant never carries the privacy programme
    closed = access_on and shape.creator == "editor" and shape.restrict_in and target == "in"
    return not closed


# =========================================================================== the world
@dataclass
class World:
    workspace: object
    form_in: str
    response_in: str
    form_out: str
    response_out: str
    unknown_form: str
    unknown_response: str
    shape: Shape
    key: object
    token: str
    baseline_token: str


async def disable_member(workspace, user) -> None:
    repo = container.workspace_user_repo()
    membership = await repo.find_workspace_user(workspace.id, RecordId(user.id))
    membership.disabled = True
    await repo.save(membership)


async def build_world(client, workspace, shape: Shape, monkeypatch) -> World:
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    # the matrix makes thousands of calls: no budget may stand in the way, and
    # no AI provider may be reached (a call that gets past the key's gate and
    # asks for one is refused by the workspace's own AI opt-in, which is off; a
    # provider that is asked anyway fails the test)
    api = settings.api_settings
    monkeypatch.setattr(api, "PUBLIC_API_REQUESTS_PER_WINDOW", 0)
    monkeypatch.setattr(api, "PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW", 0)
    use_fake_provider(monkeypatch, FakeProvider())
    owner_token = await _token(workspace, testUser)
    form_in, response_in = await _published_form(client, owner_token, SPEC, "Matrix in")
    form_out, response_out = await _published_form(client, owner_token, SPEC, "Matrix out")
    creator = await admin_creator(workspace)
    rows = [form_in] if shape.listed and shape.in_list else []
    key = await make_key(
        workspace,
        creator,
        ALL_SCOPES,
        role=shape.role,
        form_scope="listed" if shape.listed else "all",
        forms=rows,
        row_role=ROW_ROLE[shape.role],
    )
    # an unlimited key of the same creator: what the person could do themselves
    baseline = await make_key(workspace, creator, ALL_SCOPES)
    if shape.restrict_in:
        await set_mode(workspace, form_in, MODE_RESTRICTED)
    if shape.creator == "viewer":
        await set_roles(workspace, creator, "VIEWER")
    elif shape.creator == "editor":
        await set_roles(workspace, creator, "COLLABORATOR")
    elif shape.creator == "disabled":
        await disable_member(workspace, creator)
    return World(
        workspace=workspace,
        form_in=form_in,
        response_in=response_in,
        form_out=form_out,
        response_out=response_out,
        unknown_form=str(RecordId()),
        unknown_response=str(RecordId()),
        shape=shape,
        key=key,
        token=TOKENS[str(key.id)],
        baseline_token=TOKENS[str(baseline.id)],
    )


def ids_of(world: World, target: str) -> Tuple[str, str]:
    return {
        "in": (world.form_in, world.response_in),
        "out": (world.form_out, world.response_out),
        "unknown": (world.unknown_form, world.unknown_response),
    }[target]


# =========================================================================== making a call
@dataclass
class Answer:
    verdict: str
    raw: str  # status and body (the text, for a tool), ids normalised
    body: object = None


def _normal(text: str, *ids: str) -> str:
    for i in ids:
        text = text.replace(i, "<id>")
    return text


def public_verdict(response) -> str:
    status = response.status_code
    try:
        body = response.json()
    except ValueError:
        body = {}
    code = body.get("code") if isinstance(body, dict) else None
    message = body.get("message") if isinstance(body, dict) else ""
    if status == 401:
        return UNAUTH
    if status == 404 and message == "Form not found":
        return NOTFOUND
    if status == 403:
        return {
            "key_creator_lacks_permission": CREATOR,
            "key_role_lacks_permission": ROLE,
            "key_form_scope": CREATE_REFUSED,
            "missing_scope": MISSING_SCOPE,
        }.get(code, PASSED)
    if status == 429:
        return RATE
    if status >= 500:
        return SERVER
    return PASSED


def mcp_verdict(result: dict) -> str:
    if not result.get("isError"):
        return PASSED
    text = result["content"][0]["text"] if result.get("content") else ""
    for needle, verdict in (
        ("role does not allow", ROLE),
        ("created this API key", CREATOR),
        ("limited to certain forms", CREATE_REFUSED),
        ("lacks the '", MISSING_SCOPE),
        ("Too many requests", RATE),
        ("does not exist in this workspace", NOTFOUND),
        ("Response not found in this workspace", NOTFOUND),
    ):
        if needle in text:
            return verdict
    return PASSED


async def call_public(client, token: str, method: str, path: str, world: World, target: str):
    form_id, response_id = ids_of(world, target)
    entry = PUBLIC[(method, path)]
    if entry.kind in ("form_bound", "response_bound"):
        name = PUBLIC_CALL[(method, path)]
        _, real_method, real_path, kwargs = next(
            r for r in _routes(form_id, response_id) if r[0] == name
        )
    elif (method, path) == ("GET", "/forms"):
        real_method, real_path, kwargs = "GET", "/forms", {}
    else:
        real_method, real_path, kwargs = method, path, {"json": SPEC}
    got = await _call(client, token, real_method, real_path, **kwargs)
    try:
        body = got.json()
    except ValueError:
        body = got.text
    raw = _normal(f"{got.status_code} {json.dumps(body, sort_keys=True)}", form_id, response_id)
    return Answer(public_verdict(got), raw, body)


async def call_mcp(client, token: str, tool: str, world: World, target: str):
    form_id, response_id = ids_of(world, target)
    result = await _call_tool(client, token, tool, mcp_arguments(tool, form_id, response_id))
    text = result["content"][0]["text"] if result.get("content") else ""
    raw = _normal(f"{bool(result.get('isError'))} {text}", form_id, response_id)
    return Answer(mcp_verdict(result), raw, text)


def calls(world: World):
    """Every classified call that needs a key: ``(surface, id, entry)``, the
    destructive ones last (a deleted form is gone for the rest)."""
    every = [("public", key, entry) for key, entry in PUBLIC.items() if entry.kind != "document"]
    every += [("mcp", name, entry) for name, entry in MCP.items()]
    # (closing a deletion request needs the response: before the form goes)
    return sorted(
        every,
        key=lambda item: (
            2 if item[0] == "public" and item[1][0] == "DELETE" else int(item[2].destructive)
        ),
    )


def targets_of(entry: Entry) -> List[str]:
    if entry.kind in ("form_bound", "response_bound"):
        return ["in", "out", "unknown"]
    return ["in"]  # (the target does not matter: nothing is named)


async def make_call(client, token, surface, key, world, target) -> Answer:
    if surface == "public":
        return await call_public(client, token, key[0], key[1], world, target)
    return await call_mcp(client, token, key, world, target)


# =========================================================================== the matrix
def _report(failures: List[str]) -> None:
    assert not failures, "\n".join(failures[:40]) + f"\n({len(failures)} in all)"


async def check_lists(client, world: World, access_on: bool) -> List[str]:
    """The lists a key sees: the form is in them exactly when the oracle says."""
    failures: List[str] = []
    shape = world.shape
    for surface, key, entry in calls(world):
        if entry.kind not in ("list", "privacy_queue"):
            continue
        want = expected(shape, entry, "in", access_on, surface)
        got = await make_call(client, world.token, surface, key, world, "in")
        name = f"{shape.name} {label(surface, key)}"
        if got.verdict != want:
            failures.append(f"{name}: expected {want}, got {got.verdict} ({got.raw[:90]})")
            continue
        if want != PASSED:
            continue
        if surface == "public":
            items = got.body["items"]
            seen = {i["formId"] for i in items}
            if got.body["total"] != len(items):
                failures.append(f"{name}: total {got.body['total']} != {len(items)}")
        else:
            items = json.loads(got.body)
            seen = {str(i.get("formId")) for i in items}
        for target, form_id in (("in", world.form_in), ("out", world.form_out)):
            sees = lists(shape, entry, target, access_on)
            if (form_id in seen) is not sees:
                failures.append(
                    f"{name}: the form '{target}' is {'missing from' if sees else 'in'} the list"
                )
    return failures


async def check_calls(client, world: World, access_on: bool, baseline: bool) -> List[str]:
    failures: List[str] = []
    shape = world.shape
    for surface, key, entry in calls(world):
        if entry.kind in ("list", "privacy_queue"):
            continue  # checked with their contents, above
        if surface == "public" and entry.kind == "document":
            continue
        answers: Dict[str, Answer] = {}
        for target in targets_of(entry):
            got = await make_call(client, world.token, surface, key, world, target)
            answers[target] = got
            want = expected(shape, entry, target, access_on, surface)
            name = f"{shape.name} {label(surface, key)} [{target}]"
            if got.verdict != want:
                failures.append(f"{name}: expected {want}, got {got.verdict} ({got.raw[:100]})")
        # a form off the list, or closed to the creator, is an id that is not a form
        for target in ("in", "out"):
            if (
                target in answers
                and answers[target].verdict == NOTFOUND
                and "unknown" in answers
                and answers[target].raw != answers["unknown"].raw
            ):
                failures.append(
                    f"{shape.name} {label(surface, key)} [{target}]: answers differently "
                    f"from an id that is not a form: {answers[target].raw[:80]!r} vs "
                    f"{answers['unknown'].raw[:80]!r}"
                )
        if baseline and not entry.destructive:
            # a key never does more than the person who made it: whatever it
            # gets through, the same person's unlimited key does too
            for target, got in answers.items():
                if got.verdict != PASSED:
                    continue
                own = await make_call(client, world.baseline_token, surface, key, world, target)
                if own.verdict != PASSED:
                    failures.append(
                        f"{shape.name} {label(surface, key)} [{target}]: the key passed "
                        f"but its creator's unlimited key got {own.verdict}"
                    )
    return failures


async def form_count(workspace) -> int:
    return len(await container.workspace_form_repo().list_in_workspace(workspace.id))


# the switch states: both on; key roles off (a stored limit still holds); form
# access off (only the creator's workspace role decides); and both off, for the
# shapes where either switch changes an answer
STATES = [(True, True), (False, True), (True, False)]
BOTH_OFF = {"as_creator", "listed", "creator_demoted_to_editor_restricted_form"}
CASES = [(s, r, a) for s in SHAPES for r, a in STATES] + [
    (s, False, False) for s in SHAPES if s.name in BOTH_OFF
]


@pytest.mark.parametrize(
    "shape,roles_on,access_on",
    CASES,
    ids=[
        f"{s.name}-roles_{'on' if r else 'off'}-access_{'on' if a else 'off'}"
        for s, r, a in CASES
    ],
)
async def test_the_key_matrix(
    client: AsyncClient, workspace, monkeypatch, shape, roles_on, access_on
):
    """Every entry point, as this shape of key, against the form on its list, one
    off it and an unknown id. A stored limit is enforced with the switch off too
    (switching it off never widens a key), and form-level access narrows a key
    only as far as its creator."""
    world = await build_world(client, workspace, shape, monkeypatch)
    monkeypatch.setattr(settings.api_key_roles, "ENABLED", roles_on)
    monkeypatch.setattr(settings.form_access, "ENABLED", access_on)
    before = await form_count(workspace)
    failures = await check_lists(client, world, access_on)
    failures += await check_calls(client, world, access_on, baseline=roles_on and access_on)
    _report(failures)
    if shape.listed:
        # a key limited to a list of forms made no form (and deleted none)
        assert await form_count(workspace) == before


# =========================================================================== the rest
async def test_a_revoked_key_reaches_nothing(client: AsyncClient, workspace, monkeypatch):
    world = await build_world(client, workspace, Shape("revoked"), monkeypatch)
    assert await container.workspace_api_key_repo().revoke_one(workspace.id, world.key.id)
    failures: List[str] = []
    for surface, key, entry in calls(world):
        if surface == "public":
            got = await call_public(client, world.token, key[0], key[1], world, "in")
            if got.verdict != UNAUTH:
                failures.append(f"{label(surface, key)}: {got.verdict} {got.raw[:80]}")
        else:
            response = await client.post(
                MCP_URL,
                headers={**MCP_HEADERS, "Authorization": f"Bearer {world.token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": key,
                        "arguments": mcp_arguments(key, world.form_in, world.response_in),
                    },
                },
                follow_redirects=True,
            )
            if response.status_code != 401:
                failures.append(f"{label(surface, key)}: {response.status_code}")
    _report(failures)
    # the API's own document needs no key (it describes the API; it holds no data)
    assert (await client.get(f"{BASE}/openapi.json")).status_code == 200


async def test_a_key_made_while_the_switch_was_on_is_still_held_when_it_goes_off(
    client: AsyncClient, workspace, monkeypatch
):
    """The same listed key, the same forms, the switch flipped between two runs:
    the answers are identical (a stored limit never lapses)."""
    world = await build_world(client, workspace, Shape("listed", listed=True), monkeypatch)
    answers = {}
    for on in (True, False):
        monkeypatch.setattr(settings.api_key_roles, "ENABLED", on)
        for target in ("in", "out", "unknown"):
            got = await call_public(client, world.token, "GET", "/forms/{form_id}", world, target)
            answers[(on, target)] = (got.verdict, got.raw)
    for target in ("in", "out", "unknown"):
        assert answers[(True, target)] == answers[(False, target)], target
    assert answers[(True, "in")][0] == PASSED
    assert answers[(True, "out")] == answers[(True, "unknown")]


@pytest.mark.parametrize("with_submission_list", [False, True], ids=["no_submission_list", "submission_list"])
async def test_the_submissions_routes_answer_a_form_off_the_list_like_an_unknown_id(
    client: AsyncClient, workspace, monkeypatch, with_submission_list
):
    """The submissions routes decide a key's own submission list before its form
    list (403 ``form_not_allowed`` from the id alone), and the form list after
    (404): either way a form that exists and one that does not answer alike, and
    nothing is revealed (docs/api/README.md)."""
    world = await build_world(client, workspace, Shape("listed", listed=True), monkeypatch)
    if with_submission_list:
        key = await container.workspace_api_key_repo().get_or_404(world.key.id)
        key.submission_form_ids = [world.form_in]
        await container.workspace_api_key_repo().save(key)
    submissions = ("POST", "/forms/{form_id}/submissions")
    patched = ("PATCH", "/forms/{form_id}/submissions/{response_id}")
    for route in (submissions, patched):
        out = await call_public(client, world.token, route[0], route[1], world, "out")
        unknown = await call_public(client, world.token, route[0], route[1], world, "unknown")
        assert out.raw == unknown.raw, route
        status = int(out.raw.split(" ", 1)[0])
        assert status == (403 if with_submission_list else 404), (route, out.raw)
    # the form on the list is let through
    made = await call_public(client, world.token, "POST", submissions[1], world, "in")
    assert made.verdict == PASSED


async def test_a_key_that_makes_forms_is_not_asked_for_a_list(
    client: AsyncClient, workspace, monkeypatch
):
    """The other side of the creation rule: an unlimited key, or one with only a
    role, makes forms (in ``test_key_matrix`` the create rows pass for them); a
    listed key makes none, with nothing stored."""
    world = await build_world(client, workspace, Shape("listed", listed=True), monkeypatch)
    before = await form_count(workspace)
    for surface, key, entry in calls(world):
        if entry.kind != "create":
            continue
        got = await make_call(client, world.token, surface, key, world, "in")
        assert got.verdict == CREATE_REFUSED, (label(surface, key), got.raw[:100])
    assert await form_count(workspace) == before


def test_the_oracle_is_not_trivially_true():
    """The table above has to be able to fail: every shape but the unlimited key
    has a call on the form "in" that it expects to be refused, and the unlimited
    key of an Admin none."""
    refused = {
        s.name: any(
            expected(s, e, "in", True, surface) != PASSED
            for surface, entries in (("public", PUBLIC.values()), ("mcp", MCP.values()))
            for e in entries
            if e.kind != "document"
        )
        for s in SHAPES
    }
    assert all(refused[s.name] for s in SHAPES if s.name != "as_creator"), refused
    assert not refused["as_creator"]
