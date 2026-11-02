"""Directory groups linked to teams: who may link, the switch, the audit trail and
-- above all -- that a team's members through a group are read from the
directory's own tables at call time, so a deprovisioned person, a person removed
from the group and a group deleted in the directory are out of the team at once.
Everything is synthetic."""

from types import SimpleNamespace

import pytest
from common.ids import RecordId
from common.records import derived_id
from common.models.user import User

from backend.app.container import container
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_access_grant import ROLE_REVIEWER
from backend.app.schemas.scim import ScimGroupDocument, ScimGroupTeamLinkDocument
from backend.app.schemas.workspace_audit_event import TEAM_LINKED
from backend.app.services.form_access.model import SOURCE_GRANT
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    fail_audit,
    grant,
    restrict,
    team_with,
)
from tests.app.controllers.data import testUser
from tests.app.scim_helpers import (  # noqa: F401 -- fixtures
    create_directory,
    deliver,
    event,
    group_data,
    members_list,
    scim_on,
    user_data,
)
from tests.app.sso_helpers import DOMAIN, sso_on  # noqa: F401 -- fixture

pytestmark = pytest.mark.asyncio

JANE = "jane@" + DOMAIN
BOB = "bob@" + DOMAIN
P = Permission


def scim_url(workspace, group, suffix="/team"):
    return f"{api(workspace)}/scim/groups/{group}{suffix}"


async def provision(world, polis_id, email, groups=()):
    """The directory creates the person and puts them in these groups
    ((polis id, name) pairs); returns the person as a ``User``."""
    for kind, data in [("user.created", user_data(polis_id, email))] + [
        ("group.user_added", {**user_data(polis_id, email), "group": group_data(*pair)})
        for pair in groups
    ]:
        reply = await deliver(
            world.client, world.directory, world.polis, event(world.directory, kind, data)
        )
        assert reply.status_code == 200, reply.text
    account = world.auth.accounts[email.lower()]
    return User(id=account["id"], sub=email)


async def leave(world, polis_id, email, group):
    reply = await deliver(
        world.client,
        world.directory,
        world.polis,
        event(
            world.directory,
            "group.user_removed",
            {**user_data(polis_id, email), "group": group_data(*group)},
        ),
    )
    assert reply.status_code == 200, reply.text


async def scim_group(world, polis_id):
    return await container.scim_group_repo().find(world.directory.id, polis_id)


async def linked_team(world, polis_id):
    """The id of the team the directory group feeds, or None."""
    group = await scim_group(world, polis_id)
    link = await container.scim_group_team_link_repo().find(world.workspace.id, group.id)
    return str(link.team_id) if link is not None else None


async def link(world, polis_id, team, by=testUser):
    group = await scim_group(world, polis_id)
    return await world.client.put(
        scim_url(world.workspace, group.id),
        cookies=cookies(by),
        json={"teamId": str(team.id)},
    )


async def unlink(world, polis_id, by=testUser):
    group = await scim_group(world, polis_id)
    return await world.client.delete(
        scim_url(world.workspace, group.id), cookies=cookies(by)
    )


async def opens(user, world):
    """Whether the person may open the (restricted) form, and through what."""
    decided = await container.authorization_service().form_permissions(
        user, world.workspace.id, world.form.form_id
    )
    return P.FORM_READ in decided.permissions, decided.source


@pytest.fixture()
async def world(client, workspace, workspace_form, scim_on, members_list, switch_on):
    polis, auth = scim_on
    directory, _ = await create_directory(client, workspace, cookies(testUser), polis)
    for polis_id, name in (("g-hr", "Human resources"), ("g-it", "IT")):
        reply = await deliver(
            client, directory, polis, event(directory, "group.created", group_data(polis_id, name))
        )
        assert reply.status_code == 200, reply.text
    await restrict(workspace, workspace_form.form_id)
    team = await team_with(workspace, name="Hiring")
    await grant(
        workspace, workspace_form.form_id, team.id, ROLE_REVIEWER, subject_type="group"
    )
    return SimpleNamespace(
        client=client,
        workspace=workspace,
        form=workspace_form,
        directory=directory,
        polis=polis,
        auth=auth,
        team=team,
    )


