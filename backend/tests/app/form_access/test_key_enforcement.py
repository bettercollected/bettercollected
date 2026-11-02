"""Form-level access for API keys: the public API and the MCP server.

A key acts as its creator. With ``FORM_ACCESS_ENABLED`` on, every call that
names a form is decided on that form as the creator: an Owner's or Admin's key
reaches every form, restricted ones included; the key of a member a restricted
form is closed to (an Editor since demoted, say) gets the 404 of a form that is
not there on every route and tool, and the form is absent from the lists; a
grant gives the key what the grant gives, and a form the key can open but not
use for the call's purpose is a 403, as everywhere. Off (the default): nothing
changes and nothing new is read.
"""

import json
import re
from types import SimpleNamespace

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.form_access_grant import ROLE_EDITOR, ROLE_VIEWER
from backend.app.services.ai.api_keys import CreateAPIKeyDto
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.controllers.submission_cases import SPEC, text
from tests.app.controllers.test_mcp_server import _call_tool, _tool_text
from tests.app.form_access.helpers import add_member, grant, restrict
from tests.app.form_access.test_switch_and_memo import statements, touching_new_tables

BASE = "/api/v1/public/v1"
ALL_SCOPES = [
    "forms:read",
    "forms:write",
    "forms:delete",
    "responses:read",
    "deletion_requests:read",
    "deletion_requests:write",
    "submissions:write",
]
ANSWERS = {"answers": {"name": text("Ada")}, "consent": True}
OPS = {"ops": [{"op": "update_form_info", "title": "A new title"}], "atomic": True}
OPEN_TITLE = "Open registration"
CLOSED_TITLE = "Closed registration"


def _auth(token: str, **headers) -> dict:
    return {"Authorization": f"Bearer {token}", **headers}


async def _token(workspace, user, scopes=ALL_SCOPES) -> str:
    created = await container.api_key_service().create_key(
        workspace.id,
        CreateAPIKeyDto(
            name="access key",
            scopes=scopes,
            acknowledge_unredacted_responses="responses:read" in scopes,
        ),
        user,
    )
    return created.token


async def _set_roles(workspace, user, *roles):
    repo = container.workspace_user_repo()
    membership = await repo.find_workspace_user(workspace.id, RecordId(user.id))
    membership.roles = list(roles)
    await repo.save(membership)


async def _member_key(workspace, *roles_after):
    """A key made by an Admin, who then holds ``roles_after`` (a demotion: a key
    never does more than its creator may now)."""
    user = await add_member(workspace, "ADMIN")
    token = await _token(workspace, user)
    await _set_roles(workspace, user, *roles_after)
    return user, token


async def _published_form(client, owner_token, spec, title):
    created = await client.post(
        f"{BASE}/forms", json={**spec, "title": title}, headers=_auth(owner_token)
    )
    assert created.status_code == 201, created.text
    form_id = created.json()["formId"]
    published = await client.post(
        f"{BASE}/forms/{form_id}/publish", headers=_auth(owner_token)
    )
    assert published.status_code == 200, published.text
    submitted = await client.post(
        f"{BASE}/forms/{form_id}/submissions", json=ANSWERS, headers=_auth(owner_token)
    )
    assert submitted.status_code == 201, submitted.text
    response_id = submitted.json()["responseId"]
    # a pending deletion request, for the privacy routes
    await container.form_response_service().request_for_response_deletion(
        await _workspace_id(response_id), response_id, testUser
    )
    return form_id, response_id


async def _workspace_id(response_id):
    docs = await container.form_response_repo().list_by_response_id(response_id)
    return docs[0].workspace_id


