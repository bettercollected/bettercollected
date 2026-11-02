"""The route matrix of form-level access: every route that is about a form, run
as every kind of member, against a form in each access mode, with the switch on
and off.

The net is the application's own route table, not a list kept by hand. Every
route that carries a form id, a custom URL (slug) or a response id, or sits on a
form-bound collection, has to be classified in ``route_table.py`` (decided on the
form, with the permission it asks, or exempt, with the reason). A new route that
is not classified fails ``test_every_form_scoped_route_is_classified``, naming it.

What each classified route is run as (the expectations are written from the
access model of docs/enterprise-access-model.md, not read from the services):

* a member the form is closed to (restricted, no grant, no way in): the 404 of a
  form that is not there, byte for byte, when their role holds the permission the
  route asks, and the usual 403 when it lacks it;
* a grantee: exactly what the grant gives (an Editor grant edits and exports but
  never deletes the form; a Viewer grant on a Viewer reads only);
* an Owner or an Admin: always passes;
* a Privacy officer: the form's structure and the privacy programme, nothing else;
* the same members on an open form (a grant lifts a role, a restricted-only rule
  does not apply) and with the switch off (the workspace role decides, as before).

The world is built once per test and every request of the matrix is sent against
it, so the whole matrix costs a few seconds. A route found to leak is taken out of
the loop and given a test of its own marked ``xfail(strict=True)``, so the PR that
fixes it turns that test into a failure until the marker is removed (none leaks
today).
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from unittest.mock import AsyncMock
from urllib.parse import parse_qsl

import pytest
from common.ids import RecordId
from fastapi.routing import iter_route_contexts
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.router import root_api_router
from backend.app.schemas.form_access_grant import (
    GRANT_ROLES,
    ROLE_EDITOR,
    ROLE_REVIEWER,
    ROLE_VIEWER,
)
from backend.app.services.authorization_service import ROLE_PERMISSIONS
from backend.app.services.form_access.model import (
    FORM_SCOPED as SERVICE_FORM_SCOPED,
    GRANT_PERMISSIONS as SERVICE_GRANT_PERMISSIONS,
    MODE_RESTRICTED,
    MODE_WORKSPACE,
)
from backend.app.services.form_access.mode import TEMPLATE_FROM_RESTRICTED_CODE
from backend.config import settings
from tests.app.controllers.test_permission_matrix import (  # noqa: F401
    ADMIN,
    ADMINS,
    CASES,
    EDITOR,
    OWNER,
    PRIVACY,
    REVIEWER,
    ROLES_WITH,
    USERS,
    VIEWER,
    _cookies,
    matrix,
    outside_services,
    scim_on,
)
from tests.app.form_access.helpers import add_member, grant, set_mode, team_with
from tests.app.form_access.route_table import (
    EXEMPT,
    FORM,
    LIST,
    RESPONSE,
    ROUTES,
    Route,
    is_form_scoped,
)
from tests.app.controllers.test_signature_image_route import (  # noqa: F401
    _drawn_response,
    _route as _signature_route,
    signed_form,
    store,
)
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.sso_helpers import sso_on  # noqa: F401

P = Permission
ROOT = settings.api_settings.ROOT_PATH
NOT_FOUND_BODY = "Form not found in workspace"
OFF_CODE = "form_access_off"

# -- the access model, written out from the doc (not imported from the service) ------

# what a grant can give and a restricted form withholds
FORM_SCOPED: FrozenSet[Permission] = frozenset(
    {
        P.FORM_READ,
        P.FORM_EDIT,
        P.FORM_DELETE,
        P.FORM_SHARE,
        P.RESPONSE_READ,
        P.RESPONSE_ANNOTATE,
        P.RESPONSE_EXPORT,
        P.RESPONSE_DELETE,
        P.RESPONSE_EDIT,
        P.ANALYTICS_READ,
    }
)
# what a grant gives, by its role (doc, section 2: an Editor grant never deletes
# the form; export only with the flag for a Reviewer or Viewer grant)
GRANTS: Dict[str, FrozenSet[Permission]] = {
    ROLE_EDITOR: frozenset(
        {
            P.FORM_READ,
            P.FORM_EDIT,
            P.FORM_SHARE,
            P.RESPONSE_READ,
            P.RESPONSE_ANNOTATE,
            P.RESPONSE_EXPORT,
            P.RESPONSE_DELETE,
            P.RESPONSE_EDIT,
            P.ANALYTICS_READ,
        }
    ),
    ROLE_REVIEWER: frozenset(
        {P.FORM_READ, P.RESPONSE_READ, P.RESPONSE_ANNOTATE, P.ANALYTICS_READ}
    ),
    ROLE_VIEWER: frozenset({P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ}),
}
# a Privacy officer without a way in keeps these on a restricted form
PRIVACY_ON_RESTRICTED = frozenset({P.FORM_READ, P.PRIVACY_MANAGE, P.AUDIT_READ})
# what the export flag adds to a Reviewer or Viewer grant (an Editor grant has it)
EXPORT = frozenset({P.RESPONSE_EXPORT})


@dataclass(frozen=True)
class Principal:
    name: str
    role: str  # a key of ROLES_WITH's roles: owner, admin, editor, reviewer, viewer, ...
    grant: Optional[str] = None  # the grant role on the matrix's form
    export: bool = False  # the grant carries the export flag (Reviewer / Viewer grants)
    team: bool = False  # the grant is on a team the member belongs to
    creator: bool = False  # the member created the form (the link's user)

    @property
    def privileged(self) -> bool:
        return self.role in (OWNER, ADMIN)

    @property
    def privacy(self) -> bool:
        return self.role == PRIVACY


PRINCIPALS: Dict[str, Principal] = {
    p.name: p
    for p in (
        Principal("owner", OWNER),
        Principal("admin", ADMIN),
        Principal("editor", EDITOR),
        Principal("reviewer", REVIEWER),
        Principal("viewer", VIEWER),
        Principal("privacy", PRIVACY),
        # a Viewer with an Editor grant: the grant lifts the role on that form
        Principal("viewer_editor_grant", VIEWER, ROLE_EDITOR),
        # a Viewer with a Reviewer grant
        Principal("viewer_reviewer_grant", VIEWER, ROLE_REVIEWER),
        # an Editor whose grant is only Viewer: on a restricted form the grant is
        # all they have there, on an open form their role stands
        Principal("editor_viewer_grant", EDITOR, ROLE_VIEWER),
        # an Editor with an Editor grant: holds everything but deleting the form
        Principal("editor_editor_grant", EDITOR, ROLE_EDITOR),
        # the export flag: a Viewer grant and a Reviewer grant that may export
        Principal("viewer_export_grant", VIEWER, ROLE_VIEWER, export=True),
        Principal("viewer_reviewer_export_grant", VIEWER, ROLE_REVIEWER, export=True),
        # a grant given to a team the member belongs to
        Principal("viewer_team_grant", VIEWER, ROLE_EDITOR, team=True),
        # the form's creator: keeps their own role's rights on a restricted form
        Principal("creator_editor", EDITOR, creator=True),
        # a creator demoted to Viewer since
        Principal("creator_viewer", VIEWER, creator=True),
        # a creator whose membership was removed: nothing at all
        Principal("creator_removed", "removed", creator=True),
    )
}
# the principals run together on the form made by the owner, and the creators,
# each run on a form they made (the link's user), one per world
CREATORS = [name for name, p in PRINCIPALS.items() if p.creator]
NON_CREATORS = [name for name, p in PRINCIPALS.items() if not p.creator]
# the stored workspace role of the principals that need a member row of their own
STORED_ROLE = {
    VIEWER: WorkspaceRoles.VIEWER,
    EDITOR: WorkspaceRoles.COLLABORATOR,
    "removed": WorkspaceRoles.COLLABORATOR,
}
GRANTEE_ROLE = {
    name: STORED_ROLE[p.role]
    for name, p in PRINCIPALS.items()
    if p.grant is not None or p.creator
}


def base_permissions(principal: Principal) -> FrozenSet[Permission]:
    """What the member's workspace role holds (the doc's role table)."""
    return frozenset(p for p, roles in ROLES_WITH.items() if principal.role in roles)


def held_on_form(principal: Principal, mode: str, switch_on: bool) -> FrozenSet[Permission]:
    """What the member holds on the matrix's form (doc, section 2)."""
    base = base_permissions(principal)
    if not switch_on or principal.privileged or not base:
        return base
    granted = (
        frozenset()
        if principal.privacy or principal.grant is None
        else GRANTS[principal.grant]
        | (EXPORT if principal.export and principal.grant != ROLE_EDITOR else frozenset())
    )
    if mode == MODE_WORKSPACE:
        return base | granted
    outside = base - FORM_SCOPED - {P.PRIVACY_MANAGE}
    if principal.creator:
        return base | granted
    if granted:
        return outside | granted
    if principal.privacy:
        return (base & PRIVACY_ON_RESTRICTED) | outside
    return outside