# -- the switch ----------------------------------------------------------------------
async def test_both_routes_answer_422_while_the_switch_is_off(world, switch_off):
    for call in (link(world, "g-hr", world.team), unlink(world, "g-hr")):
        reply = await call
        assert reply.status_code == 422, reply.text
        assert reply.json()["code"] == "form_access_off"
    assert await linked_team(world, "g-hr") is None
    assert not await audit_events(world.workspace, TEAM_LINKED)


async def test_a_link_made_while_on_is_kept_but_decides_nothing_while_off(
    world, monkeypatch
):
    from backend.config import settings

    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    assert (await link(world, "g-hr", world.team)).status_code == 200
    assert (await opens(jane, world))[0] is True

    monkeypatch.setattr(settings.form_access, "ENABLED", False)
    # the stored link stays, and the form is decided by the role alone
    assert await linked_team(world, "g-hr") == str(world.team.id)
    assert (await opens(jane, world))[1] != SOURCE_GRANT


# -- who may link ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "role", ["ADMIN", "COLLABORATOR", "REVIEWER", "VIEWER", "PRIVACY_OFFICER"]
)
async def test_only_the_owner_links_or_unlinks(world, role):
    assert (await link(world, "g-hr", world.team)).status_code == 200
    member = await add_member(world.workspace, role)
    assert (await link(world, "g-it", world.team, by=member)).status_code == 403
    assert (await unlink(world, "g-hr", by=member)).status_code == 403
    assert await linked_team(world, "g-it") is None
    assert await linked_team(world, "g-hr") == str(world.team.id)
    assert len(await audit_events(world.workspace, TEAM_LINKED)) == 1


async def test_the_group_and_the_team_must_be_the_workspaces_own(world, workspace_1):
    foreign_team = await team_with(workspace_1, name="Elsewhere")
    reply = await link(world, "g-hr", foreign_team)
    assert reply.status_code == 404
    assert await linked_team(world, "g-hr") is None

    foreign_group = await container.scim_group_repo().save(
        ScimGroupDocument(
            directory_id=RecordId(),
            workspace_id=workspace_1.id,
            polis_group_id="g-x",
            name="Foreign",
        )
    )
    for group_id, team_id in (
        (str(foreign_group.id), str(world.team.id)),
        ("not-an-id", str(world.team.id)),
        ("0" * 24, str(world.team.id)),
    ):
        reply = await world.client.put(
            scim_url(world.workspace, group_id),
            cookies=cookies(testUser),
            json={"teamId": team_id},
        )
        assert reply.status_code == 404, (group_id, reply.text)
    for team_id in ("nope", "0" * 24):
        group = await scim_group(world, "g-hr")
        reply = await world.client.put(
            scim_url(world.workspace, group.id),
            cookies=cookies(testUser),
            json={"teamId": team_id},
        )
        assert reply.status_code == 404, team_id
    assert not await audit_events(world.workspace, TEAM_LINKED)
    assert await container.scim_group_team_link_repo().by_group(workspace_1.id) == {}


async def test_a_link_that_cannot_be_recorded_is_not_made(world, monkeypatch):
    fail_audit(monkeypatch)
    reply = await link(world, "g-hr", world.team)
    assert reply.status_code == 503
    assert reply.json()["code"] == "audit_unavailable"
    assert await linked_team(world, "g-hr") is None


