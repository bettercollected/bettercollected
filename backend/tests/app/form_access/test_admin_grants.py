"""Grants on a form and a form's access mode: the routes, the grantor's caps,
the checks inside the workspace and the audit trail. Everything is synthetic."""

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.workspace_audit_event import (
    ACCESS_GRANT_ADDED,
    ACCESS_GRANT_CHANGED,
    ACCESS_GRANT_REMOVED,
    ACCESS_MODE_CHANGED,
)
from backend.app.services.form_access.model import FormPermissions, MODE_RESTRICTED
from tests.app.controllers.data import testUser, testUser1
from tests.app.form_access.test_switch_and_memo import statements, touching_new_tables
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    create_form,
    fail_audit,
    grant,
    restrict,
    team_with,
)

pytestmark = pytest.mark.asyncio
P = Permission


def form_url(workspace, form, tail="") -> str:
    return f"{api(workspace)}/forms/{form.form_id}{tail}"


async def put_grant(client, workspace, form, user, subject_id, role, subject_type="user", **extra):
    return await client.put(
        form_url(workspace, form, "/grants"),
        cookies=cookies(user),
        json={"subjectType": subject_type, "subjectId": str(subject_id), "role": role, **extra},
    )


async def stored(workspace, form):
    return await container.form_access_grant_repo().list_for_form(
        workspace.id, form.form_id
    )


async def link_mode(workspace, form):
    link = await container.workspace_form_repo().find_workspace_form(
        workspace.id, form.form_id
    )
    return link.settings.access_mode


# -- the switch -----------------------------------------------------------------
async def test_the_form_routes_answer_422_while_the_switch_is_off_and_get_says_so(
    client: AsyncClient, workspace, workspace_form, switch_off
):
    member = await add_member(workspace, "VIEWER")
    form = workspace_form
    calls = [
        ("PUT", "/grants", {"subjectType": "user", "subjectId": member.id, "role": "VIEWER"}),
        ("PUT", "/access/mode", {"mode": "restricted"}),
        ("DELETE", "/grants/" + "0" * 24, None),
    ]
    for method, tail, body in calls:
        response = await client.request(
            method, form_url(workspace, form, tail), cookies=cookies(testUser), json=body
        )
        assert response.status_code == 422, (tail, response.text)
        assert response.json()["code"] == "form_access_off"
    got = await client.get(form_url(workspace, form, "/access"), cookies=cookies(testUser))
    assert got.status_code == 200 and got.json() == {
        "enabled": False,
        "accessMode": None,
        "restricted": False,
        "myPermissions": [],
        "source": None,
        "canManage": False,
        "grants": None,
    }
    assert await stored(workspace, form) == []
    assert await link_mode(workspace, form) is None
    assert not await audit_events(workspace)


async def test_the_permissions_answer_says_whether_form_access_is_on(
    client: AsyncClient, workspace, monkeypatch
):
    url = f"{api(workspace)}/permissions"
    off = await client.get(url, cookies=cookies(testUser))
    assert off.json()["formAccessEnabled"] is False
    from backend.config import settings

    monkeypatch.setattr(settings.form_access, "ENABLED", True)
    on = await client.get(url, cookies=cookies(testUser))
    assert on.json()["formAccessEnabled"] is True


async def test_with_the_switch_off_existing_reads_touch_none_of_the_new_tables(
    client: AsyncClient, workspace, workspace_form, switch_off
):
    with statements() as seen:
        permissions = await client.get(
            f"{api(workspace)}/permissions", cookies=cookies(testUser)
        )
        await container.authorization_service().authorize(
            testUser, Permission.FORM_READ, workspace.id, form_id=workspace_form.form_id
        )
    assert permissions.status_code == 200
    assert touching_new_tables(seen) == []


# -- reading --------------------------------------------------------------------
async def test_the_access_summary_for_an_owner_lists_the_circle(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, name="Hiring")
    await grant(workspace, workspace_form.form_id, person.id, "REVIEWER", export=True)
    await grant(workspace, workspace_form.form_id, team.id, "VIEWER", subject_type="group")
    response = await client.get(
        form_url(workspace, workspace_form, "/access"), cookies=cookies(testUser)
    )
    body = response.json()
    assert body["enabled"] is True and body["restricted"] is False
    assert body["canManage"] is True and body["source"] == "role"
    assert Permission.FORM_SHARE.value in body["myPermissions"]
    by_subject = {g["subjectId"]: g for g in body["grants"]}
    assert by_subject[person.id]["role"] == "REVIEWER" and by_subject[person.id]["export"]
    assert by_subject[str(team.id)]["name"] == "Hiring"
    assert by_subject[str(team.id)]["subjectType"] == "group"