def closed_to(principal: Principal, mode: str, switch_on: bool) -> bool:
    """The form is a restricted one this member has no way into and their role
    reads forms: it answers as a form that is not there."""
    return (
        switch_on
        and mode == MODE_RESTRICTED
        and not principal.privileged
        and not principal.privacy
        and not principal.creator
        and principal.grant is None
        and P.FORM_READ in base_permissions(principal)
    )


def decide(principal: Principal, chain, mode: str, switch_on: bool):
    """``allowed`` or the status the route answers: the first permission of the
    chain the member lacks decides it."""
    base = base_permissions(principal)
    held = held_on_form(principal, mode, switch_on)
    closed = closed_to(principal, mode, switch_on)
    for permission in chain:
        if permission not in held:
            return 404 if closed and permission in base else 403
    return "allowed"


def expected(route: Route, principal: Principal, mode: str, switch_on: bool):
    if route.needs_switch and not switch_on:
        return 422
    if (
        route.creator_only
        and switch_on
        and mode == MODE_RESTRICTED
        and not principal.privileged
        and not principal.creator
        and decide(principal, route.chain, mode, switch_on) == "allowed"
    ):
        # may do it by role or grant, but a restricted form's template is for its
        # creator, an Owner or an Admin: the code, not the generic 403
        return "creator_only"
    chain = route.chain
    if route.respondent_rule and (
        closed_to(principal, mode, switch_on) or not base_permissions(principal)
    ):
        # no staff here (closed to them, or no member at all): the respondent rule
        # answers "not found" for a response that is not theirs
        return 404
    if route.kind == LIST:
        # a workspace list answers the workspace-level permission; what it
        # leaves out is checked on the body
        return "allowed" if chain[0] in base_permissions(principal) else 403
    if route.delivery_log:
        base = base_permissions(principal)
        opened = base
        if (
            switch_on
            and mode == MODE_RESTRICTED
            and P.FORM_EDIT not in held_on_form(principal, mode, switch_on)
        ):
            opened = base - {P.AUDIT_READ}
        for permission in (P.FORM_EDIT, P.AUDIT_READ):
            if permission in opened:
                chain = (permission,)
                break
        else:
            chain = (P.FORM_EDIT,)
    return decide(principal, chain, mode, switch_on)