# -- membership is read, not copied -------------------------------------------------
async def test_the_members_of_a_linked_group_are_in_the_team_and_a_grant_reaches_them(
    world,
):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    bob = await provision(world, "u2", BOB, groups=[("g-it", "IT")])
    assert (await opens(jane, world))[0] is False  # restricted, and no link yet

    reply = await link(world, "g-hr", world.team)
    assert reply.status_code == 200, reply.text
    assert reply.json()["teamId"] == str(world.team.id)

    assert await opens(jane, world) == (True, SOURCE_GRANT)
    assert (await opens(bob, world))[0] is False
    # nothing was copied into the team's own member rows
    repo = container.member_group_repo()
    assert await repo.manual_member_ids(world.workspace.id, world.team.id) == []
    assert await repo.member_ids(world.workspace.id, world.team.id) == [jane.id]
    assert await repo.group_ids_of(world.workspace.id, jane.id) == [str(world.team.id)]
    assert await repo.member_counts(world.workspace.id) == {str(world.team.id): 1}

    # the member's own view lists the team, the team page says how she is in it
    seen = await world.client.get(
        f"{api(world.workspace)}/members/{jane.id}/access", cookies=cookies(testUser)
    )
    assert [t["id"] for t in seen.json()["teams"]] == [str(world.team.id)]
    detail = (
        await world.client.get(
            f"{api(world.workspace)}/member-groups/{world.team.id}",
            cookies=cookies(testUser),
        )
    ).json()
    assert [(m["userId"], m["viaDirectory"]) for m in detail["members"]] == [(jane.id, True)]
    assert detail["linkedGroups"] == 1 and detail["memberCount"] == 1

    # unlinking takes them out; nobody and nothing is deleted
    assert (await unlink(world, "g-hr")).status_code == 200
    assert (await opens(jane, world))[0] is False
    assert await linked_team(world, "g-hr") is None
    assert len(await container.form_access_grant_repo().list_for_form(
        world.workspace.id, world.form.form_id
    )) == 1


