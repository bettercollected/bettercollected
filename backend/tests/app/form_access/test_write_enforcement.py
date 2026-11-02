"""Form-level access on the WRITE side: every route that changes a form, its
settings, its automations or its structure decides on the form.

The rows are the form-acting rows of the permission matrix
(``tests/app/controllers/test_permission_matrix.py``), run against a published
form that is restricted to two people with a grant. With
``FORM_ACCESS_ENABLED`` on:

* a member the form is closed to gets the 404 of a form that is not there when
  their role holds the permission, and the usual 403 when it lacks it;
* a grantee gets exactly what the grant gives (an Editor grant edits, shares and
  exports but never deletes the form; a Reviewer grant annotates only);
* Owners and Admins always pass;
* a copy (duplicate) of a restricted form stays restricted.
"""

from types import SimpleNamespace
from typing import Dict, FrozenSet, List
from unittest.mock import AsyncMock

import pytest
from common.constants import MESSAGE_FORBIDDEN
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import ROLE_EDITOR, ROLE_REVIEWER
from backend.app.services.form_access.model import (
    GRANT_PERMISSIONS,
    MODE_RESTRICTED,
    MODE_WORKSPACE,
)
from backend.app.services.authorization_service import EDITOR_PERMISSIONS
from backend.config import settings
from tests.app.controllers.data import testUser
from tests.app.controllers.test_permission_matrix import (  # noqa: F401
    ADMIN,
    CASES,
    COLLABORATOR,
    EDITOR,
    OWNER,
    PRIVACY,
    REVIEWER,
    ROLES_WITH,
    USERS,
    VIEWER,
    Case,
    _cookies,
    matrix,
    outside_services,
    scim_on,
)
from tests.app.sso_helpers import sso_on  # noqa: F401
from tests.app.form_access.helpers import add_member, grant, restrict, set_mode

P = Permission
NOT_FOUND_BODY = "Form not found in workspace"

# the form-acting rows this phase decides on the form (name -> the permissions
# the service asks, in order, when one row asks several)
WRITE_ROWS: Dict[str, List[Permission]] = {
    "forms.update": [P.FORM_EDIT],
    "forms.logo.upload": [P.FORM_EDIT],
    "forms.logo.remove": [P.FORM_EDIT],
    "forms.duplicate": [P.FORM_CREATE, P.FORM_READ],
    "forms.publish": [P.FORM_EDIT],
    "forms.delete": [P.FORM_DELETE],
    "forms.settings": [P.FORM_EDIT],
    "forms.settings.feedback": [P.FORM_EDIT],
    "forms.settings.hidden": [P.FORM_EDIT, P.FORM_SHARE],
    "forms.settings.private": [P.FORM_EDIT, P.FORM_SHARE],
    "forms.groups.add": [P.FORM_EDIT],
    "forms.groups.remove": [P.FORM_EDIT],
    "forms.actions.add": [P.FORM_EDIT, P.RESPONSE_EXPORT],
    "forms.actions.update": [P.FORM_EDIT],
    "forms.actions.remove": [P.FORM_EDIT],
    "forms.as_template": [P.FORM_CREATE, P.FORM_EDIT],
    "ai.chat": [P.FORM_EDIT],
    "ai.review": [P.FORM_EDIT],
    "ai.proposal.accept": [P.FORM_EDIT],
    "ai.proposal.reject": [P.FORM_EDIT],
    "ai.insights.get": [P.RESPONSE_READ],
    "ai.insights.generate": [P.RESPONSE_READ],
    "ai.insights.settings": [P.AI_MANAGE],
    "spec.dry_run": [P.FORM_EDIT],
    "forms.ops.save": [P.FORM_EDIT],
    "forms.versions.restore": [P.FORM_EDIT],
    "forms.open_formulieren_export": [P.FORM_READ],
}
ROWS = [case for case in CASES if case.name in WRITE_ROWS]
# a form that is deleted cannot be deleted by the next principal
DESTRUCTIVE = {"forms.delete"}