# -- the route table ----------------------------------------------------------------


def rest_routes() -> Set[Tuple[str, str]]:
    found = set()
    for context in iter_route_contexts(root_api_router.routes):
        path = context.path
        if not path or not path.startswith(ROOT):
            continue
        for method in context.methods or ():
            if method in ("HEAD", "OPTIONS"):
                continue
            found.add((method, path[len(ROOT):]))
    return found


def test_every_form_scoped_route_is_classified():
    """A route with a form id, a slug or a response id in its path (or on a
    form-bound collection) is decided on the form (ROUTES) or exempt with a
    reason (EXEMPT): a new one has to be put in ``route_table.py`` first."""
    live = rest_routes()
    scoped = {r for r in live if is_form_scoped(ROOT + r[1])}
    # the table really is bound to the application's routes
    assert len(scoped) >= 130, len(scoped)
    classified = set(ROUTES) | set(EXEMPT)
    missing = sorted(scoped - classified)
    assert not missing, (
        "form-scoped routes missing from tests/app/form_access/route_table.py "
        "(classify each: ROUTES with the permission it asks, or EXEMPT with the "
        "reason no form-level decision applies):\n"
        + "\n".join(f"  {method} {path}" for method, path in missing)
    )
    assert not (set(ROUTES) & set(EXEMPT)), set(ROUTES) & set(EXEMPT)


def test_the_table_names_no_route_that_is_gone():
    live = rest_routes()
    gone = sorted((set(ROUTES) | set(EXEMPT)) - live)
    assert not gone, (
        "route_table.py lists routes that no longer exist (remove them):\n"
        + "\n".join(f"  {method} {path}" for method, path in gone)
    )


