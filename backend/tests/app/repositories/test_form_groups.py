"""Saving a form's groups replaces its set of groups, and leaves the links of
groups it keeps alone."""

from backend.app.repositories.postgres.responses import (
    PostgresResponderGroupsRepository,
)
from backend.db.models import ResponderGroupFormRow
from common.models.user import User
from common.records import RecordId
from tests.app.repositories.parity import sessions  # noqa: F401
from tests.app.repositories.test_forms_repositories import (
    form,
    form_repos,
    workspace_form,
)


async def _links(repo, form_id):
    rows = await repo._links(ResponderGroupFormRow.form_id == form_id)
    return {str(r.group_id): (str(r.id), r.created_at) for r in rows}


async def test_resaving_the_same_groups_keeps_their_links(sessions):
    repo = PostgresResponderGroupsRepository(sessions)
    ws = RecordId()
    a, b, c = [await repo.create_group(ws, name) for name in ("A", "B", "C")]
    form_id = f"form-{ws}"
    await repo.add_groups_to_form(form_id, [a.id, b.id, c.id])
    before = await _links(repo, form_id)
    await repo.add_groups_to_form(form_id, [a.id, b.id, c.id])
    assert await _links(repo, form_id) == before


async def test_saving_groups_replaces_the_set(sessions):
    repo = PostgresResponderGroupsRepository(sessions)
    ws = RecordId()
    a, b, c = [await repo.create_group(ws, name) for name in ("A", "B", "C")]
    form_id = f"form-{ws}"
    await repo.add_groups_to_form(form_id, [a.id, b.id])
    ids = [a.id, c.id]
    await repo.add_groups_to_form(form_id, ids)
    assert set(await _links(repo, form_id)) == {str(a.id), str(c.id)}
    assert ids == [a.id, c.id], "the caller's list must not be modified"


async def _shared_form(repo, ws_a, ws_b, form_id):
    """A form both workspaces hold, each with a group of its own: A's admits
    a@x.test and *@a.test, B's b@x.test and *@b.test."""
    group_a = await repo.create_group(ws_a, "Group A", regex=r".*@a\.test")
    group_b = await repo.create_group(ws_b, "Group B", regex=r".*@b\.test")
    await repo.add_emails_to_group(group_a.id, ["a@x.test"])
    await repo.add_emails_to_group(group_b.id, ["b@x.test"])
    await repo.add_groups_to_form(form_id, [group_a.id, group_b.id])
    return group_a, group_b


async def test_group_reads_are_scoped_to_the_requesting_workspace(sessions):
    repo = PostgresResponderGroupsRepository(sessions)
    ws_a, ws_b = RecordId(), RecordId()
    group_a, group_b = await _shared_form(repo, ws_a, ws_b, "shared")
    await repo.add_groups_to_form("only-b", [group_b.id])

    by_form = await repo.get_groups_by_form_ids(["shared", "only-b"], ws_a)
    assert [g["name"] for g in by_form["shared"]] == ["Group A"]
    assert by_form["only-b"] == []
    by_form = await repo.get_groups_by_form_ids(["shared", "only-b"], ws_b)
    assert [g["name"] for g in by_form["shared"]] == ["Group B"]
    assert [g["name"] for g in by_form["only-b"]] == ["Group B"]
    assert await repo.get_groups_by_form_ids(["shared"], RecordId()) == {"shared": []}

    # every link stays visible to the save logic, with its owner
    owners = await repo.get_linked_group_owners("shared")
    assert {str(g): str(w) for g, w in owners.items()} == {
        str(group_a.id): str(ws_a),
        str(group_b.id): str(ws_b),
    }

    # B's groups neither admit nor refuse anyone on A's copy
    forms = ["shared", "only-b"]
    for who, in_a, in_b in (
        ("a@x.test", {"shared"}, set()),
        ("x@a.test", {"shared"}, set()),
        ("b@x.test", set(), {"shared", "only-b"}),
        ("x@b.test", set(), {"shared", "only-b"}),
        ("nobody@x.test", set(), set()),
    ):
        assert await repo.get_form_ids_accessible_to(forms, who, ws_a) == in_a, who
        assert await repo.get_form_ids_accessible_to(forms, who, ws_b) == in_b, who


async def test_the_forms_repositories_use_only_the_workspaces_own_groups(sessions):
    """A private form held by two workspaces lists each one's own groups and is
    open to its own groups' respondents only."""
    ws_a, ws_b = RecordId(), RecordId()
    groups, forms, links = form_repos(sessions)
    await forms.save_form(form("shared", "Shared", 1))
    await links.save(workspace_form(ws_a, "shared", "u1", 1, private=True))
    await links.save(workspace_form(ws_b, "shared", "u2", 2, private=True))
    await _shared_form(groups, ws_a, ws_b, "shared")

    for ws, expected in ((ws_a, ["Group A"]), (ws_b, ["Group B"])):
        rows = await forms.get_forms_in_workspace(ws, ["shared"], True)
        assert sorted(g["name"] for g in rows[0]["groups"]) == expected

    for email, admitted_in in (
        ("a@x.test", ws_a),
        ("x@a.test", ws_a),
        ("b@x.test", ws_b),
        ("x@b.test", ws_b),
        ("nobody@x.test", None),
    ):
        user = User(id=str(RecordId()), sub=email)
        for ws in (ws_a, ws_b):
            ids = await links.get_form_ids_in_workspace(
                ws, is_not_admin=True, user=user
            )
            assert ("shared" in ids) == (ws == admitted_in), (email, ws)