@pytest.fixture()
async def world(client: AsyncClient, workspace, monkeypatch):
    """An open and a restricted published form, each with one response that has
    a deletion request, and keys of: the owner, an Admin, an Editor the form is
    closed to, an Editor with a Viewer grant on it and an Editor with an Editor
    grant on it. The switch is off while this is set up."""
    monkeypatch.setattr(settings, "SUBMISSIONS_API_ENABLED", True)
    owner_token = await _token(workspace, testUser)
    open_id, open_response = await _published_form(client, owner_token, SPEC, OPEN_TITLE)
    closed_id, closed_response = await _published_form(
        client, owner_token, SPEC, CLOSED_TITLE
    )
    await restrict(workspace, closed_id)
    admin, admin_token = await _member_key(workspace, "ADMIN")
    editor, editor_token = await _member_key(workspace, "COLLABORATOR")
    viewer_granted, viewer_granted_token = await _member_key(workspace, "COLLABORATOR")
    editor_granted, editor_granted_token = await _member_key(workspace, "COLLABORATOR")
    await grant(workspace, closed_id, viewer_granted.id, ROLE_VIEWER)
    await grant(workspace, closed_id, editor_granted.id, ROLE_EDITOR)
    return SimpleNamespace(
        workspace=workspace,
        open_id=open_id,
        open_response=open_response,
        closed_id=closed_id,
        closed_response=closed_response,
        token=SimpleNamespace(
            owner=owner_token,
            admin=admin_token,
            editor=editor_token,
            viewer_granted=viewer_granted_token,
            editor_granted=editor_granted_token,
        ),
    )


def _routes(form_id, response_id):
    """Every public API route that names a form: (name, method, path, kwargs)."""
    f = f"/forms/{form_id}"
    r = f"{f}/responses/{response_id}"
    return [
        ("getForm", "GET", f, {}),
        ("replaceForm", "PUT", f, {"json": SPEC, "headers": {"If-Match": '"x"'}}),
        ("previewReplaceForm", "POST", f"{f}/replace/dry-run", {"json": SPEC}),
        ("publishForm", "POST", f"{f}/publish", {}),
        ("deleteForm", "DELETE", f, {}),
        ("applyFormOps", "POST", f"{f}/ops", {"json": OPS}),
        ("dryRunFormOps", "POST", f"{f}/ops/dry-run", {"json": OPS}),
        ("listResponses", "GET", f"{f}/responses", {}),
        ("getResponse", "GET", r, {}),
        (
            "closeDeletionRequest",
            "POST",
            f"{r}/deletion-request/close",
            {"json": {"outcome": "declined", "reason": "legal_obligation"}},
        ),
        ("createSubmission", "POST", f"{f}/submissions", {"json": ANSWERS}),
        (
            "updateSubmission",
            "PATCH",
            f"{f}/submissions/{response_id}",
            {"json": {"answers": {"name": text("Grace")}}},
        ),
    ]


async def _call(client, token, method, path, **kwargs):
    headers = _auth(token, **kwargs.pop("headers", {}))
    return await client.request(method, f"{BASE}{path}", headers=headers, **kwargs)


def _unknown_ids():
    return str(RecordId()), str(RecordId())


# -- the public API ---------------------------------------------------------------


async def test_a_key_of_a_member_the_form_is_closed_to_is_refused_on_every_route(
    client: AsyncClient, world, switch_on
):
    """Each route answers a closed form exactly as it answers a form that is not
    there (status and body), for the same key. The one exception is the privacy
    route: the Editor's role never held ``privacy.manage``, so it was and stays
    a 403 for any form (open, closed or unknown)."""
    unknown_form, unknown_response = _unknown_ids()
    closed = _routes(world.closed_id, world.closed_response)
    unknown = _routes(unknown_form, unknown_response)
    opened = _routes(world.open_id, world.open_response)
    for (name, method, path, kw), (_, _, upath, ukw), (_, _, opath, okw) in zip(
        closed, unknown, opened
    ):
        got = await _call(client, world.token.editor, method, path, **kw)
        ghost = await _call(client, world.token.editor, method, upath, **ukw)
        assert (got.status_code, got.json()) == (ghost.status_code, ghost.json()), name
        expected = 403 if name == "closeDeletionRequest" else 404
        assert got.status_code == expected, (name, got.status_code, got.text)
        # the same key and the open form: the form is not what refuses it
        # (never destroy it here: delete and publish are tried on the closed one)
        if name in ("deleteForm", "publishForm"):
            continue
        allowed = await _call(client, world.token.editor, method, opath, **okw)
        # (a response is changed only by the key that made it: its own 404)
        assert allowed.status_code != 404 or name == "updateSubmission", (
            name,
            allowed.status_code,
            allowed.text,
        )