def test_every_decided_route_has_its_outcome_pinned():
    """The statuses an allowed member is answered with are pinned per route (see
    ``route_table.OUTCOMES``): a new route has to say what a member who is let
    through gets, and the routes that return data say what the data is."""
    unpinned = sorted(key for key, route in ROUTES.items() if not route.ok)
    assert not unpinned, (
        "decided routes without a pinned outcome (route_table.OUTCOMES):\n"
        + "\n".join(f"  {m} {p}" for m, p in unpinned)
    )
    assert sum(1 for route in ROUTES.values() if route.check) >= 20


def test_every_exemption_names_its_reason_and_every_route_its_permission():
    for key, exempt in EXEMPT.items():
        assert len(exempt.reason.strip()) >= 30, key
    for key, route in ROUTES.items():
        assert route.chain, key
        assert route.kind in (FORM, LIST, RESPONSE), key
        assert key[1].startswith(("/workspaces/{workspace_id}", "/{workspace_name}/")), key
    case_names = {case.name for case in CASES}
    for key, route in ROUTES.items():
        assert route.case is None or route.case in case_names, (key, route.case)


def test_the_classified_chain_matches_the_permission_matrix_rows():
    """Where a route is sent with a row of the permission matrix, the permission
    that row names is the first one this table asks (the two tables agree on
    what the route needs)."""
    by_name = {case.name: case for case in CASES}
    differing = []
    for key, route in ROUTES.items():
        case = by_name.get(route.case) if route.case else None
        if case is None or not isinstance(case.allowed, Permission):
            continue
        if case.allowed not in route.chain:
            differing.append((key, route.case, case.allowed, route.chain))
    assert not differing, differing


# -- the role facts the matrix stands on ----------------------------------------------

PINNED = frozenset({P.MEMBERS_MANAGE, P.RESPONSE_IMPORT, P.WORKSPACE_MANAGE})


def test_members_manage_response_import_and_workspace_manage_are_owner_admin_only():
    """Pinned (the review of the write phase): these three are held by Owners and
    Admins and by nobody else, and are never granted per form, so a grant or a
    restricted form can never change who holds them."""
    for role, held in ROLE_PERMISSIONS.items():
        privileged = role in (WorkspaceRoles.OWNER, WorkspaceRoles.ADMIN)
        assert (PINNED <= held) is privileged, (role, sorted(p.value for p in PINNED - held))
        if not privileged:
            assert not (held & PINNED), (role, held & PINNED)
    # the doc's table (written out in the permission matrix) says the same
    for permission in PINNED:
        assert ROLES_WITH[permission] == ADMINS, permission
    # never granted per form: no grant role holds them, they are not form-scoped
    # (what a restricted form withholds), and a grant cannot name a role that does
    for role in GRANT_ROLES:
        assert not (SERVICE_GRANT_PERMISSIONS[role] & PINNED), role
        assert not (GRANTS[role] & PINNED), role
    assert not (SERVICE_FORM_SCOPED & PINNED)
    assert not (FORM_SCOPED & PINNED)
    # the grants the model above is written from are the service's
    assert dict(SERVICE_GRANT_PERMISSIONS) == dict(GRANTS)
    assert SERVICE_FORM_SCOPED == FORM_SCOPED
    # a grant is capped by what the form-scoped set allows
    for role in GRANT_ROLES:
        assert GRANTS[role] <= FORM_SCOPED, role


# -- the world -----------------------------------------------------------------------


def _ids(ctx: dict, form=None, slug=None, response=None, response_key="response") -> dict:
    mine = response or ctx[response_key]
    return {
        "workspace_id": ctx["ws"],
        "form_id": form or ctx["form"],
        "slug": slug or ctx["slug"],
        "workspace_name": ctx["name"],
        "submission_id": mine,
        "response_id": mine,
        "action_id": ctx["random"],
        "export_id": "0" * 24,
        "import_id": ctx["random"],
        "webhook_id": ctx["random"],
        "delivery_id": ctx["random"],
        "grant_id": ctx["random"],
        "version": "1",
        "seq": "1",
        "proposal_id": "0" * 24 + "-" + "0" * 16,
        "field_id": ctx["random"],
        "template_id": ctx["template"],
    }


CASE = {case.name: case for case in CASES}