GRANTEE_EDITOR, GRANTEE_REVIEWER, GRANTEE_COLLABORATOR = (
    "grantee_editor",
    "grantee_reviewer",
    "grantee_collaborator",
)
NON_FORM_SCOPED_OF_ROLE = {
    # what a role keeps on a restricted form it has no way into (nothing
    # form-scoped; what its role gives otherwise)
    GRANTEE_EDITOR: frozenset(),  # a Viewer
    GRANTEE_REVIEWER: frozenset(),  # a Viewer
    GRANTEE_COLLABORATOR: frozenset({P.FORM_CREATE}),  # an Editor
}
GRANT_ROLE = {
    GRANTEE_EDITOR: ROLE_EDITOR,
    GRANTEE_REVIEWER: ROLE_REVIEWER,
    GRANTEE_COLLABORATOR: ROLE_EDITOR,
}
BASE_ROLE = {
    GRANTEE_EDITOR: "VIEWER",
    GRANTEE_REVIEWER: "VIEWER",
    GRANTEE_COLLABORATOR: "COLLABORATOR",
}
CLOSED_ROLES = (EDITOR, COLLABORATOR, REVIEWER, VIEWER, PRIVACY)
GRANTEES = (GRANTEE_EDITOR, GRANTEE_REVIEWER, GRANTEE_COLLABORATOR)


@pytest.fixture()
async def closed(matrix, workspace, monkeypatch):
    """The matrix's published form, restricted, with grants to three members;
    the switch is on."""
    users = {}
    for key in GRANTEES:
        users[key] = await add_member(workspace, BASE_ROLE[key])
        await grant(workspace, matrix["form"], users[key].id, GRANT_ROLE[key])
    await restrict(workspace, matrix["form"])
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    return SimpleNamespace(matrix=matrix, workspace=workspace, grantees=users)


def _user(closed, who):
    return closed.grantees[who] if who in closed.grantees else USERS[who]


def _held(who) -> FrozenSet[Permission]:
    """What ``who`` holds on the restricted form, written from the access
    model (not read from the service): grantees what the grant gives, a Privacy
    officer the structure and the privacy programme, owners and admins
    everything, anyone else only what is not about one form."""
    if who in (OWNER, ADMIN):
        return frozenset(Permission)
    if who in GRANTEES:
        return NON_FORM_SCOPED_OF_ROLE[who] | GRANT_PERMISSIONS[GRANT_ROLE[who]]
    if who == PRIVACY:
        return frozenset({P.FORM_READ, P.PRIVACY_MANAGE, P.AUDIT_READ})
    return frozenset(
        p for p in (P.FORM_CREATE,) if who in ROLES_WITH[p]
    )  # editors keep form.create; the rest hold nothing here


def _closed(who) -> bool:
    """The form reads as not there to this member (they hold form.read by their
    role and have no way in)."""
    return who in (EDITOR, COLLABORATOR, REVIEWER, VIEWER)


def _role_holds(who, permission) -> bool:
    """Whether the member's workspace ROLE (before any grant) holds it."""
    if who in GRANTEES:
        if BASE_ROLE[who] == "VIEWER":
            return permission in {P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ}
        return permission in EDITOR_PERMISSIONS
    return who in ROLES_WITH[permission]


def _expected(who, chain):
    """``allowed`` or the refusal (404 or 403) the first permission of the chain
    the member lacks gives."""
    held = _held(who)
    for permission in chain:
        if permission not in held:
            if _closed(who) and _role_holds(who, permission):
                return 404
            return 403
    return "allowed"


async def _send(client, closed, case: Case, who, monkeypatch, form=None):
    for name, value in (case.api_settings or {}).items():
        monkeypatch.setattr(settings.api_settings, name, value)
    if case.open_formulieren_export:
        monkeypatch.setattr(
            settings.open_formulieren, "EXPORT", case.open_formulieren_export
        )
    for name, value in (case.switches or {}).items():
        monkeypatch.setattr(settings, name, value)
    context = dict(closed.matrix)
    if form is not None:
        context["form"] = form
    return await client.request(
        case.method,
        case.path.format(**context),
        cookies=_cookies(_user(closed, who)),
        **case.request(context),
    )


def _body(response):
    try:
        return response.json()
    except ValueError:
        return response.text