async def test_an_admin_and_an_owner_key_reach_the_restricted_form(
    client: AsyncClient, world, switch_on
):
    for token in (world.token.admin, world.token.owner):
        for name, method, path, kw in _routes(world.closed_id, world.closed_response):
            if name in ("deleteForm", "updateSubmission"):
                continue  # destructive / a response another key made
            got = await _call(client, token, method, path, **kw)
            assert got.status_code not in (403, 404), (name, got.status_code, got.text)
    # and may delete it (the Admin's key)
    gone = await _call(client, world.token.admin, "DELETE", f"/forms/{world.closed_id}")
    assert gone.status_code == 204, gone.text


async def test_the_list_leaves_out_the_closed_form_and_its_total(
    client: AsyncClient, world, switch_on
):
    for token, sees_closed in (
        (world.token.editor, False),
        (world.token.admin, True),
        (world.token.owner, True),
        (world.token.viewer_granted, True),
    ):
        listed = (await _call(client, token, "GET", "/forms")).json()
        ids = {i["formId"] for i in listed["items"]}
        assert world.open_id in ids
        assert (world.closed_id in ids) is sees_closed
        assert listed["total"] == len(ids)


async def test_a_grant_gives_the_key_what_the_grant_gives(
    client: AsyncClient, world, switch_on
):
    # a Viewer grant: the form and its structure, no editing, no exporting
    token = world.token.viewer_granted
    assert (await _call(client, token, "GET", f"/forms/{world.closed_id}")).status_code == 200
    for method, path, kw in (
        ("POST", f"/forms/{world.closed_id}/ops", {"json": OPS}),
        ("GET", f"/forms/{world.closed_id}/responses", {}),
    ):
        refused = await _call(client, token, method, path, **kw)
        assert refused.status_code == 403, (path, refused.text)
        assert refused.json()["code"] == "key_creator_lacks_permission"
    # an Editor grant: edit, read and export the answers of that one form
    token = world.token.editor_granted
    assert (
        await _call(client, token, "POST", f"/forms/{world.closed_id}/ops", json=OPS)
    ).status_code == 200
    assert (
        await _call(client, token, "GET", f"/forms/{world.closed_id}/responses")
    ).status_code == 200
    # a grant on one form is no way into another restricted form
    other, _ = await _published_form(client, world.token.owner, SPEC, "Another closed form")
    await restrict(world.workspace, other)
    assert (await _call(client, token, "GET", f"/forms/{other}")).status_code == 404


async def test_a_response_is_found_only_through_a_form_the_key_may_open(
    client: AsyncClient, world, switch_on
):
    # the response of the closed form, asked for through the OPEN form's path
    got = await _call(
        client,
        world.token.admin,
        "GET",
        f"/forms/{world.open_id}/responses/{world.closed_response}",
    )
    assert got.status_code == 404


async def test_the_submissions_api_keeps_taking_answers_for_a_restricted_form(
    client: AsyncClient, world, switch_on
):
    """Restricting a form is about the team, not the respondent: a key whose
    creator may edit the form still submits to it."""
    made = await _call(
        client, world.token.admin, "POST", f"/forms/{world.closed_id}/submissions", json=ANSWERS
    )
    assert made.status_code == 201, made.text
    changed = await _call(
        client,
        world.token.admin,
        "PATCH",
        f"/forms/{world.closed_id}/submissions/{made.json()['responseId']}",
        json={"answers": {"name": text("Grace")}},
    )
    assert changed.status_code == 200, changed.text


async def test_a_closed_form_is_a_404_before_the_keys_own_form_list(
    client: AsyncClient, world, switch_on
):
    """A key limited to some forms answers 403 ``form_not_allowed`` for every
    form outside its list, an unknown id included; for one inside it, a form
    closed to the key's creator answers as an unknown form does (404). Neither
    answer tells a closed form from a missing one."""
    workspace = world.workspace

    async def limited_key(form_ids):
        user = await add_member(workspace, "ADMIN")
        created = await container.api_key_service().create_key(
            workspace.id,
            CreateAPIKeyDto(
                name="limited", scopes=["submissions:write"], submission_form_ids=form_ids
            ),
            user,
        )
        await _set_roles(workspace, user, "COLLABORATOR")
        return created.token

    async def post(token, form_id):
        got = await _call(
            client, token, "POST", f"/forms/{form_id}/submissions", json=ANSWERS
        )
        return got.status_code, got.json()

    outside = await limited_key([world.open_id])
    assert await post(outside, world.closed_id) == await post(outside, RecordId())
    assert (await post(outside, world.closed_id))[1]["code"] == "form_not_allowed"
    inside = await limited_key([world.closed_id])
    unlimited = await limited_key(None)
    assert await post(inside, world.closed_id) == await post(unlimited, RecordId())
    assert (await post(inside, world.closed_id))[0] == 404
    assert await post(unlimited, world.closed_id) == await post(unlimited, RecordId())