def build_request(route: Route, ctx: dict, template: str) -> Tuple[str, dict]:
    """The path and the keyword arguments of one request of the matrix."""
    kwargs: dict = {}
    case = CASE[route.case] if route.case else None
    if case is not None:
        kwargs = dict(case.request(ctx))
        if "?" in case.path:
            query = dict(parse_qsl(case.path.split("?", 1)[1]))
            kwargs["params"] = {**query, **kwargs.get("params", {})}
    if route.request is not None:
        kwargs = dict(route.request(ctx))
    return template, kwargs


@pytest.fixture()
def umami(monkeypatch):
    client = container.umami_client()
    monkeypatch.setattr(client, "fetch_stats", AsyncMock(return_value={"pageviews": 3}))
    monkeypatch.setattr(
        client,
        "fetch_pageviews",
        AsyncMock(return_value={"pageviews": [], "sessions": []}),
    )
    monkeypatch.setattr(client, "fetch_form_metrics", AsyncMock(return_value=[]))
    return client


@pytest.fixture()
async def world(matrix, workspace, umami, client, memory_jobs, monkeypatch):
    """The permission matrix's workspace (an Owner, an Admin, an Editor, a
    Reviewer, a Viewer, a Privacy officer, a published form with answers and a
    deletion request) plus three members whose grant on the form lifts or
    narrows their role. The features the routes sit behind are on."""
    users = dict(USERS)
    users["owner"], users["admin"] = USERS[OWNER], USERS[ADMIN]
    for name, role in (
        (EDITOR, "editor"),
        (REVIEWER, "reviewer"),
        (VIEWER, "viewer"),
        (PRIVACY, "privacy"),
    ):
        users[role] = USERS[name]
    for name, stored in GRANTEE_ROLE.items():
        principal = PRINCIPALS[name]
        member = await add_member(workspace, stored)
        users[name] = member
        if principal.grant and principal.team:
            team = await team_with(workspace, member)
            await grant(
                workspace, matrix["form"], team.id, principal.grant,
                export=principal.export, subject_type="group",
            )
        elif principal.grant:
            await grant(
                workspace, matrix["form"], member.id, principal.grant,
                export=principal.export,
            )
        if name == "creator_removed":
            await container.workspace_user_repo().delete(workspace.id, member.id)
    for target, name, value in (
        (settings.webhooks, "ENABLED", True),
        (settings.email_actions, "ENABLED", True),
        (settings.registration, "REGISTRATION", "on"),
        (settings.open_formulieren, "EXPORT", "on"),
        (settings.api_settings, "EDITOR_OPS_SAVE_ENABLED", True),
        (settings, "CSV_IMPORT_ENABLED", True),
        (settings, "FORM_REVISIONS_UI_ENABLED", True),
        (settings, "AUDIT_LOG_UI_ENABLED", True),
        (settings, "RESPONSE_REVISIONS_ENABLED", True),
    ):
        monkeypatch.setattr(target, name, value, raising=False)
    cookies = {name: _cookies(user) for name, user in users.items() if name in PRINCIPALS}
    ctx = dict(matrix)
    ctx.update(await real_objects(client, workspace, matrix, monkeypatch))
    return SimpleNamespace(ctx=ctx, workspace=workspace, cookies=cookies, users=users)


async def real_objects(client, workspace, matrix, monkeypatch) -> dict:
    """Real sub-objects of the matrix's form, made by the Owner while the switch
    is off, so that a route that acts on one is let through to what it does (a
    webhook, an email action, a built export and its link, an import, a grant, an
    action on the form), not to a 404 for a made-up id."""
    from backend.app.services.registration import client as registration_client
    from backend.app.services.response_export import limits, links
    from tests.app.email_actions.conftest import FakeTransport
    from tests.app.registration.tls_server import PUBLIC_ADDRESS
    from tests.app.response_import.helpers import csv_bytes
    from tests.app.webhooks.helpers import make_webhook

    async def resolve(host, port=443):
        return [PUBLIC_ADDRESS]

    monkeypatch.setattr(registration_client, "resolve", resolve)
    monkeypatch.setattr(settings.mail_settings, "smtp_server", "smtp.example.test")
    monkeypatch.setattr(settings.mail_settings, "sender", "noreply@example.test")
    monkeypatch.setattr(container.email_action_service(), "_transport", FakeTransport())  # (an email action needs a mapped team: not made here)
    monkeypatch.setattr(limits, "STREAM_MAX_ROWS", 1)
    monkeypatch.setattr(limits, "CHUNK_BYTES", 120)
    form = SimpleNamespace(form_id=matrix["form"])
    ws, owner = matrix["ws"], USERS[OWNER]
    base = f"{ROOT}/workspaces/{ws}/forms/{matrix['form']}"
    webhook = await make_webhook(workspace, form, fields=(), user=owner)
    started = await client.post(f"{base}/exports", json={}, cookies=_cookies(owner))
    assert started.status_code == 202, started.text[:150]
    export = started.json()["id"]
    assert await container.response_export_service().run_job(export) == "ready"
    uploaded = await client.post(
        f"{base}/imports",
        content=csv_bytes([["name"], ["Ada"]]),
        headers={"content-type": "text/csv"},
        cookies=_cookies(owner),
    )
    assert uploaded.status_code == 201, uploaded.text[:150]
    attached = await client.post(
        f"{base}/actions", json={"action_id": matrix["action"]}, cookies=_cookies(owner)
    )
    assert attached.status_code == 200, attached.text[:150]
    row = await grant(workspace, matrix["form"], matrix["removable"], "VIEWER")
    return {
        "webhook": str(webhook.id),
        "export": export,
        "export_token": links.issue(export, workspace.id, matrix["form"], owner.id),
        "import": uploaded.json()["id"],
        "grant": str(row.id),
        "action": matrix["action"],
    }