@pytest.mark.parametrize("case", ROWS, ids=[case.name for case in ROWS])
async def test_a_restricted_form_is_decided_on_the_form_by_every_write_row(
    client: AsyncClient, closed, monkeypatch, case: Case
):
    chain = WRITE_ROWS[case.name]
    unknown_form = str(RecordId())
    refused_first = [
        who
        for who in (*CLOSED_ROLES, *GRANTEES)
        if _expected(who, chain) != "allowed"
    ]
    allowed = [
        who
        for who in (*GRANTEES, ADMIN, OWNER)
        if _expected(who, chain) == "allowed"
    ]
    if case.name in DESTRUCTIVE:
        allowed = allowed[:1]
    for who in (*refused_first, *allowed):
        response = await _send(client, closed, case, who, monkeypatch)
        seen = f"{case.name} as {who}: {response.status_code} {response.text}"
        expected = _expected(who, chain)
        if expected == 404:
            assert response.status_code == 404, seen
            # exactly what an id that does not exist answers
            gone = await _send(client, closed, case, who, monkeypatch, form=unknown_form)
            assert (response.status_code, _body(response)) == (
                gone.status_code,
                _body(gone),
            ), seen
        elif expected == 403:
            assert response.status_code == 403, seen
            assert _body(response) == MESSAGE_FORBIDDEN, seen
        else:
            # past the access decision: whatever the row itself answers, never
            # an access refusal and never an error
            assert not (
                response.status_code == 403 and _body(response) == MESSAGE_FORBIDDEN
            ), seen
            assert not (
                response.status_code == 404 and _body(response) == NOT_FOUND_BODY
            ), seen
            assert response.status_code < 500 or response.status_code == 503, seen


async def test_an_editor_grant_never_deletes_the_form(client: AsyncClient, closed):
    """A member whose workspace role can delete forms but who holds an Editor
    grant on a restricted form still cannot delete it: the grant gives the
    content permissions, not deletion. The Admin can."""
    url = f"/api/v1/workspaces/{closed.matrix['ws']}/forms/{closed.matrix['form']}"
    for who in (GRANTEE_COLLABORATOR, GRANTEE_EDITOR):
        response = await client.delete(url, cookies=_cookies(_user(closed, who)))
        assert response.status_code == 403, (who, response.text)
    assert (
        await container.workspace_form_repo().find_workspace_form(
            closed.workspace.id, closed.matrix["form"]
        )
        is not None
    )
    assert (
        await client.delete(url, cookies=_cookies(USERS[ADMIN]))
    ).status_code == 200


# -- a copy of a restricted form stays restricted -------------------------------


async def _link(closed, form_id):
    return await container.workspace_form_repo().find_workspace_form(
        closed.workspace.id, str(form_id)
    )


async def test_a_duplicate_of_a_restricted_form_is_restricted(closed):
    service = container.workspace_form_service()
    copy = await service.duplicate_form(
        closed.workspace.id, closed.matrix["form"], _user(closed, ADMIN)
    )
    link = await _link(closed, copy.form_id)
    assert link.settings.access_mode == MODE_RESTRICTED
    # no grant comes along
    assert (
        await container.form_access_grant_repo().list_for_form(
            closed.workspace.id, copy.form_id
        )
        == []
    )
    # the creator of the copy keeps it, a member who was never let in does not
    editor = _user(closed, EDITOR)
    assert (
        Permission.FORM_READ
        not in await container.authorization_service().effective_permissions(
            editor, closed.workspace.id, form_id=str(copy.form_id)
        )
    )


async def test_a_grantee_who_duplicates_owns_a_restricted_copy(closed):
    grantee = _user(closed, GRANTEE_COLLABORATOR)
    copy = await container.workspace_form_service().duplicate_form(
        closed.workspace.id, closed.matrix["form"], grantee
    )
    link = await _link(closed, copy.form_id)
    assert link.settings.access_mode == MODE_RESTRICTED
    assert str(link.user_id) == str(grantee.id)
    held = await container.authorization_service().effective_permissions(
        grantee, closed.workspace.id, form_id=str(copy.form_id)
    )
    assert Permission.FORM_EDIT in held


async def test_a_duplicate_of_an_open_form_is_open(closed):
    await set_mode(closed.workspace, closed.matrix["form"], MODE_WORKSPACE)
    copy = await container.workspace_form_service().duplicate_form(
        closed.workspace.id, closed.matrix["form"], _user(closed, ADMIN)
    )
    assert (await _link(closed, copy.form_id)).settings.access_mode is None


async def test_a_duplicate_of_a_private_form_is_restricted_while_the_switch_is_on(
    closed, monkeypatch
):
    """A Private (hidden) form with no mode chosen reads as restricted, so its
    copy is restricted too, by an explicit mode (the copy is not itself hidden)."""
    # no mode chosen: written with the switch off (a save keeps the stored mode
    # while it is on)
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    link = await _link(closed, closed.matrix["form"])
    link.settings.access_mode = None
    link.settings.hidden = True
    await container.workspace_form_repo().save(link)
    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    copy = await container.workspace_form_service().duplicate_form(
        closed.workspace.id, closed.matrix["form"], _user(closed, ADMIN)
    )
    assert (await _link(closed, copy.form_id)).settings.access_mode == MODE_RESTRICTED
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    off = await container.workspace_form_service().duplicate_form(
        closed.workspace.id, closed.matrix["form"], _user(closed, ADMIN)
    )
    assert (await _link(closed, off.form_id)).settings.access_mode is None


