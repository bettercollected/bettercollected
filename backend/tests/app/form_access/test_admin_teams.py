"""Teams (member groups): the routes, who may use them, the checks inside the
workspace and the audit trail. Everything is synthetic."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.member_group import MemberGroupDocument
from backend.app.schemas.workspace_audit_event import (
    TEAM_CREATED,
    TEAM_DELETED,
    TEAM_MEMBER_ADDED,
    TEAM_MEMBER_REMOVED,
    TEAM_RENAMED,
)
from backend.app.services.form_access import admin as admin_module
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    fail_audit,
    grant,
    team_with,
)

pytestmark = pytest.mark.asyncio

ROLES_THAT_MANAGE = {"ADMIN"}
ROLES_THAT_DO_NOT = ("COLLABORATOR", "REVIEWER", "VIEWER", "PRIVACY_OFFICER")


async def create(client, workspace, name="Hiring", user=testUser, **extra):
    return await client.post(
        f"{api(workspace)}/member-groups",
        cookies=cookies(user),
        json={"name": name, **extra},
    )


# -- the switch -----------------------------------------------------------------
async def test_every_team_route_answers_422_while_the_switch_is_off(
    client: AsyncClient, workspace, switch_off
):
    member = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, member)
    base = f"{api(workspace)}/member-groups"
    calls = [
        ("GET", base, None),
        ("POST", base, {"name": "x"}),
        ("GET", f"{base}/{team.id}", None),
        ("PATCH", f"{base}/{team.id}", {"name": "y"}),
        ("DELETE", f"{base}/{team.id}", None),
        ("PUT", f"{base}/{team.id}/members/{member.id}", None),
        ("DELETE", f"{base}/{team.id}/members/{member.id}", None),
        ("GET", f"{api(workspace)}/members/{member.id}/access", None),
    ]
    for method, url, body in calls:
        response = await client.request(
            method, url, cookies=cookies(testUser), json=body
        )
        assert response.status_code == 422, (method, url, response.text)
        assert response.json()["code"] == "form_access_off"
    # nothing was written or removed
    assert await container.member_group_repo().member_ids(workspace.id, team.id) == [
        member.id
    ]
    assert not await audit_events(workspace)


# -- the flow -----------------------------------------------------------------
async def test_an_owner_creates_lists_renames_fills_and_deletes_a_team(
    client: AsyncClient, workspace, switch_on
):
    created = await create(client, workspace, "  Human   Resources ", description="HR")
    assert created.status_code == 201, created.text
    team = created.json()
    assert team["name"] == "Human Resources"
    assert team["source"] == "manual" and team["memberCount"] == 0

    # the same name, spelled differently, is the same team
    for spelling in ("human resources", "HUMAN  RESOURCES", "Ｈuman Ｒesources"):
        clash = await create(client, workspace, spelling)
        assert clash.status_code == 409, spelling
        assert clash.json()["code"] == "team_name_taken"

    member = await add_member(workspace, "VIEWER")
    added = await client.put(
        f"{api(workspace)}/member-groups/{team['id']}/members/{member.id}",
        cookies=cookies(testUser),
    )
    assert added.status_code == 204, added.text
    # adding again changes nothing
    again = await client.put(
        f"{api(workspace)}/member-groups/{team['id']}/members/{member.id}",
        cookies=cookies(testUser),
    )
    assert again.status_code == 204

    listed = await client.get(f"{api(workspace)}/member-groups", cookies=cookies(testUser))
    assert [(t["name"], t["memberCount"]) for t in listed.json()] == [
        ("Human Resources", 1)
    ]
    detail = (
        await client.get(
            f"{api(workspace)}/member-groups/{team['id']}", cookies=cookies(testUser)
        )
    ).json()
    assert [m["userId"] for m in detail["members"]] == [member.id]
    assert detail["members"][0]["role"] == "VIEWER"
    assert detail["formCount"] == 0

    renamed = await client.patch(
        f"{api(workspace)}/member-groups/{team['id']}",
        cookies=cookies(testUser),
        json={"name": "People team"},
    )
    assert renamed.status_code == 200, renamed.text
    stored = await container.member_group_repo().find(workspace.id, team["id"])
    # the unique key follows the name
    assert stored.name == "People team" and stored.name_key == "people team"
    assert (await create(client, workspace, "Human Resources")).status_code == 201

    removed = await client.delete(
        f"{api(workspace)}/member-groups/{team['id']}/members/{member.id}",
        cookies=cookies(testUser),
    )
    assert removed.status_code == 204
    gone = await client.delete(
        f"{api(workspace)}/member-groups/{team['id']}", cookies=cookies(testUser)
    )
    assert gone.status_code == 204
    assert await container.member_group_repo().find(workspace.id, team["id"]) is None

    events = await audit_events(workspace)
    assert [e.event for e in events] == [
        TEAM_CREATED,
        TEAM_MEMBER_ADDED,
        TEAM_RENAMED,
        TEAM_CREATED,
        TEAM_MEMBER_REMOVED,
        TEAM_DELETED,
    ]


async def test_audit_rows_name_ids_and_never_a_name(
    client: AsyncClient, workspace, switch_on
):
    team = (await create(client, workspace, "Secret Project Team")).json()
    member = await add_member(workspace, "VIEWER")
    await client.put(
        f"{api(workspace)}/member-groups/{team['id']}/members/{member.id}",
        cookies=cookies(testUser),
    )
    rows = await audit_events(workspace)
    created, added = rows
    assert created.event == TEAM_CREATED and created.group_id == team["id"]
    assert added.group_id == team["id"] and added.target_user_id == member.id
    assert added.user_id == testUser.id and added.session_id
    dump = " ".join(str(r.model_dump(mode="json")) for r in rows)
    assert "Secret Project Team" not in dump and "@" not in dump


async def test_a_description_only_change_is_audited_and_an_unchanged_patch_is_not(
    client: AsyncClient, workspace, switch_on
):
    team = (await create(client, workspace)).json()
    url = f"{api(workspace)}/member-groups/{team['id']}"
    await client.patch(url, cookies=cookies(testUser), json={"description": "Who hires"})
    assert len(await audit_events(workspace, TEAM_RENAMED)) == 1
    same = await client.patch(url, cookies=cookies(testUser), json={"description": "Who hires"})
    assert same.status_code == 200
    assert len(await audit_events(workspace, TEAM_RENAMED)) == 1


async def test_invalid_names_are_refused(client: AsyncClient, workspace, switch_on):
    for name in ("", "   ", "x" * 81, "bad\x00name"):
        response = await create(client, workspace, name)
        assert response.status_code in (422,), (name, response.text)
    assert await container.member_group_repo().list_in_workspace(workspace.id) == []


async def test_a_workspace_has_a_limited_number_of_teams_and_members(
    client: AsyncClient, workspace, switch_on, monkeypatch
):
    monkeypatch.setattr(admin_module, "MAX_TEAMS", 2)
    monkeypatch.setattr(admin_module, "MAX_TEAM_MEMBERS", 1)
    first = (await create(client, workspace, "One")).json()
    assert (await create(client, workspace, "Two")).status_code == 201
    full = await create(client, workspace, "Three")
    assert full.status_code == 409 and full.json()["code"] == "too_many_teams"

    one, two = await add_member(workspace, "VIEWER"), await add_member(workspace, "VIEWER")
    base = f"{api(workspace)}/member-groups/{first['id']}/members"
    assert (await client.put(f"{base}/{one.id}", cookies=cookies(testUser))).status_code == 204
    over = await client.put(f"{base}/{two.id}", cookies=cookies(testUser))
    assert over.status_code == 409 and over.json()["code"] == "team_full"
    # the member already in is not "over"
    assert (await client.put(f"{base}/{one.id}", cookies=cookies(testUser))).status_code == 204


# -- who may -------------------------------------------------------------------
async def test_only_owners_and_admins_manage_teams(
    client: AsyncClient, workspace, switch_on
):
    team = await team_with(workspace, name="Existing")
    target = await add_member(workspace, "VIEWER")
    for role in ("ADMIN",) + ROLES_THAT_DO_NOT:
        user = await add_member(workspace, role)
        allowed = role in ROLES_THAT_MANAGE
        for method, url, body in (
            ("GET", f"{api(workspace)}/member-groups", None),
            ("POST", f"{api(workspace)}/member-groups", {"name": f"By {role}"}),
            ("GET", f"{api(workspace)}/member-groups/{team.id}", None),
            ("PATCH", f"{api(workspace)}/member-groups/{team.id}", {"name": f"R {role}"}),
            ("PUT", f"{api(workspace)}/member-groups/{team.id}/members/{target.id}", None),
            ("DELETE", f"{api(workspace)}/member-groups/{team.id}/members/{target.id}", None),
            ("GET", f"{api(workspace)}/members/{target.id}/access", None),
        ):
            response = await client.request(
                method, url, cookies=cookies(user), json=body
            )
            assert (response.status_code < 400) == allowed, (role, method, url)
            if not allowed:
                assert response.status_code == 403, (role, method, url)
    # and a stranger
    from common.models.user import User
    from common.ids import RecordId

    stranger = User(id=str(RecordId()), sub="stranger@example.org")
    response = await client.get(f"{api(workspace)}/member-groups", cookies=cookies(stranger))
    assert response.status_code == 403


# -- inside the workspace (IDOR) -------------------------------------------------
async def test_another_workspaces_team_is_a_404_everywhere(
    client: AsyncClient, workspace, workspace_1, switch_on
):
    foreign = await team_with(workspace_1, name="Foreign")
    member = await add_member(workspace, "VIEWER")
    base = f"{api(workspace)}/member-groups/{foreign.id}"
    for method, url, body in (
        ("GET", base, None),
        ("PATCH", base, {"name": "mine now"}),
        ("DELETE", base, None),
        ("PUT", f"{base}/members/{member.id}", None),
        ("DELETE", f"{base}/members/{member.id}", None),
    ):
        response = await client.request(method, url, cookies=cookies(testUser), json=body)
        assert response.status_code == 404, (method, response.text)
    stored = await container.member_group_repo().find(workspace_1.id, foreign.id)
    assert stored is not None and stored.name == "Foreign"
    assert await container.member_group_repo().member_ids(workspace_1.id, foreign.id) == []
    assert not await audit_events(workspace)


async def test_a_person_of_another_workspace_or_a_bad_id_cannot_join_a_team(
    client: AsyncClient, workspace, workspace_1, switch_on
):
    team = await team_with(workspace, name="Mine")
    outsider = await add_member(workspace_1, "VIEWER")
    disabled = await add_member(workspace, "VIEWER", disabled=True)
    for who in (outsider.id, disabled.id, "not-an-id", "0" * 24):
        response = await client.put(
            f"{api(workspace)}/member-groups/{team.id}/members/{who}",
            cookies=cookies(testUser),
        )
        assert response.status_code == 404, (who, response.text)
    assert await container.member_group_repo().member_ids(workspace.id, team.id) == []
    assert not await audit_events(workspace, TEAM_MEMBER_ADDED)


async def test_removing_someone_who_is_not_in_the_team_is_a_404(
    client: AsyncClient, workspace, switch_on
):
    team = await team_with(workspace, name="Mine")
    other = await add_member(workspace, "VIEWER")
    response = await client.delete(
        f"{api(workspace)}/member-groups/{team.id}/members/{other.id}",
        cookies=cookies(testUser),
    )
    assert response.status_code == 404
    assert not await audit_events(workspace, TEAM_MEMBER_REMOVED)


async def test_a_member_of_another_workspace_has_no_access_page(
    client: AsyncClient, workspace, workspace_1, switch_on
):
    outsider = await add_member(workspace_1, "VIEWER")
    response = await client.get(
        f"{api(workspace)}/members/{outsider.id}/access", cookies=cookies(testUser)
    )
    assert response.status_code == 404


async def test_a_members_access_lists_their_teams_and_grants(
    client: AsyncClient, workspace, workspace_form, switch_on
):
    member = await add_member(workspace, "VIEWER")
    team = await team_with(workspace, member, name="Reviewers")
    await team_with(workspace, name="Others")
    await grant(workspace, workspace_form.form_id, member.id, "REVIEWER")
    response = await client.get(
        f"{api(workspace)}/members/{member.id}/access", cookies=cookies(testUser)
    )
    body = response.json()
    assert [t["id"] for t in body["teams"]] == [str(team.id)]
    assert [(g["subjectId"], g["role"]) for g in body["grants"]] == [(member.id, "REVIEWER")]


# -- audit first -----------------------------------------------------------------
async def test_nothing_changes_when_the_audit_cannot_be_written(
    client: AsyncClient, workspace, switch_on, monkeypatch
):
    team = await team_with(workspace, name="Existing")
    member = await add_member(workspace, "VIEWER")
    fail_audit(monkeypatch)
    base = f"{api(workspace)}/member-groups"
    for method, url, body in (
        ("POST", base, {"name": "New"}),
        ("PATCH", f"{base}/{team.id}", {"name": "Renamed"}),
        ("PUT", f"{base}/{team.id}/members/{member.id}", None),
        ("DELETE", f"{base}/{team.id}", None),
    ):
        response = await client.request(method, url, cookies=cookies(testUser), json=body)
        assert response.status_code == 503, (method, response.text)
        assert response.json()["code"] == "audit_unavailable"
    teams = await container.member_group_repo().list_in_workspace(workspace.id)
    assert [t.name for t in teams] == ["Existing"]
    assert await container.member_group_repo().member_ids(workspace.id, team.id) == []


async def test_the_row_is_written_before_the_change(
    client: AsyncClient, workspace, switch_on, monkeypatch
):
    """The entry is in the log when the team is created (the order, not just
    the count): the write sees the entry already stored."""
    seen = {}
    real_create = container.member_group_repo().create

    async def spy(group, max_teams):
        seen["entries"] = len(await audit_events(workspace, TEAM_CREATED))
        return await real_create(group, max_teams)

    monkeypatch.setattr(container.member_group_repo(), "create", spy)
    assert (await create(client, workspace)).status_code == 201
    assert seen["entries"] == 1


# -- the memo -----------------------------------------------------------------------
async def test_every_write_drops_what_the_request_remembered(
    client: AsyncClient, workspace, switch_on, monkeypatch
):
    calls = []
    service = container.form_access_service()
    real = service.invalidate
    monkeypatch.setattr(service, "invalidate", lambda: (calls.append(1), real())[1])
    team = (await create(client, workspace)).json()
    member = await add_member(workspace, "VIEWER")
    base = f"{api(workspace)}/member-groups/{team['id']}"
    await client.put(f"{base}/members/{member.id}", cookies=cookies(testUser))
    await client.delete(f"{base}/members/{member.id}", cookies=cookies(testUser))
    await client.delete(base, cookies=cookies(testUser))
    assert len(calls) >= 4


async def test_a_team_row_built_without_a_workspace_match_is_not_found(
    workspace, workspace_1
):
    """The repository itself never finds a team through another workspace."""
    team = await container.member_group_repo().save(
        MemberGroupDocument(workspace_id=workspace_1.id, name="Elsewhere")
    )
    assert await container.member_group_repo().find(workspace.id, team.id) is None