async def make_creator(world, name: str) -> None:
    """The form's creator (the link's user) is this principal."""
    repo = container.workspace_form_repo()
    link = await repo.find_workspace_form(world.workspace.id, str(world.ctx["form"]))
    link.user_id = str(world.users[name].id)
    await repo.save(link)


def _text(response) -> str:
    try:
        return response.text
    except Exception:  # noqa: BLE001
        return ""


def _body(response):
    try:
        return response.json()
    except ValueError:
        return response.text


async def _send(client, world, route: Route, template: str, principal: str, ghost=False):
    """One request of the matrix: ``ghost`` swaps the id the route is decided on
    (the form, the response, the slug) for one that does not exist."""
    ctx = dict(world.ctx)
    ctx["mode"] = world.mode
    unknown = str(RecordId())
    overrides = {}
    if ghost:
        if route.ghost == "slug":
            overrides["slug"] = "no-such-" + unknown[:8]
        elif route.ghost == "response":
            overrides["response"] = unknown
        else:
            overrides["form"] = unknown
    path, kwargs = build_request(route, ctx, template)
    values = _ids(ctx, **overrides, response_key=route.response_key)
    for parameter, key in route.ids:
        values[parameter] = ctx[key]
    url = ROOT + path.format(**values)
    return await client.request(
        route.method, url, cookies=world.cookies[principal], **kwargs
    )


async def run_matrix(
    client: AsyncClient,
    world,
    principals: List[str],
    mode: str,
    switch_on: bool,
) -> List[str]:
    """Every classified route as every principal; the list of what does not
    answer as the access model says."""
    world.mode = mode
    failures: List[str] = []
    # what consumes its object goes last, the response before the form it is in
    ordered = sorted(
        ROUTES.items(),
        key=lambda item: (item[1].destructive, -len(item[0][1]), item[0][1], item[0][0]),
    )
    for (method, template), route in ordered:
        route = _with(route, method=method)
        taken = False
        order = principals
        if route.destructive:
            # the refused first: the one who may consumes what the rest are refused on
            order = sorted(
                principals,
                key=lambda n: expected(route, PRINCIPALS[n], mode, switch_on) == "allowed",
            )
        for name in order:
            principal = PRINCIPALS[name]
            want = expected(route, principal, mode, switch_on)
            if route.destructive and want == "allowed":
                if taken:
                    continue
                taken = True
            label = f"{method} {template} as {name} [{mode}, switch {'on' if switch_on else 'off'}]"
            response = await _send(client, world, route, template, name)
            seen = f"{label}: {response.status_code} {str(_body(response))[:120]}"
            if response.status_code >= 500 and response.status_code != 503:
                failures.append(f"server error: {seen}")
                continue
            if route.opaque:
                if closed_to(principal, mode, switch_on):
                    ghost = await _send(client, world, route, template, name, ghost=True)
                    if (response.status_code, _body(response)) != (
                        ghost.status_code,
                        _body(ghost),
                    ):
                        failures.append(f"differs from an unknown id: {seen}")
            elif want == "allowed":
                if (
                    response.status_code == route.refused_status
                    and _body(response) == route.refused_body
                ):
                    failures.append(f"refused, expected to pass: {seen}")
                elif response.status_code == 404 and _body(response) == NOT_FOUND_BODY:
                    failures.append(f"form not found, expected to pass: {seen}")
                else:
                    OBSERVED.setdefault((method, template), set()).add(response.status_code)
                    failures.extend(
                        outcome(route, template, world, principal, label, response, mode, switch_on)
                    )
            elif want == "creator_only":
                body = _body(response)
                if not (
                    response.status_code == 403
                    and isinstance(body, dict)
                    and body.get("code") == TEMPLATE_FROM_RESTRICTED_CODE
                ):
                    failures.append(f"expected 403 {TEMPLATE_FROM_RESTRICTED_CODE}: {seen}")
            elif want == 422:
                if response.status_code != 422:
                    failures.append(f"expected 422 (switch off): {seen}")
            elif want == 403:
                if not (
                    response.status_code == route.refused_status
                    and _body(response) == route.refused_body
                ):
                    failures.append(f"expected {route.refused_status}, got: {seen}")
            else:
                ghost = await _send(client, world, route, template, name, ghost=True)
                if response.status_code != route.closed_status:
                    failures.append(f"expected {route.closed_status}, got: {seen}")
                elif (response.status_code, _body(response)) != (
                    ghost.status_code,
                    _body(ghost),
                ):
                    failures.append(
                        f"404 differs from an unknown id ({ghost.status_code} "
                        f"{str(_body(ghost))[:80]}): {seen}"
                    )
    return failures