async def test_a_form_id_that_is_no_id_is_a_404_for_every_key(
    client: AsyncClient, world, switch_on
):
    for token in (world.token.editor, world.token.admin):
        for name, method, path, kw in _routes("not-an-id", "not-an-id"):
            got = await _call(client, token, method, path, **kw)
            assert got.status_code in (404, 403, 422), (name, got.status_code, got.text)
            assert got.status_code != 500, name
    editor = await _call(client, world.token.editor, "GET", "/forms/not-an-id")
    admin = await _call(client, world.token.admin, "GET", "/forms/not-an-id")
    assert (editor.status_code, editor.json()) == (admin.status_code, admin.json())


async def test_the_access_mode_is_in_no_key_payload(
    client: AsyncClient, world, switch_on
):
    body = (await _call(client, world.token.admin, "GET", f"/forms/{world.closed_id}")).text
    assert not re.search(r"access.?mode|restricted", body, re.IGNORECASE)
    listed = (await _call(client, world.token.admin, "GET", "/forms")).text
    assert not re.search(r"access.?mode|restricted", listed, re.IGNORECASE)
    spec = _tool_text(
        await _call_tool(client, world.token.admin, "get_form_spec", {"form_id": world.closed_id})
    )
    assert not re.search(r"access.?mode|restricted", json.dumps(spec), re.IGNORECASE)
    form = await _call_tool(client, world.token.admin, "get_form", {"form_id": world.closed_id})
    assert not re.search(r"access.?mode|restricted", form["content"][0]["text"], re.IGNORECASE)


# -- MCP ---------------------------------------------------------------------------


def _mcp_calls(form_id, response_id):
    return [
        ("get_form", {"form_id": form_id}),
        ("get_form_spec", {"form_id": form_id}),
        ("update_form", {"form_id": form_id, "ops": OPS["ops"]}),
        ("dry_run_ops", {"form_id": form_id, "ops": OPS["ops"]}),
        ("publish_form", {"form_id": form_id}),
        ("list_responses", {"form_id": form_id}),
        ("get_response", {"response_id": response_id}),
    ]


def _normal(text_, *ids):
    for i in ids:
        text_ = text_.replace(i, "<id>")
    return text_


async def test_every_form_bound_mcp_tool_treats_a_closed_form_as_unknown(
    client: AsyncClient, world, switch_on
):
    unknown_form, unknown_response = _unknown_ids()
    for tool, args in _mcp_calls(world.closed_id, world.closed_response):
        got = await _call_tool(client, world.token.editor, tool, args)
        ghost_args = _mcp_calls(unknown_form, unknown_response)
        ghost = await _call_tool(
            client, world.token.editor, tool, dict(ghost_args)[tool]
        )
        assert got.get("isError") is True, tool
        assert _normal(got["content"][0]["text"], world.closed_id, world.closed_response) == _normal(
            ghost["content"][0]["text"], unknown_form, unknown_response
        ), tool
    # the lists
    listed = _tool_text(await _call_tool(client, world.token.editor, "list_forms", {}))
    assert {f["formId"] for f in listed} == {world.open_id}
    # while the same key opens the open form
    for tool, args in _mcp_calls(world.open_id, world.open_response):
        if tool == "publish_form":
            continue
        ok = await _call_tool(client, world.token.editor, tool, args)
        assert not ok.get("isError"), (tool, ok)


async def test_the_mcp_keys_of_an_admin_reach_the_restricted_form(
    client: AsyncClient, world, switch_on
):
    listed = _tool_text(await _call_tool(client, world.token.admin, "list_forms", {}))
    assert {f["formId"] for f in listed} == {world.open_id, world.closed_id}
    for tool, args in _mcp_calls(world.closed_id, world.closed_response):
        got = await _call_tool(client, world.token.admin, tool, args)
        assert not got.get("isError"), (tool, got)