async def test_the_stored_mode_is_inherited_with_the_switch_off_too(closed, monkeypatch):
    """Turning the switch on later must not find an open copy of a form that was
    restricted when it was copied."""
    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    copy = await container.workspace_form_service().duplicate_form(
        closed.workspace.id, closed.matrix["form"], _user(closed, ADMIN)
    )
    assert (await _link(closed, copy.form_id)).settings.access_mode == MODE_RESTRICTED


# -- the delivery logs ------------------------------------------------------------


@pytest.mark.parametrize("kind", ["webhooks", "email-actions"])
async def test_a_privacy_officer_reads_no_delivery_log_of_a_restricted_form(
    client: AsyncClient, closed, monkeypatch, kind
):
    """audit.read alone opens the log of an open form; on a restricted form it
    needs form.edit on it (owners and admins and grantees who may edit do)."""
    monkeypatch.setattr(settings.webhooks, "ENABLED", True)
    monkeypatch.setattr(settings.email_actions, "ENABLED", True)
    ws, form = closed.matrix["ws"], closed.matrix["form"]
    url = f"/api/v1/workspaces/{ws}/forms/{form}/{kind}/deliveries"
    officer = _cookies(USERS[PRIVACY])
    assert (await client.get(url, cookies=officer)).status_code == 403
    for who in (ADMIN, OWNER, GRANTEE_EDITOR):
        response = await client.get(url, cookies=_cookies(_user(closed, who)))
        assert response.status_code == 200, (who, response.text)
    for who in (GRANTEE_REVIEWER, VIEWER):
        response = await client.get(url, cookies=_cookies(_user(closed, who)))
        assert response.status_code in (403, 404), (who, response.text)
    # a member who may edit forms by role is closed out like any unknown form
    assert (
        await client.get(url, cookies=_cookies(USERS[EDITOR]))
    ).status_code == 404
    # open again: the officer's audit.read opens the log as it always did
    await set_mode(closed.workspace, form, MODE_WORKSPACE)
    assert (await client.get(url, cookies=officer)).status_code == 200


async def test_the_registration_delivery_log_is_closed_to_a_member_without_access(
    client: AsyncClient, closed, monkeypatch
):
    monkeypatch.setattr(settings.registration, "REGISTRATION", "on")
    ws, form = closed.matrix["ws"], closed.matrix["form"]
    url = f"/api/v1/workspaces/{ws}/forms/{form}/registration/deliveries"
    assert (
        await client.get(url, cookies=_cookies(USERS[EDITOR]))
    ).status_code == 404
    assert (
        await client.get(url, cookies=_cookies(_user(closed, GRANTEE_EDITOR)))
    ).status_code == 200


# -- reads that were left open ----------------------------------------------------


async def test_the_reconsent_read_of_an_action_is_closed_to_a_member_without_access(
    client: AsyncClient, closed
):
    ws, form = closed.matrix["ws"], closed.matrix["form"]
    url = f"/api/v1/workspaces/{ws}/forms/{form}/actions/{closed.matrix['action']}/reconsent"
    assert (
        await client.get(url, cookies=_cookies(USERS[EDITOR]))
    ).status_code == 404
    # a grantee who edits the form is past the gate (the action is not on the
    # form, which is a 404 with another body)
    response = await client.get(
        url, cookies=_cookies(_user(closed, GRANTEE_EDITOR))
    )
    assert _body(response) != NOT_FOUND_BODY
    assert (
        await client.get(url, cookies=_cookies(_user(closed, GRANTEE_REVIEWER)))
    ).status_code == 403


async def test_the_editor_etag_of_a_closed_form_is_never_computed(
    client: AsyncClient, closed, monkeypatch
):
    monkeypatch.setattr(settings.api_settings, "EDITOR_OPS_SAVE_ENABLED", True)
    service = container.editor_ops_service()
    etag = AsyncMock(wraps=service._etag_of)
    monkeypatch.setattr(service, "_etag_of", etag)
    ws, form = closed.workspace.id, closed.matrix["form"]
    assert await service.etag_for_editor(USERS[EDITOR], ws, form) is None
    etag.assert_not_called()
    assert await service.etag_for_editor(_user(closed, GRANTEE_EDITOR), ws, form)
    assert await service.etag_for_editor(USERS[ADMIN], ws, form)