#: the statuses the allowed members were answered with, per route (calibration)
OBSERVED: Dict[Tuple[str, str], Set[int]] = {}

# a workspace list names a form (or its answers) to the member who holds this
# permission on it, and to nobody else
LIST_PRESENCE = {
    ("GET", "/workspaces/{workspace_id}/forms"): (P.FORM_READ, "form"),
    ("GET", "/workspaces/{workspace_id}/all-submissions"): (P.RESPONSE_READ, "response"),
}


def outcome(
    route: Route, template: str, world, principal, label, response, mode, switch_on
) -> List[str]:
    """What an allowed member is answered: a status the route gives once it has
    been let through (``Route.ok``), the data it is meant to return
    (``Route.check``), and, for a list, the form or its answers exactly when the
    member holds the permission on them."""
    failures: List[str] = []
    seen = f"{label}: {response.status_code} {str(_body(response))[:100]}"
    if route.ok and response.status_code not in route.ok:
        failures.append(f"outcome {response.status_code} not in {route.ok}: {seen}")
    if route.check is not None and 200 <= response.status_code < 300:
        problem = route.check(world.ctx, response)
        if problem:
            failures.append(f"data: {problem}: {seen}")
    if route.kind == LIST:
        failures.extend(leaks(world, principal, label, response, mode, switch_on))
        presence = LIST_PRESENCE.get((route.method, template))
        if presence and response.status_code == 200:
            permission, what = presence
            held = held_on_form(principal, mode, switch_on)
            identifier = str(world.ctx["form" if what == "form" else "response"])
            named = identifier in _text(response)
            if (permission in held) and not named:
                failures.append(f"the list leaves out what the member may open: {seen}")
    return failures


def leaks(world, principal: Principal, label, response, mode, switch_on) -> List[str]:
    """A list a member reads must not carry a form (or its answers) they have no
    way into."""
    if response.status_code != 200 or principal.privileged or principal.privacy:
        return []
    if not closed_to(principal, mode, switch_on):
        return []
    text = _text(response)
    named = [
        i
        for i in (world.ctx["form"], world.ctx["response"], world.ctx["requested"])
        if str(i) in text
    ]
    return [f"leaks a closed form: {label} ({len(named)} ids)"] if named else []


def _with(route: Route, **fields) -> Route:
    values = {f: getattr(route, f) for f in route.__dataclass_fields__}
    values.update(fields)
    return Route(**values)




# -- the matrix, per mode ------------------------------------------------------------

EVERY = NON_CREATORS
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
OFF_SET = NON_CREATORS  # every principal: with the switch off the grants are inert


async def test_the_matrix_on_a_restricted_form(client: AsyncClient, world, monkeypatch):
    """Switch on, the form restricted: nine members, every classified route."""
    await set_mode(world.workspace, world.ctx["form"], MODE_RESTRICTED)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    failures = await run_matrix(
        client, world, EVERY, MODE_RESTRICTED, True
    )
    assert not failures, "\n".join(failures[:60]) + f"\n({len(failures)} in all)"