async def test_a_reader_without_share_sees_the_mode_and_their_rights_but_not_the_circle(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    viewer = await add_member(workspace, "VIEWER")
    other = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, other.id, "REVIEWER")
    body = (
        await client.get(
            form_url(workspace, workspace_form, "/access"), cookies=cookies(viewer)
        )
    ).json()
    assert body["grants"] is None and body["canManage"] is False
    assert Permission.FORM_READ.value in body["myPermissions"]


async def test_a_restricted_form_is_unknown_to_a_member_without_a_way_in(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    await restrict(workspace, workspace_form.form_id)
    stranger = await add_member(workspace, "COLLABORATOR")
    for method, tail, body in (
        ("GET", "/access", None),
        ("PUT", "/access/mode", {"mode": "workspace"}),
        ("PUT", "/grants", {"subjectType": "user", "subjectId": stranger.id, "role": "VIEWER"}),
        ("DELETE", "/grants/" + "0" * 24, None),
    ):
        response = await client.request(
            method, form_url(workspace, workspace_form, tail), cookies=cookies(stranger), json=body
        )
        assert response.status_code == 404, (method, tail, response.text)
    assert await link_mode(workspace, workspace_form) == MODE_RESTRICTED
    assert not await stored(workspace, workspace_form)


# -- putting a grant ------------------------------------------------------------------
async def test_an_owner_grants_changes_and_removes_a_role(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    added = await put_grant(client, workspace, workspace_form, testUser, person.id, "VIEWER")
    assert added.status_code == 200, added.text
    body = added.json()
    assert (body["subjectType"], body["subjectId"], body["role"], body["export"]) == (
        "user",
        person.id,
        "VIEWER",
        False,
    )
    assert body["createdBy"] == testUser.id

    changed = await put_grant(
        client, workspace, workspace_form, testUser, person.id, "REVIEWER", export=True
    )
    assert changed.status_code == 200 and changed.json()["id"] == body["id"]
    (row,) = await stored(workspace, workspace_form)
    assert (row.role, row.export, row.created_by) == ("REVIEWER", True, testUser.id)

    removed = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{body['id']}"),
        cookies=cookies(testUser),
    )
    assert removed.status_code == 204
    assert await stored(workspace, workspace_form) == []

    events = await audit_events(workspace)
    assert [e.event for e in events] == [
        ACCESS_GRANT_ADDED,
        ACCESS_GRANT_CHANGED,
        ACCESS_GRANT_REMOVED,
    ]
    added_row, changed_row, removed_row = events
    assert added_row.form_id == workspace_form.form_id
    assert (added_row.target_user_id, added_row.grant_role, added_row.grant_export) == (
        person.id,
        "VIEWER",
        False,
    )
    assert (changed_row.grant_role, changed_row.grant_export) == ("REVIEWER", True)
    assert removed_row.target_user_id == person.id
    assert all(e.user_id == testUser.id for e in events)


async def test_a_grant_to_a_team_is_audited_with_the_team_id(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    team = await team_with(workspace, name="Hiring")
    response = await put_grant(
        client, workspace, workspace_form, testUser, team.id, "EDITOR", subject_type="group"
    )
    assert response.status_code == 200, response.text
    (event,) = await audit_events(workspace, ACCESS_GRANT_ADDED)
    assert event.group_id == str(team.id) and event.target_user_id is None
    assert "Hiring" not in str(event.model_dump(mode="json"))


async def test_an_editor_grant_does_not_store_the_export_flag(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    response = await put_grant(
        client, workspace, workspace_form, testUser, person.id, "EDITOR", export=True
    )
    assert response.status_code == 200
    assert response.json()["export"] is False


async def test_the_grant_changes_what_the_person_may_do_at_once(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    authz = container.authorization_service()
    assert P.FORM_EDIT not in await authz.effective_permissions(
        person, workspace.id, form_id=workspace_form.form_id
    )
    await put_grant(client, workspace, workspace_form, testUser, person.id, "EDITOR")
    assert P.FORM_EDIT in await authz.effective_permissions(
        person, workspace.id, form_id=workspace_form.form_id
    )


# -- the grantor's caps ---------------------------------------------------------------------
async def test_an_editor_grants_within_their_own_role_but_never_export(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    editor = await add_member(workspace, "COLLABORATOR")
    person = await add_member(workspace, "VIEWER")
    for role in ("VIEWER", "REVIEWER", "EDITOR"):
        ok = await put_grant(client, workspace, workspace_form, editor, person.id, role)
        assert ok.status_code == 200, (role, ok.text)
    denied = await put_grant(
        client, workspace, workspace_form, editor, person.id, "VIEWER", export=True
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "export_grant_reserved"
    (row,) = await stored(workspace, workspace_form)
    assert (row.role, row.export) == ("EDITOR", False)


async def test_an_editor_cannot_change_a_grant_that_allows_export(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    editor = await add_member(workspace, "COLLABORATOR")
    person = await add_member(workspace, "VIEWER")
    await put_grant(client, workspace, workspace_form, testUser, person.id, "VIEWER", export=True)
    for role in ("VIEWER", "EDITOR"):
        response = await put_grant(client, workspace, workspace_form, editor, person.id, role)
        assert response.status_code == 403, role
        assert response.json()["code"] == "export_grant_reserved"
    (row,) = await stored(workspace, workspace_form)
    assert (row.role, row.export) == ("VIEWER", True)


async def test_a_grant_is_never_above_the_grantors_own_role_on_the_form(
    client: AsyncClient, workspace, workspace_form, switch_on, monkeypatch
):
    """The cap is the grantor's permissions on the form: someone who can share
    it but cannot annotate gives no Reviewer or Editor grant."""
    sharer = await add_member(workspace, "COLLABORATOR")
    person = await add_member(workspace, "VIEWER")
    authz = container.authorization_service()
    real = authz.form_permissions

    async def narrowed(user, workspace_id, form_id, raise_sso_required=False):
        decided = await real(user, workspace_id, form_id, raise_sso_required)
        if str(user.id) != sharer.id:
            return decided
        return FormPermissions(
            frozenset({P.FORM_READ, P.FORM_SHARE, P.RESPONSE_READ, P.ANALYTICS_READ}),
            decided.source,
            decided.restricted,
            decided.form_found,
        )

    monkeypatch.setattr(authz, "form_permissions", narrowed)
    for role in ("EDITOR", "REVIEWER"):
        response = await put_grant(client, workspace, workspace_form, sharer, person.id, role)
        assert response.status_code == 403, role
        assert response.json()["code"] == "grant_above_own_role"
    assert (await put_grant(client, workspace, workspace_form, sharer, person.id, "VIEWER")).status_code == 200


async def test_nobody_grants_themselves_a_role(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    editor = await add_member(workspace, "COLLABORATOR")
    for user in (editor, testUser):
        response = await put_grant(client, workspace, workspace_form, user, user.id, "EDITOR")
        assert response.status_code == 403
        assert response.json()["code"] == "cannot_grant_self"
    assert await stored(workspace, workspace_form) == []


async def test_a_grantee_cannot_remove_their_own_grant_but_an_owner_can(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    editor = await add_member(workspace, "COLLABORATOR")
    await put_grant(client, workspace, workspace_form, testUser, editor.id, "EDITOR")
    (row,) = await stored(workspace, workspace_form)
    own = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{row.id}"), cookies=cookies(editor)
    )
    assert own.status_code == 403 and own.json()["code"] == "cannot_grant_self"
    assert len(await stored(workspace, workspace_form)) == 1
    by_owner = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{row.id}"), cookies=cookies(testUser)
    )
    assert by_owner.status_code == 204


async def test_an_editor_cannot_remove_what_they_could_not_give(
    client: AsyncClient, workspace, workspace_form, switch_on, monkeypatch
):
    """Removing a grant has the caps of giving it: no removing and giving back
    something the editor may not give."""
    editor = await add_member(workspace, "COLLABORATOR")
    exporter = await add_member(workspace, "VIEWER")
    plain = await add_member(workspace, "VIEWER")
    await put_grant(client, workspace, workspace_form, testUser, exporter.id, "VIEWER", export=True)
    await put_grant(client, workspace, workspace_form, testUser, plain.id, "EDITOR")
    rows = {g.subject_id: g for g in await stored(workspace, workspace_form)}

    denied = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{rows[exporter.id].id}"),
        cookies=cookies(editor),
    )
    assert denied.status_code == 403 and denied.json()["code"] == "export_grant_reserved"

    # an editor who can share but is below the grant's role cannot remove it
    authz = container.authorization_service()
    real = authz.form_permissions

    async def narrowed(user, workspace_id, form_id, raise_sso_required=False):
        decided = await real(user, workspace_id, form_id, raise_sso_required)
        if str(user.id) != editor.id:
            return decided
        return FormPermissions(
            frozenset({P.FORM_READ, P.FORM_SHARE, P.RESPONSE_READ, P.ANALYTICS_READ}),
            decided.source,
            decided.restricted,
            decided.form_found,
        )

    monkeypatch.setattr(authz, "form_permissions", narrowed)
    above = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{rows[plain.id].id}"),
        cookies=cookies(editor),
    )
    assert above.status_code == 403 and above.json()["code"] == "grant_above_own_role"
    assert len(await stored(workspace, workspace_form)) == 2
    # an owner can
    by_owner = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{rows[exporter.id].id}"),
        cookies=cookies(testUser),
    )
    assert by_owner.status_code == 204


async def test_a_privacy_officer_is_never_granted_a_role(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    officer = await add_member(workspace, "PRIVACY_OFFICER")
    response = await put_grant(client, workspace, workspace_form, testUser, officer.id, "VIEWER")
    assert response.status_code == 422
    assert response.json()["code"] == "privacy_officer_cannot_be_granted"
    assert await stored(workspace, workspace_form) == []


async def test_a_reviewer_or_viewer_cannot_grant_at_all(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    for role in ("REVIEWER", "VIEWER", "PRIVACY_OFFICER"):
        user = await add_member(workspace, role)
        response = await put_grant(client, workspace, workspace_form, user, person.id, "VIEWER")
        assert response.status_code == 403, role


# -- inside the workspace (IDOR) -------------------------------------------------------------------
async def test_a_subject_from_another_workspace_is_a_404(
    client: AsyncClient, workspace, workspace_1, workspace_form, switch_on
):
    outsider = await add_member(workspace_1, "VIEWER")
    foreign_team = await team_with(workspace_1, name="Foreign")
    removed = await add_member(workspace, "VIEWER")
    for subject, kind in (
        (outsider.id, "user"),
        (str(foreign_team.id), "group"),
        (str(RecordId()), "user"),
        (str(RecordId()), "group"),
        ("not-an-id", "user"),
        (removed.id, "group"),  # a person's id never names a team
    ):
        response = await put_grant(
            client, workspace, workspace_form, testUser, subject, "VIEWER", subject_type=kind
        )
        assert response.status_code == 404, (subject, kind, response.text)
    assert await stored(workspace, workspace_form) == []
    assert not await audit_events(workspace, ACCESS_GRANT_ADDED)


async def test_a_form_of_another_workspace_is_a_404_for_every_route(
    client: AsyncClient, workspace, workspace_1, switch_on
):
    foreign = await create_form(workspace_1, testUser1)
    person = await add_member(workspace, "VIEWER")
    for method, tail, body in (
        ("GET", "/access", None),
        ("PUT", "/access/mode", {"mode": "restricted"}),
        ("PUT", "/grants", {"subjectType": "user", "subjectId": person.id, "role": "VIEWER"}),
        ("DELETE", "/grants/" + "0" * 24, None),
    ):
        # the path names this workspace but the other workspace's form
        response = await client.request(
            method, form_url(workspace, foreign, tail), cookies=cookies(testUser), json=body
        )
        assert response.status_code == 404, (method, tail, response.text)
    assert await link_mode(workspace_1, foreign) is None


async def test_a_grant_id_of_another_form_or_workspace_is_a_404_and_removes_nothing(
    client: AsyncClient, workspace, workspace_1, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    other_form = await create_form(workspace, testUser)
    await put_grant(client, workspace, other_form, testUser, person.id, "VIEWER")
    (row,) = await stored(workspace, other_form)
    # the right id, the wrong form of the same workspace
    response = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{row.id}"), cookies=cookies(testUser)
    )
    assert response.status_code == 404
    # the wrong workspace in the path, as another workspace's owner
    response = await client.delete(
        form_url(workspace_1, other_form, f"/grants/{row.id}"), cookies=cookies(testUser1)
    )
    assert response.status_code == 404
    for bad in ("not-an-id", "0" * 24):
        gone = await client.delete(
            form_url(workspace, workspace_form, f"/grants/{bad}"), cookies=cookies(testUser)
        )
        assert gone.status_code == 404
    assert len(await stored(workspace, other_form)) == 1
    assert not await audit_events(workspace, ACCESS_GRANT_REMOVED)


# -- restricted forms: who widens the circle ----------------------------------------------------------
async def test_on_a_restricted_form_a_grantee_editor_cannot_widen_the_circle_or_the_mode(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    await restrict(workspace, workspace_form.form_id)
    grantee = await add_member(workspace, "COLLABORATOR")
    person = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, grantee.id, "EDITOR")
    existing = await grant(workspace, workspace_form.form_id, person.id, "VIEWER")
    for method, tail, body in (
        ("PUT", "/grants", {"subjectType": "user", "subjectId": person.id, "role": "EDITOR"}),
        ("DELETE", f"/grants/{existing.id}", None),
        ("PUT", "/access/mode", {"mode": "workspace"}),
    ):
        response = await client.request(
            method, form_url(workspace, workspace_form, tail), cookies=cookies(grantee), json=body
        )
        assert response.status_code == 403, (method, tail, response.text)
        assert response.json()["code"] == "access_manage_forbidden"
    assert await link_mode(workspace, workspace_form) == MODE_RESTRICTED
    assert len(await stored(workspace, workspace_form)) == 2
    # reading the circle is allowed to a grantee who may share
    got = await client.get(
        form_url(workspace, workspace_form, "/access"), cookies=cookies(grantee)
    )
    assert got.status_code == 200 and got.json()["canManage"] is False


async def test_on_a_restricted_form_the_creator_and_an_admin_manage_the_circle(
    client: AsyncClient, workspace, switch_on
):
    creator = await add_member(workspace, "COLLABORATOR")
    admin = await add_member(workspace, "ADMIN")
    form = await create_form(workspace, creator)
    await restrict(workspace, form.form_id)
    person = await add_member(workspace, "VIEWER")
    for user in (creator, admin):
        ok = await put_grant(client, workspace, form, user, person.id, "VIEWER")
        assert ok.status_code == 200, (user.id, ok.text)
    # a plain Editor, with no grant, does not even see the form
    editor = await add_member(workspace, "COLLABORATOR")
    assert (await put_grant(client, workspace, form, editor, person.id, "VIEWER")).status_code == 404


async def test_on_an_open_form_any_editor_within_their_caps_may_share_it(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    editor = await add_member(workspace, "COLLABORATOR")
    person = await add_member(workspace, "VIEWER")
    ok = await put_grant(client, workspace, workspace_form, editor, person.id, "REVIEWER")
    assert ok.status_code == 200


# -- the mode -------------------------------------------------------------------------------------------------
async def test_the_creator_restricts_and_reopens_their_form_and_it_is_audited(
    client: AsyncClient, workspace, switch_on
):
    creator = await add_member(workspace, "COLLABORATOR")
    form = await create_form(workspace, creator)
    other = await add_member(workspace, "VIEWER")
    url = form_url(workspace, form, "/access/mode")

    restricted = await client.put(url, cookies=cookies(creator), json={"mode": "restricted"})
    assert restricted.status_code == 200, restricted.text
    body = restricted.json()
    assert (body["accessMode"], body["restricted"], body["source"]) == (
        "restricted",
        True,
        "creator",
    )
    assert await link_mode(workspace, form) == MODE_RESTRICTED
    # nobody else sees it any more
    assert (
        await client.get(form_url(workspace, form, "/access"), cookies=cookies(other))
    ).status_code == 404

    # the same value again changes nothing and records nothing
    again = await client.put(url, cookies=cookies(creator), json={"mode": "restricted"})
    assert again.status_code == 200
    assert len(await audit_events(workspace, ACCESS_MODE_CHANGED)) == 1

    reopened = await client.put(url, cookies=cookies(creator), json={"mode": "workspace"})
    assert reopened.status_code == 200 and reopened.json()["restricted"] is False
    events = await audit_events(workspace, ACCESS_MODE_CHANGED)
    assert [(e.access_mode, e.form_id, e.user_id) for e in events] == [
        ("restricted", form.form_id, creator.id),
        ("workspace", form.form_id, creator.id),
    ]


async def test_an_editor_who_is_not_the_creator_does_not_change_the_mode(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    editor = await add_member(workspace, "COLLABORATOR")
    for mode in ("restricted", "workspace"):
        response = await client.put(
            form_url(workspace, workspace_form, "/access/mode"),
            cookies=cookies(editor),
            json={"mode": mode},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "access_manage_forbidden"
    assert await link_mode(workspace, workspace_form) is None


async def test_an_unknown_mode_or_role_or_subject_type_is_a_validation_error(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    bad = [
        ("PUT", "/access/mode", {"mode": "private"}),
        ("PUT", "/grants", {"subjectType": "user", "subjectId": person.id, "role": "OWNER"}),
        ("PUT", "/grants", {"subjectType": "key", "subjectId": person.id, "role": "VIEWER"}),
        ("PUT", "/grants", {"subjectType": "user", "role": "VIEWER"}),
    ]
    for method, tail, body in bad:
        response = await client.request(
            method, form_url(workspace, workspace_form, tail), cookies=cookies(testUser), json=body
        )
        assert response.status_code == 422, (tail, body)
    assert await link_mode(workspace, workspace_form) is None
    assert await stored(workspace, workspace_form) == []


async def test_the_mode_cannot_be_written_through_the_grant_body_or_the_settings(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    await client.put(
        form_url(workspace, workspace_form, "/grants"),
        cookies=cookies(testUser),
        json={
            "subjectType": "user",
            "subjectId": person.id,
            "role": "VIEWER",
            "accessMode": "restricted",
        },
    )
    assert await link_mode(workspace, workspace_form) is None


# -- audit first ---------------------------------------------------------------------------------------------------
async def test_nothing_changes_when_the_audit_cannot_be_written(
    client: AsyncClient, workspace, workspace_form, switch_on, monkeypatch
):
    person = await add_member(workspace, "VIEWER")
    existing = await grant(workspace, workspace_form.form_id, person.id, "VIEWER")
    fail_audit(monkeypatch)
    for method, tail, body in (
        ("PUT", "/grants", {"subjectType": "user", "subjectId": person.id, "role": "EDITOR"}),
        ("DELETE", f"/grants/{existing.id}", None),
        ("PUT", "/access/mode", {"mode": "restricted"}),
    ):
        response = await client.request(
            method, form_url(workspace, workspace_form, tail), cookies=cookies(testUser), json=body
        )
        assert response.status_code == 503, (tail, response.text)
        assert response.json()["code"] == "audit_unavailable"
    (row,) = await stored(workspace, workspace_form)
    assert row.role == "VIEWER"
    assert await link_mode(workspace, workspace_form) is None


async def test_every_write_drops_what_the_request_remembered(
    client: AsyncClient, workspace, workspace_form, switch_on, monkeypatch
):
    calls = []
    service = container.form_access_service()
    real = service.invalidate
    monkeypatch.setattr(service, "invalidate", lambda: (calls.append(1), real())[1])
    person = await add_member(workspace, "VIEWER")
    added = await put_grant(client, workspace, workspace_form, testUser, person.id, "VIEWER")
    await client.put(
        form_url(workspace, workspace_form, "/access/mode"),
        cookies=cookies(testUser),
        json={"mode": "restricted"},
    )
    await client.delete(
        form_url(workspace, workspace_form, f"/grants/{added.json()['id']}"),
        cookies=cookies(testUser),
    )
    assert len(calls) >= 3


async def test_a_disabled_member_is_flagged_on_their_grant(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    person = await add_member(workspace, "VIEWER")
    await put_grant(client, workspace, workspace_form, testUser, person.id, "VIEWER")
    membership = await container.workspace_user_repo().find_workspace_user(
        workspace.id, person.id
    )
    membership.disabled = True
    await container.workspace_user_repo().save(membership)
    body = (
        await client.get(
            form_url(workspace, workspace_form, "/access"), cookies=cookies(testUser)
        )
    ).json()
    assert [g["disabled"] for g in body["grants"]] == [True]