async def test_an_option_source_names_a_closed_form_as_a_form_that_does_not_exist(
    closed, monkeypatch
):
    from backend.app.exceptions import HTTPException

    service = container.option_source_service()
    source = {"kind": "form_answers", "form_id": closed.matrix["form"], "question_id": "x"}
    with pytest.raises(HTTPException) as refused:
        await service.authorize_source(
            closed.workspace.id, source, _user(closed, EDITOR), own_form_id=None
        )
    assert "does not exist" in str(refused.value.content)


async def test_the_billing_owner_can_read_every_restricted_form(closed):
    """The Sheets reconnect mail goes to the billing owner: an owner always
    holds the form, so a restricted form's title never reaches anyone who may
    not read it."""
    holders = await container.authorization_service().member_ids_holding(
        closed.workspace.id, closed.matrix["form"], Permission.FORM_READ
    )
    assert str(testUser.id) in holders
    assert str(_user(closed, EDITOR).id) not in holders
    assert str(_user(closed, GRANTEE_REVIEWER).id) in holders


async def test_the_stats_count_deletion_requests_by_the_privacy_permission(
    client: AsyncClient, closed
):
    """A Privacy officer counts the deletion requests of a restricted form (the
    privacy programme), a member who may not open it counts none."""
    url = f"/api/v1/workspaces/{closed.matrix['ws']}/stats"
    seen = {}
    for who in (PRIVACY, ADMIN, EDITOR):
        response = await client.get(url, cookies=_cookies(USERS[who]))
        assert response.status_code == 200, (who, response.text)
        seen[who] = response.json()["deletionRequests"]["total"]
    assert seen == {PRIVACY: 1, ADMIN: 1, EDITOR: 0}


async def test_who_may_read_a_form_is_decided_with_a_fixed_number_of_queries(
    closed, monkeypatch
):
    from tests.app.form_access.test_switch_and_memo import statements

    authorization = container.authorization_service()
    for _ in range(6):
        await add_member(closed.workspace, "VIEWER")
    with statements() as few:
        await authorization.member_ids_holding(
            closed.workspace.id, closed.matrix["form"], Permission.FORM_READ
        )
    for _ in range(6):
        await add_member(closed.workspace, "VIEWER")
    with statements() as more:
        await authorization.member_ids_holding(
            closed.workspace.id, closed.matrix["form"], Permission.FORM_READ
        )
    assert len(more) == len(few)


# -- switch off: nothing changes ---------------------------------------------------

# Statements per request with the switch off, measured on the commit before the
# write side was enforced (for a second request of the same kind, an Admin and
# an Editor alike; the delete is a single request). A change that adds a query
# while the switch is off has to raise a number here knowingly.
OFF_WRITE_STATEMENTS = {
    "forms.update": 7,
    "forms.publish": 9,
    "forms.settings": 8,
    "forms.settings.hidden": 8,
    "forms.actions.update": 7,
    "forms.groups.add": 11,
    "forms.duplicate": 6,
    "forms.logo.remove": 6,
    "spec.dry_run": 4,
    "forms.versions.restore": 9,
    "forms.delete": 33,
}


async def test_off_the_write_rows_run_no_more_statements_than_before(
    client: AsyncClient, closed, monkeypatch
):
    from tests.app.form_access.test_switch_and_memo import (
        statements,
        touching_new_tables,
    )

    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    # a form that never had an access mode (a copy of one that has takes one more
    # write, whatever the switch says: see the inheritance tests)
    link = await _link(closed, closed.matrix["form"])
    link.settings.access_mode = None
    await container.workspace_form_repo().save(link)
    by_name = {case.name: case for case in CASES}
    measured = {}
    for name in OFF_WRITE_STATEMENTS:
        counts = []
        for who in (ADMIN, EDITOR):
            case = by_name[name]
            if name == "forms.delete" and who == EDITOR:
                continue
            if name != "forms.delete":
                await _send(client, closed, case, who, monkeypatch)  # warm
            with statements() as seen:
                response = await _send(client, closed, case, who, monkeypatch)
            assert response.status_code < 500, (name, who, response.text)
            assert not touching_new_tables(seen), (name, who)
            counts.append(len(seen))
        measured[name] = max(counts)
    for name, limit in OFF_WRITE_STATEMENTS.items():
        assert measured[name] <= limit, (name, measured[name], limit)