async def test_the_matrix_on_an_open_form(client: AsyncClient, world, monkeypatch):
    """Switch on, the form open to the workspace: a grant lifts a role, nothing
    is closed to anyone."""
    await set_mode(world.workspace, world.ctx["form"], MODE_WORKSPACE)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    failures = await run_matrix(
        client, world, OPEN_SET, MODE_WORKSPACE, True
    )
    assert not failures, "\n".join(failures[:60]) + f"\n({len(failures)} in all)"


async def test_the_matrix_with_the_switch_off(client: AsyncClient, world, monkeypatch):
    """Switch off: the stored mode and grants are ignored, the workspace role
    decides as it did before form-level access (and the routes that change
    grants or the mode answer 422)."""
    await set_mode(world.workspace, world.ctx["form"], MODE_RESTRICTED)
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    failures = await run_matrix(
        client, world, OFF_SET, MODE_RESTRICTED, False
    )
    assert not failures, "\n".join(failures[:60]) + f"\n({len(failures)} in all)"


@pytest.mark.parametrize(
    "creator,switch_on",
    [
        ("creator_editor", True),
        ("creator_viewer", True),
        ("creator_removed", True),
        ("creator_removed", False),
    ],
)
async def test_the_matrix_for_the_forms_creator(
    client: AsyncClient, world, monkeypatch, creator, switch_on
):
    """The member who made the form: on a restricted form they keep what their own
    role gives (an Editor everything, a demoted creator only a Viewer's reads, a
    creator whose membership is gone nothing), never more; run on a form they
    created, with the switch on and off."""
    await set_mode(world.workspace, world.ctx["form"], MODE_RESTRICTED)
    await make_creator(world, creator)
    monkeypatch.setattr(settings.form_access, "ENABLED", switch_on)
    failures = await run_matrix(client, world, [creator], MODE_RESTRICTED, switch_on)
    assert not failures, "\n".join(failures[:60]) + f"\n({len(failures)} in all)"


async def test_a_closed_member_reads_a_version_as_the_public_does(
    client: AsyncClient, world, monkeypatch
):
    """``GET .../versions/{version}`` is the published read shared with the
    public: a member a restricted form is closed to sees what anyone sees (the
    respondent's view), never the builder's; staff who may open the form do."""
    await set_mode(world.workspace, world.ctx["form"], MODE_RESTRICTED)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    ws, form = world.ctx["ws"], world.ctx["form"]
    url = f"{ROOT}/workspaces/{ws}/forms/{form}/versions/1"
    public = await client.get(url)
    closed = await client.get(url, cookies=world.cookies["editor"])
    assert (closed.status_code, _body(closed)) == (public.status_code, _body(public))
    for name in ("owner", "admin", "viewer_editor_grant"):
        staff = await client.get(url, cookies=world.cookies[name])
        assert staff.status_code == 200, (name, staff.status_code, _body(staff))


async def test_the_signature_image_of_a_closed_form_is_the_404_of_an_unknown_response(
    client: AsyncClient, workspace, signed_form, store, monkeypatch
):
    """The signature route answers every refusal with the same 404 (so the matrix
    cannot tell a refused member from one who may read): here with a real drawn
    signature on a restricted form."""
    form_id = signed_form.form_id
    response_id = await _drawn_response(client, workspace, form_id)
    await set_mode(workspace, form_id, MODE_RESTRICTED)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    editor = await add_member(workspace, "COLLABORATOR")
    viewer = await add_member(workspace, "VIEWER")
    granted = await add_member(workspace, "VIEWER")
    await grant(workspace, form_id, granted.id, "VIEWER")
    admin = await add_member(workspace, "ADMIN")
    unknown = await client.get(
        _signature_route(workspace, str(RecordId())), cookies=_cookies(editor)
    )
    assert unknown.status_code == 404
    for user in (editor, viewer):
        got = await client.get(
            _signature_route(workspace, response_id), cookies=_cookies(user)
        )
        assert (got.status_code, got.text) == (unknown.status_code, unknown.text)
    for user in (granted, admin):
        got = await client.get(
            _signature_route(workspace, response_id), cookies=_cookies(user)
        )
        assert got.status_code == 200 and got.content.startswith(b"\x89PNG"), user.sub