async def test_deprovisioning_takes_the_person_out_of_the_team_at_once(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    assert (await opens(jane, world))[0] is True

    # the directory deactivates her: the very next read has her out of the team
    # (no sync step, no job) and the grant stops reaching her
    reply = await deliver(
        world.client,
        world.directory,
        world.polis,
        event(world.directory, "user.updated", user_data("u1", JANE, active=False)),
    )
    assert reply.status_code == 200, reply.text
    repo = container.member_group_repo()
    assert await repo.member_ids(world.workspace.id, world.team.id) == []
    assert await repo.member_counts(world.workspace.id) == {}
    assert (await opens(jane, world))[0] is False

    # provisioned again: she is back, nothing was left to restore
    await deliver(
        world.client,
        world.directory,
        world.polis,
        event(world.directory, "user.updated", user_data("u1", JANE)),
    )
    assert await repo.member_ids(world.workspace.id, world.team.id) == [jane.id]
    assert (await opens(jane, world))[0] is True


async def test_a_person_deleted_in_the_directory_is_out_at_once(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    reply = await deliver(
        world.client,
        world.directory,
        world.polis,
        event(world.directory, "user.deleted", user_data("u1", JANE)),
    )
    assert reply.status_code == 200, reply.text
    assert await container.member_group_repo().member_ids(
        world.workspace.id, world.team.id
    ) == []
    assert (await opens(jane, world))[0] is False


async def test_leaving_the_group_in_the_directory_takes_the_person_out(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    assert (await opens(jane, world))[0] is True
    await leave(world, "u1", JANE, ("g-hr", "Human resources"))
    # still an active member of the workspace, no longer in the team
    assert await container.member_group_repo().member_ids(
        world.workspace.id, world.team.id
    ) == []
    assert (await opens(jane, world))[0] is False


async def test_a_group_deleted_in_the_directory_is_unlinked_and_audited(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    group = await scim_group(world, "g-hr")
    reply = await deliver(
        world.client,
        world.directory,
        world.polis,
        event(world.directory, "group.deleted", group_data("g-hr", "Human resources")),
    )
    assert reply.status_code == 200, reply.text
    assert (await opens(jane, world))[0] is False
    # the team and its grant stay; the team is empty
    assert await container.member_group_repo().find(world.workspace.id, world.team.id)
    first, second = await audit_events(world.workspace, TEAM_LINKED)
    assert (first.linked, second.linked) == (True, False)
    assert second.user_id == "scim"
    assert (second.group_id, second.scim_group_id) == (str(world.team.id), str(group.id))


async def test_a_disabled_membership_is_not_in_the_team(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    membership = await container.workspace_user_repo().find_workspace_user(
        world.workspace.id, jane.id
    )
    membership.disabled = True
    await container.workspace_user_repo().save(membership)
    assert await container.member_group_repo().member_ids(
        world.workspace.id, world.team.id
    ) == []
    assert (await opens(jane, world))[0] is False


async def test_a_link_never_reaches_a_team_of_another_workspace(world, workspace_1):
    """Even a link written straight to the table (which the routes refuse) names
    a team that is not this workspace's: nobody is in it here."""
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    foreign = await team_with(workspace_1, name="Elsewhere")
    group = await scim_group(world, "g-hr")
    await container.scim_group_team_link_repo().save_document(
        ScimGroupTeamLinkDocument(
            id=derived_id("scim_group_team_link", str(group.id)),
            group_id=group.id,
            team_id=foreign.id,
            workspace_id=world.workspace.id,
        )
    )
    await grant(
        world.workspace, world.form.form_id, foreign.id, ROLE_REVIEWER, subject_type="group"
    )
    repo = container.member_group_repo()
    assert await repo.member_ids(world.workspace.id, foreign.id) == []
    assert await repo.member_ids(workspace_1.id, foreign.id) == []
    assert await repo.group_ids_of(world.workspace.id, jane.id) == []
    assert (await opens(jane, world))[0] is False


# -- one group, one team; several groups, one team --------------------------------------
async def test_linking_a_group_again_moves_it_and_a_team_may_take_several_groups(world):
    other = await team_with(world.workspace, name="Recruiting")
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    bob = await provision(world, "u2", BOB, groups=[("g-it", "IT")])

    await link(world, "g-hr", world.team)
    await link(world, "g-it", world.team)
    repo = container.member_group_repo()
    assert sorted(await repo.member_ids(world.workspace.id, world.team.id)) == sorted(
        [jane.id, bob.id]
    )
    listed = (
        await world.client.get(
            f"{api(world.workspace)}/member-groups", cookies=cookies(testUser)
        )
    ).json()
    by_name = {t["name"]: t for t in listed}
    assert (by_name["Hiring"]["linkedGroups"], by_name["Hiring"]["memberCount"]) == (2, 2)

    # a person in both groups is one member, and also listed by hand: still one
    await deliver(
        world.client,
        world.directory,
        world.polis,
        event(
            world.directory,
            "group.user_added",
            {**user_data("u1", JANE), "group": group_data("g-it", "IT")},
        ),
    )
    await repo.add_member(world.workspace.id, world.team.id, jane.id)
    assert sorted(await repo.member_ids(world.workspace.id, world.team.id)) == sorted(
        [jane.id, bob.id]
    )
    assert (await repo.member_counts(world.workspace.id))[str(world.team.id)] == 2

    # a group is in one team: linking it elsewhere moves it
    reply = await link(world, "g-it", other)
    assert reply.status_code == 200
    assert reply.json()["teamId"] == str(other.id)
    assert await repo.member_ids(world.workspace.id, world.team.id) == [jane.id]
    assert sorted(await repo.member_ids(world.workspace.id, other.id)) == sorted(
        [jane.id, bob.id]
    )

    events = await audit_events(world.workspace, TEAM_LINKED)
    assert [(e.group_id, e.linked) for e in events] == [
        (str(world.team.id), True),
        (str(world.team.id), True),
        (str(world.team.id), False),
        (str(other.id), True),
    ]


async def test_linking_the_same_team_again_changes_and_records_nothing(world):
    await link(world, "g-hr", world.team)
    assert (await link(world, "g-hr", world.team)).status_code == 200
    assert len(await audit_events(world.workspace, TEAM_LINKED)) == 1
    await unlink(world, "g-hr")
    assert (await unlink(world, "g-hr")).status_code == 200
    assert len(await audit_events(world.workspace, TEAM_LINKED)) == 2


async def test_the_audit_rows_hold_ids_only(world):
    await link(world, "g-hr", world.team)
    await unlink(world, "g-hr")
    group = await scim_group(world, "g-hr")
    for entry in await audit_events(world.workspace, TEAM_LINKED):
        assert entry.user_id == str(testUser.id)
        assert (entry.group_id, entry.scim_group_id) == (str(world.team.id), str(group.id))
        text = str(entry.model_dump(mode="json"))
        for name in ("Hiring", "Human resources", JANE):
            assert name not in text


# -- the members of a linked team ----------------------------------------------------------
async def test_a_person_in_through_the_directory_is_removed_there_not_here(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    reply = await world.client.delete(
        f"{api(world.workspace)}/member-groups/{world.team.id}/members/{jane.id}",
        cookies=cookies(testUser),
    )
    assert reply.status_code == 409
    assert reply.json()["code"] == "managed_by_directory"
    assert (await opens(jane, world))[0] is True
    # a person who is in no way in the team is still the plain 404
    stranger = await add_member(world.workspace, "VIEWER")
    reply = await world.client.delete(
        f"{api(world.workspace)}/member-groups/{world.team.id}/members/{stranger.id}",
        cookies=cookies(testUser),
    )
    assert reply.status_code == 404


async def test_a_listed_member_who_is_also_in_the_directory_group_is_removed_by_hand(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    await container.member_group_repo().add_member(
        world.workspace.id, world.team.id, jane.id
    )
    reply = await world.client.delete(
        f"{api(world.workspace)}/member-groups/{world.team.id}/members/{jane.id}",
        cookies=cookies(testUser),
    )
    assert reply.status_code == 204
    # still in through the directory
    assert (await opens(jane, world))[0] is True


async def test_deleting_a_team_unlinks_its_groups(world):
    await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    reply = await world.client.delete(
        f"{api(world.workspace)}/member-groups/{world.team.id}",
        cookies=cookies(testUser),
    )
    assert reply.status_code == 204
    assert await linked_team(world, "g-hr") is None
    overview = await world.client.get(
        f"{api(world.workspace)}/scim", cookies=cookies(testUser)
    )
    assert {g["name"]: g["teamId"] for g in overview.json()["groups"]} == {
        "Human resources": None,
        "IT": None,
    }


async def test_the_directory_settings_say_which_team_each_group_feeds(world):
    await link(world, "g-it", world.team)
    overview = (
        await world.client.get(f"{api(world.workspace)}/scim", cookies=cookies(testUser))
    ).json()
    assert overview["canManage"] is True
    assert {g["name"]: g["teamId"] for g in overview["groups"]} == {
        "Human resources": None,
        "IT": str(world.team.id),
    }
    # an Admin sees the same page, and may not change it
    admin = await add_member(world.workspace, "ADMIN")
    seen = (
        await world.client.get(f"{api(world.workspace)}/scim", cookies=cookies(admin))
    ).json()
    assert seen["canManage"] is False


# -- the link is not part of the group document ---------------------------------------
async def test_a_stale_group_save_after_an_unlink_does_not_bring_the_link_back(world):
    """The directory sync, the role mapping and a rotation save a whole group
    document read earlier. The link is a row of its own, so none of them can
    restore it."""
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    stale = await scim_group(world, "g-hr")  # read while linked
    assert (await unlink(world, "g-hr")).status_code == 200
    stale.name = "Human resources (renamed)"
    await container.scim_group_repo().save(stale)  # a blind whole-document save
    assert await linked_team(world, "g-hr") is None
    assert await container.member_group_repo().member_ids(world.workspace.id, world.team.id) == []
    assert (await opens(jane, world))[0] is False


async def test_a_stale_group_save_after_a_team_delete_does_not_bring_the_link_back(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    stale = await scim_group(world, "g-hr")
    deleted = await world.client.delete(
        f"{api(world.workspace)}/member-groups/{world.team.id}", cookies=cookies(testUser)
    )
    assert deleted.status_code == 204
    await container.scim_group_repo().save(stale)
    assert await linked_team(world, "g-hr") is None
    assert await container.scim_group_team_link_repo().link_counts(world.workspace.id) == {}
    assert (await opens(jane, world))[0] is False


async def test_a_link_survives_every_writer_of_the_group_document(world):
    """A group event, the role mapping and a rotation's mark all save the group;
    the link stays."""
    await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    group = await scim_group(world, "g-hr")
    reply = await world.client.put(
        f"{api(world.workspace)}/scim/groups/{group.id}",
        cookies=cookies(testUser),
        json={"role": "VIEWER"},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["teamId"] == str(world.team.id)
    group = await scim_group(world, "g-hr")
    group.replaced = True
    await container.scim_group_repo().save(group)
    await leave(world, "u1", JANE, ("g-hr", "Human resources"))
    await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    assert await linked_team(world, "g-hr") == str(world.team.id)


async def test_group_events_racing_an_unlink_never_restore_the_link(world):
    import asyncio

    await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    group = await scim_group(world, "g-hr")
    sync = container.scim_sync_service()
    data = group_data("g-hr", "Human resources")
    events = [sync.apply_group(world.directory, data) for _ in range(8)]
    unlinking = world.client.delete(
        scim_url(world.workspace, group.id), cookies=cookies(testUser)
    )
    results = await asyncio.gather(*events, unlinking)
    assert results[-1].status_code == 200
    assert await linked_team(world, "g-hr") is None
    # and the other way: linking while events arrive keeps the link
    events = [sync.apply_group(world.directory, data) for _ in range(8)]
    results = await asyncio.gather(
        *events,
        world.client.put(
            scim_url(world.workspace, group.id),
            cookies=cookies(testUser),
            json={"teamId": str(world.team.id)},
        ),
    )
    assert results[-1].status_code == 200
    assert await linked_team(world, "g-hr") == str(world.team.id)


async def test_a_group_dropped_by_the_directory_takes_its_link_row_with_it(world):
    await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    await deliver(
        world.client,
        world.directory,
        world.polis,
        event(world.directory, "group.deleted", group_data("g-hr", "Human resources")),
    )
    assert await container.scim_group_team_link_repo().link_counts(world.workspace.id) == {}


async def test_a_large_directory_team_lists_a_page_of_people_and_the_total(
    world, monkeypatch
):
    from backend.app.services.form_access import admin as admin_module

    monkeypatch.setattr(admin_module, "MAX_SHOWN_MEMBERS", 2)
    for n in range(4):
        await provision(world, f"u{n}", f"p{n}@{DOMAIN}", groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    detail = (
        await world.client.get(
            f"{api(world.workspace)}/member-groups/{world.team.id}", cookies=cookies(testUser)
        )
    ).json()
    assert detail["memberCount"] == 4
    assert len(detail["members"]) == 2 and detail["membersTruncated"] is True


async def test_a_person_listed_by_hand_and_in_the_group_is_flagged_as_both(world):
    jane = await provision(world, "u1", JANE, groups=[("g-hr", "Human resources")])
    await link(world, "g-hr", world.team)
    await container.member_group_repo().add_member(world.workspace.id, world.team.id, jane.id)
    detail = (
        await world.client.get(
            f"{api(world.workspace)}/member-groups/{world.team.id}", cookies=cookies(testUser)
        )
    ).json()
    (member,) = detail["members"]
    assert (member["viaDirectory"], member["alsoViaDirectory"]) == (False, True)