async def test_mcp_grants_and_the_permission_a_tool_needs(
    client: AsyncClient, world, switch_on
):
    token = world.token.viewer_granted
    assert not (
        await _call_tool(client, token, "get_form", {"form_id": world.closed_id})
    ).get("isError")
    update = await _call_tool(
        client, token, "update_form", {"form_id": world.closed_id, "ops": OPS["ops"]}
    )
    assert update["isError"] and "form.edit" in update["content"][0]["text"]
    answers = await _call_tool(
        client, token, "list_responses", {"form_id": world.closed_id}
    )
    assert answers["isError"] and "response.export" in answers["content"][0]["text"]
    # the same Viewer-granted key does not see the response of the closed form
    # through get_response either
    one = await _call_tool(
        client, token, "get_response", {"response_id": world.closed_response}
    )
    assert one["isError"]
    # an Editor grant gives the answers of that form
    granted = world.token.editor_granted
    one = await _call_tool(
        client, granted, "get_response", {"response_id": world.closed_response}
    )
    assert not one.get("isError"), one


# -- the switch off ---------------------------------------------------------------


async def test_off_an_editors_key_reads_as_before_and_no_new_table_is_touched(
    client: AsyncClient, world, switch_off
):
    with statements() as seen:
        for name, method, path, kw in _routes(world.closed_id, world.closed_response):
            if name in ("deleteForm", "publishForm", "closeDeletionRequest", "updateSubmission"):
                continue
            got = await _call(client, world.token.editor, method, path, **kw)
            assert got.status_code not in (403, 404), (name, got.status_code, got.text)
        listed = (await _call(client, world.token.editor, "GET", "/forms")).json()
        assert world.closed_id in {i["formId"] for i in listed["items"]}
        for tool, args in _mcp_calls(world.closed_id, world.closed_response):
            if tool == "publish_form":
                continue
            got = await _call_tool(client, world.token.editor, tool, args)
            assert not got.get("isError"), (tool, got)
    assert not touching_new_tables(seen)


# Statements per call with the switch off, measured on the commit before keys
# were decided per form (a call after a first one). Adding a query to these
# paths while the switch is off has to raise a number here knowingly.
OFF_API_STATEMENTS = {
    "GET /forms": 12,
    "GET /forms/{f}": 13,
    "GET /forms/{f}/responses": 16,
    "GET /forms/{f}/responses/{r}": 15,
    "POST /forms/{f}/ops/dry-run": 13,
}
OFF_MCP_STATEMENTS = {
    "list_forms": 8,
    "get_form": 8,
    "get_form_spec": 9,
    "dry_run_ops": 9,
    "list_responses": 12,
    "get_response": 10,
}


async def test_off_the_key_calls_run_no_more_statements_than_before(
    client: AsyncClient, world, switch_off
):
    token = world.token.editor
    measured = {}
    for route in OFF_API_STATEMENTS:
        method, path = route.split(" ", 1)
        path = path.format(f=world.open_id, r=world.open_response)
        kw = {"json": OPS} if method == "POST" else {}
        await _call(client, token, method, path, **kw)  # warm what is cached
        with statements() as seen:
            got = await _call(client, token, method, path, **kw)
        assert got.status_code == 200, (route, got.text)
        measured[route] = len(seen)
    arguments = {
        "list_forms": {},
        "get_form": {"form_id": world.open_id},
        "get_form_spec": {"form_id": world.open_id},
        "dry_run_ops": {"form_id": world.open_id, "ops": OPS["ops"]},
        "list_responses": {"form_id": world.open_id},
        "get_response": {"response_id": world.open_response},
    }
    for tool in OFF_MCP_STATEMENTS:
        await _call_tool(client, token, tool, arguments[tool])
        with statements() as seen:
            got = await _call_tool(client, token, tool, arguments[tool])
        assert not got.get("isError"), (tool, got)
        measured[tool] = len(seen)
    limits = {**OFF_API_STATEMENTS, **OFF_MCP_STATEMENTS}
    over = {k: (n, limits[k]) for k, n in measured.items() if n > limits[k]}
    assert not over, (over, measured)
