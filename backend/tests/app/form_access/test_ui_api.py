"""What the form-access screens ask of the API: the ``access`` block of the
dashboard payloads, the form titles of a member's access view, the picker for
whoever may share a form but cannot list the members, team sizes, the dry run
of restricting a form and the name of whoever gave a grant. Everything is
synthetic."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from common.ids import RecordId
from httpx import AsyncClient

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import ROLE_EDITOR, ROLE_VIEWER
from tests.app.controllers.data import formData, testUser, testUser1
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    create_form,
    grant,
    restrict,
    team_with,
)
from tests.app.form_access.test_switch_and_memo import statements, touching_new_tables

pytestmark = pytest.mark.asyncio
P = Permission


def form_url(workspace, form_id, tail="") -> str:
    return f"{api(workspace)}/forms/{form_id}{tail}"


@pytest.fixture()
def names(monkeypatch):
    """The auth service's user lookup: every id is named ``Person <last 4>``,
    with an address the screens must never receive."""

    async def users(url, params=None, **kwargs):
        return {
            "users_info": [
                {
                    "_id": i,
                    "first_name": "Person",
                    "last_name": str(i)[-4:],
                    "email": f"{i}@never-shown.example",
                }
                for i in params["user_ids"]
            ]
        }

    directory = container.member_directory()
    monkeypatch.setattr(directory._http_client, "get", AsyncMock(side_effect=users))
    monkeypatch.setattr(
        container.form_service(),
        "fetch_user_details",
        AsyncMock(return_value={"users_info": []}),
    )


def name_of(user) -> str:
    return f"Person {str(user.id)[-4:]}"


@pytest.fixture()
async def world(workspace, names):
    """An owner, an Admin, a Privacy officer, a Viewer, a Reviewer, an Editor
    who created the restricted form, another Editor, and a Viewer holding a
    Viewer grant on it; one open form and one restricted form."""
    who = SimpleNamespace(
        owner=testUser,
        admin=await add_member(workspace, "ADMIN"),
        officer=await add_member(workspace, "PRIVACY_OFFICER"),
        viewer=await add_member(workspace, "VIEWER"),
        reviewer=await add_member(workspace, "REVIEWER"),
        creator=await add_member(workspace, "COLLABORATOR"),
        editor=await add_member(workspace, "COLLABORATOR"),
        granted=await add_member(workspace, "VIEWER"),
        gone=await add_member(workspace, "VIEWER", disabled=True),
    )
    open_form = await create_form(workspace, who.owner)
    closed_form = await create_form(workspace, who.creator)
    await restrict(workspace, closed_form.form_id)
    await grant(workspace, closed_form.form_id, who.granted.id, ROLE_VIEWER)
    return SimpleNamespace(
        workspace=workspace, who=who, open=open_form, closed=closed_form
    )


def by_id(page) -> dict:
    return {item["formId"]: item for item in page["items"]}


# -- 1. the access block ---------------------------------------------------------
async def test_the_dashboard_list_carries_the_readers_own_access(
    client: AsyncClient, world, switch_on
):
    base = api(world.workspace)
    owner = by_id((await client.get(f"{base}/forms", cookies=cookies(world.who.owner))).json())
    assert owner[str(world.open.form_id)]["access"]["restricted"] is False
    shown = owner[str(world.closed.form_id)]["access"]
    assert shown["restricted"] is True and shown["canManage"] is True
    assert P.FORM_EDIT.value in shown["permissions"]
    # nothing about grants or anyone else's access travels in it
    assert set(shown) == {"restricted", "canManage", "permissions"}
    assert all(p in {x.value for x in Permission} for p in shown["permissions"])

    # the creator keeps the form they made; a granted Viewer reads it, no more
    creator = by_id((await client.get(f"{base}/forms", cookies=cookies(world.who.creator))).json())
    mine = creator[str(world.closed.form_id)]["access"]
    assert mine["restricted"] is True and mine["canManage"] is True
    granted = by_id((await client.get(f"{base}/forms", cookies=cookies(world.who.granted))).json())
    theirs = granted[str(world.closed.form_id)]["access"]
    assert theirs["restricted"] is True and theirs["canManage"] is False
    assert P.FORM_READ.value in theirs["permissions"]
    assert P.FORM_EDIT.value not in theirs["permissions"]
    assert P.FORM_SHARE.value not in theirs["permissions"]
    # the open form, for the same Viewer
    assert granted[str(world.open.form_id)]["access"] == {
        "restricted": False,
        "canManage": False,
        "permissions": sorted(
            p.value
            for p in (P.FORM_READ, P.RESPONSE_READ, P.ANALYTICS_READ)
        ),
    }
    # a member the form is closed to does not see it, and so no block of it
    editor = by_id((await client.get(f"{base}/forms", cookies=cookies(world.who.editor))).json())
    assert str(world.closed.form_id) not in editor
    assert editor[str(world.open.form_id)]["access"]["restricted"] is False


async def test_search_and_one_form_carry_it_too(client: AsyncClient, world, switch_on):
    base = api(world.workspace)
    found = await client.post(
        f"{base}/forms/search",
        params={"query": formData["title"]},
        cookies=cookies(world.who.creator),
    )
    assert found.status_code == 200
    blocks = {f["formId"]: f.get("access") for f in found.json()}
    assert blocks[str(world.closed.form_id)]["restricted"] is True
    one = await client.get(
        form_url(world.workspace, world.closed.form_id), cookies=cookies(world.who.creator)
    )
    assert one.status_code == 200
    assert one.json()["access"] == {
        "restricted": True,
        "canManage": True,
        "permissions": one.json()["access"]["permissions"],
    }
    assert P.FORM_EDIT.value in one.json()["access"]["permissions"]


async def test_the_public_listing_carries_none(client: AsyncClient, world, switch_on):
    base = api(world.workspace)
    listed = await client.get(
        f"{base}/forms", params={"published": True}, cookies=cookies(world.who.owner)
    )
    assert listed.status_code == 200
    assert all("access" not in item for item in listed.json()["items"])


async def test_off_nothing_is_added_to_a_payload_or_a_query(
    client: AsyncClient, world, switch_off
):
    base = api(world.workspace)
    for user in (world.who.owner, world.who.editor):
        await client.get(f"{base}/forms", cookies=cookies(user))  # warm what is cached
        with statements() as seen:
            listed = await client.get(f"{base}/forms", cookies=cookies(user))
        assert listed.status_code == 200
        assert all("access" not in item for item in listed.json()["items"]), user.sub
        # the same ceiling as before the screens (test_read_enforcement.py)
        assert len(seen) <= 10, len(seen)
        assert not touching_new_tables(seen)
        one = await client.get(
            form_url(world.workspace, world.open.form_id), cookies=cookies(user)
        )
        assert "access" not in one.json()
        found = await client.post(
            f"{base}/forms/search",
            params={"query": formData["title"]},
            cookies=cookies(user),
        )
        assert all("access" not in item for item in found.json())


async def test_the_block_is_one_read_for_the_page_however_many_forms(
    client: AsyncClient, world, switch_on
):
    base = api(world.workspace)

    async def measured(user):
        await client.get(f"{base}/forms", cookies=cookies(user))
        with statements() as seen:
            listed = await client.get(f"{base}/forms", cookies=cookies(user))
        assert listed.status_code == 200
        return len(seen), len(listed.json()["items"])

    users = (world.who.owner, world.who.granted)
    small = {u.sub: await measured(u) for u in users}
    for _ in range(4):
        await create_form(world.workspace, world.who.owner)
    for user in users:
        count, forms = small[user.sub]
        more, now = await measured(user)
        assert now > forms or user is world.who.granted
        assert more == count, (user.sub, count, more)


# -- 2. the forms of a member's grants -----------------------------------------------
async def test_a_members_access_view_names_the_form_of_each_grant(
    client: AsyncClient, world, switch_on
):
    await grant(world.workspace, world.open.form_id, world.who.granted.id, ROLE_EDITOR)
    got = await client.get(
        f"{api(world.workspace)}/members/{world.who.granted.id}/access",
        cookies=cookies(world.who.owner),
    )
    assert got.status_code == 200
    grants = {g["formId"]: g for g in got.json()["grants"]}
    assert set(grants) == {str(world.open.form_id), str(world.closed.form_id)}
    assert all(g["formTitle"] == formData["title"] for g in grants.values())


async def test_a_grant_on_another_workspaces_form_names_no_form(
    client: AsyncClient, world, workspace_1, switch_on
):
    foreign = await create_form(workspace_1, testUser1)
    await grant(world.workspace, foreign.form_id, world.who.granted.id, ROLE_VIEWER)
    got = await client.get(
        f"{api(world.workspace)}/members/{world.who.granted.id}/access",
        cookies=cookies(world.who.owner),
    )
    assert got.status_code == 200
    odd = [g for g in got.json()["grants"] if g["id"] and g["formId"] is None]
    assert len(odd) == 1 and odd[0]["formTitle"] is None
    assert str(foreign.form_id) not in got.text


async def test_a_reader_who_may_not_open_a_form_gets_no_title(world, switch_on):
    """The titles are filtered through the reader's own right to open each
    form (an owner or admin opens all of them)."""
    service = container.form_access_admin_service()
    grants = await container.form_access_grant_repo().direct_for_user(
        world.workspace.id, world.who.granted.id
    )
    assert grants
    assert await service._visible_titles(world.workspace.id, grants, world.who.editor) == {}
    seen = await service._visible_titles(world.workspace.id, grants, world.who.admin)
    assert seen == {str(world.closed.form_id): formData["title"]}


async def test_the_member_view_is_for_those_who_manage_members(
    client: AsyncClient, world, switch_on
):
    url = f"{api(world.workspace)}/members/{world.who.granted.id}/access"
    for user in (world.who.creator, world.who.editor, world.who.viewer):
        assert (await client.get(url, cookies=cookies(user))).status_code == 403


# -- 3. the picker ---------------------------------------------------------------------
async def test_the_creator_of_a_restricted_form_lists_who_could_be_added(
    client: AsyncClient, world, switch_on
):
    team = await team_with(
        world.workspace, world.who.viewer, world.who.reviewer, name="Research"
    )
    await team_with(world.workspace, name="Empty")
    url = form_url(world.workspace, world.closed.form_id, "/access/candidates")
    with statements() as seen:
        got = await client.get(url, cookies=cookies(world.who.creator))
    assert got.status_code == 200, got.text
    picked = got.json()
    listed = {m["id"]: m for m in picked["members"]}
    expected = [
        world.who.viewer,
        world.who.reviewer,
        world.who.editor,
        world.who.granted,
    ]
    for user in expected:
        assert listed[str(user.id)] == {"id": str(user.id), "name": name_of(user)}
    # no owner, admin, privacy officer, deactivated member or oneself
    for user in (
        world.who.owner,
        world.who.admin,
        world.who.officer,
        world.who.gone,
        world.who.creator,
    ):
        assert str(user.id) not in listed
    assert {(t["name"], t["memberCount"]) for t in picked["teams"]} == {
        ("Research", 2),
        ("Empty", 0),
    }
    assert {t["id"] for t in picked["teams"]} >= {str(team.id)}
    # nothing but ids, names and sizes; no address, no role, no grant
    assert "never-shown" not in got.text and "email" not in got.text.lower()
    assert all(set(m) == {"id", "name"} for m in picked["members"])
    assert all(set(t) == {"id", "name", "memberCount"} for t in picked["teams"])
    # a constant number of statements and nothing is audited
    assert len(seen) <= 20, len(seen)
    assert not await audit_events(world.workspace)


async def test_the_picker_is_for_whoever_may_change_the_circle(
    client: AsyncClient, world, switch_on
):
    url = form_url(world.workspace, world.closed.form_id, "/access/candidates")
    # an owner and an admin always may
    for user in (world.who.owner, world.who.admin):
        assert (await client.get(url, cookies=cookies(user))).status_code == 200
    # an Editor the form is closed to gets the answer of an unknown form
    assert (await client.get(url, cookies=cookies(world.who.editor))).status_code == 404
    unknown = form_url(world.workspace, "0" * 24, "/access/candidates")
    assert (await client.get(unknown, cookies=cookies(world.who.editor))).status_code == 404
    # a grantee who can edit the form may not widen who sees it
    await grant(world.workspace, world.closed.form_id, world.who.editor.id, ROLE_EDITOR)
    refused = await client.get(url, cookies=cookies(world.who.editor))
    assert refused.status_code == 403
    assert refused.json()["code"] == "access_manage_forbidden"
    # a Viewer holds no form.share, with a grant or without
    assert (await client.get(url, cookies=cookies(world.who.granted))).status_code == 403
    assert (await client.get(url, cookies=cookies(world.who.viewer))).status_code == 403


async def test_the_picker_never_crosses_a_workspace(
    client: AsyncClient, world, workspace_1, switch_on
):
    stranger = await add_member(workspace_1, "COLLABORATOR")
    await team_with(workspace_1, stranger, name="Elsewhere")
    foreign = await create_form(workspace_1, testUser1)
    got = await client.get(
        form_url(world.workspace, world.closed.form_id, "/access/candidates"),
        cookies=cookies(world.who.creator),
    )
    assert str(stranger.id) not in got.text and "Elsewhere" not in got.text
    # another workspace's form through this workspace's path is not found, and
    # a member of the other workspace has no standing here
    crossed = form_url(world.workspace, foreign.form_id, "/access/candidates")
    assert (await client.get(crossed, cookies=cookies(world.who.owner))).status_code == 404
    other = form_url(world.workspace, world.closed.form_id, "/access/candidates")
    assert (await client.get(other, cookies=cookies(stranger))).status_code == 403
    assert (
        await client.get(
            form_url(workspace_1, world.closed.form_id, "/access/candidates"),
            cookies=cookies(testUser1),
        )
    ).status_code == 404


async def test_the_picker_is_off_with_the_switch(client: AsyncClient, world, switch_off):
    for tail in ("/access/candidates", "/access/impact?mode=restricted"):
        got = await client.get(
            form_url(world.workspace, world.closed.form_id, tail),
            cookies=cookies(world.who.creator),
        )
        assert got.status_code == 422 and got.json()["code"] == "form_access_off"


# -- 4. team size and the dry run ---------------------------------------------------------
async def test_a_team_grant_carries_the_teams_size_and_a_person_grant_none(
    client: AsyncClient, world, switch_on
):
    team = await team_with(
        world.workspace, world.who.viewer, world.who.reviewer, world.who.editor, name="Ops"
    )
    for subject_type, subject in (("group", team.id), ("user", world.who.viewer.id)):
        put = await client.put(
            form_url(world.workspace, world.closed.form_id, "/grants"),
            cookies=cookies(world.who.creator),
            json={"subjectType": subject_type, "subjectId": str(subject), "role": "VIEWER"},
        )
        assert put.status_code == 200, put.text
        assert put.json()["memberCount"] == (3 if subject_type == "group" else None)
    got = await client.get(
        form_url(world.workspace, world.closed.form_id, "/access"),
        cookies=cookies(world.who.creator),
    )
    sizes = {g["subjectType"]: g["memberCount"] for g in got.json()["grants"]}
    assert sizes == {"group": 3, "user": None}


async def test_the_dry_run_counts_who_would_lose_access(
    client: AsyncClient, world, switch_on
):
    url = form_url(world.workspace, world.open.form_id, "/access/impact")
    with statements() as seen:
        got = await client.get(
            url, params={"mode": "restricted"}, cookies=cookies(world.who.owner)
        )
    assert got.status_code == 200, got.text
    # by role they open this form now: the Viewer, the Reviewer, both Editors
    # and the Viewer who holds a grant on the other form (that grant is on
    # another form: here only their role opens it); the owner (who made it)
    # and the Admin keep it, the Privacy officer keeps the structure, and a
    # deactivated member opens nothing now
    now = await container.authorization_service().member_ids_holding(
        world.workspace.id, world.open.form_id, P.FORM_READ
    )
    after = await container.authorization_service().member_ids_holding(
        world.workspace.id, world.open.form_id, P.FORM_READ, restricted=True
    )
    lost = {name for name, u in vars(world.who).items() if str(u.id) in (now - after)}
    assert lost == {"viewer", "reviewer", "creator", "editor", "granted"}, lost
    # (the workspace fixture holds one more Editor of its own)
    total = len(now - after)
    assert total == 6
    assert got.json() == {"mode": "restricted", "membersLosingAccess": total}
    assert len(seen) < 40
    # going the other way, or asking about a restricted form, loses nobody
    for form, mode in (
        (world.open, "workspace"),
        (world.closed, "restricted"),
        (world.closed, "workspace"),
    ):
        again = await client.get(
            form_url(world.workspace, form.form_id, "/access/impact"),
            params={"mode": mode},
            cookies=cookies(world.who.owner),
        )
        assert again.json() == {"mode": mode, "membersLosingAccess": 0}
    # grantees and teams count as keeping it
    await grant(world.workspace, world.open.form_id, world.who.viewer.id, ROLE_VIEWER)
    await team_with(world.workspace, world.who.reviewer, name="Keepers")
    team = (await container.member_group_repo().list_in_workspace(world.workspace.id))[0]
    await grant(world.workspace, world.open.form_id, team.id, ROLE_VIEWER, subject_type="group")
    after = await client.get(
        url, params={"mode": "restricted"}, cookies=cookies(world.who.owner)
    )
    assert after.json()["membersLosingAccess"] == total - 2
    # nothing was changed or recorded
    link = await container.workspace_form_repo().find_workspace_form(
        world.workspace.id, str(world.open.form_id)
    )
    assert link.settings.access_mode is None
    assert not await audit_events(world.workspace)


async def test_the_dry_run_is_for_whoever_changes_the_mode(
    client: AsyncClient, world, switch_on
):
    url = form_url(world.workspace, world.open.form_id, "/access/impact")
    ask = lambda user, **p: client.get(url, params=p or {"mode": "restricted"}, cookies=cookies(user))
    assert (await ask(world.who.admin)).status_code == 200
    # an Editor who did not create the form may not change its mode
    refused = await ask(world.who.editor)
    assert refused.status_code == 403 and refused.json()["code"] == "access_manage_forbidden"
    assert (await ask(world.who.viewer)).status_code == 403
    assert (await ask(world.who.owner, mode="nonsense")).status_code == 422
    assert (await client.get(url, cookies=cookies(world.who.owner))).status_code == 422


async def test_the_dry_run_never_crosses_a_workspace(
    client: AsyncClient, world, workspace_1, switch_on
):
    foreign = await create_form(workspace_1, testUser1)
    got = await client.get(
        form_url(world.workspace, foreign.form_id, "/access/impact"),
        params={"mode": "restricted"},
        cookies=cookies(world.who.owner),
    )
    assert got.status_code == 404


# -- 5. who gave the grant ------------------------------------------------------------------
async def test_a_grant_names_who_gave_it_when_they_are_a_member(
    client: AsyncClient, world, switch_on
):
    put = await client.put(
        form_url(world.workspace, world.closed.form_id, "/grants"),
        cookies=cookies(world.who.creator),
        json={"subjectType": "user", "subjectId": str(world.who.viewer.id), "role": "VIEWER"},
    )
    assert put.status_code == 200, put.text
    assert put.json()["grantedBy"] == name_of(world.who.creator)
    got = await client.get(
        form_url(world.workspace, world.closed.form_id, "/access"),
        cookies=cookies(world.who.creator),
    )
    grants = {g["subjectId"]: g for g in got.json()["grants"]}
    assert grants[str(world.who.viewer.id)]["grantedBy"] == name_of(world.who.creator)
    # a grant stored without a known giver, or by someone no longer a member
    assert grants[str(world.who.granted.id)]["grantedBy"] is None
    stranger = str(RecordId())
    repo = container.form_access_grant_repo()
    row = (await repo.list_for_form(world.workspace.id, world.closed.form_id))[0]
    row.created_by = stranger
    await repo.save_document(row)
    again = await client.get(
        form_url(world.workspace, world.closed.form_id, "/access"),
        cookies=cookies(world.who.creator),
    )
    assert all(g["grantedBy"] in (None, name_of(world.who.creator)) for g in again.json()["grants"])
    assert stranger not in {g["grantedBy"] for g in again.json()["grants"]}
    assert "never-shown" not in again.text


async def test_the_names_lookup_failing_leaves_the_names_out(
    client: AsyncClient, world, switch_on, monkeypatch
):
    directory = container.member_directory()
    monkeypatch.setattr(
        directory._http_client, "get", AsyncMock(side_effect=RuntimeError("down"))
    )
    got = await client.get(
        form_url(world.workspace, world.closed.form_id, "/access"),
        cookies=cookies(world.who.creator),
    )
    assert got.status_code == 200
    assert all(g["grantedBy"] is None for g in got.json()["grants"])
