"""Saving a form's groups replaces its set of groups, and leaves the links of
groups it keeps alone, in both stores."""

from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.postgres.forms import (
    PostgresFormRepository,
    PostgresWorkspaceFormRepository,
)
from backend.app.repositories.postgres.responses import (
    PostgresResponderGroupsRepository,
)
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from common.models.user import User
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.schemas.responder_group import ResponderGroupFormDocument
from backend.db.models import ResponderGroupFormRow
from tests.app.repositories.test_forms_parity import (  # noqa: F401
    form,
    seed_both,
    sessions,
    workspace_form,
)


async def _links(repo, form_id):
    if isinstance(repo, ResponderGroupsRepository):
        rows = await ResponderGroupFormDocument.find({"form_id": form_id}).to_list()
    else:
        rows = await repo._links(ResponderGroupFormRow.form_id == form_id)
    return {str(r.group_id): (str(r.id), r.created_at) for r in rows}


async def test_resaving_the_same_groups_keeps_their_links(sessions):
    for repo in (
        ResponderGroupsRepository(),
        PostgresResponderGroupsRepository(sessions),
    ):
        ws = PydanticObjectId()
        a, b, c = [await repo.create_group(ws, name) for name in ("A", "B", "C")]
        form_id = f"form-{ws}"
        await repo.add_groups_to_form(form_id, [a.id, b.id, c.id])
        before = await _links(repo, form_id)
        await repo.add_groups_to_form(form_id, [a.id, b.id, c.id])
        assert await _links(repo, form_id) == before, type(repo).__name__


async def test_saving_groups_replaces_the_set(sessions):
    for repo in (
        ResponderGroupsRepository(),
        PostgresResponderGroupsRepository(sessions),
    ):
        ws = PydanticObjectId()
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
    for repo in (
        ResponderGroupsRepository(),
        PostgresResponderGroupsRepository(sessions),
    ):
        name = type(repo).__name__
        ws_a, ws_b = PydanticObjectId(), PydanticObjectId()
        group_a, group_b = await _shared_form(repo, ws_a, ws_b, "shared")
        await repo.add_groups_to_form("only-b", [group_b.id])

        by_form = await repo.get_groups_by_form_ids(["shared", "only-b"], ws_a)
        assert [g["name"] for g in by_form["shared"]] == ["Group A"], name
        assert by_form["only-b"] == [], name
        by_form = await repo.get_groups_by_form_ids(["shared", "only-b"], ws_b)
        assert [g["name"] for g in by_form["shared"]] == ["Group B"], name
        assert [g["name"] for g in by_form["only-b"]] == ["Group B"], name
        assert await repo.get_groups_by_form_ids(["shared"], PydanticObjectId()) == {
            "shared": []
        }, name

        # every link stays visible to the save logic, with its owner
        owners = await repo.get_linked_group_owners("shared")
        assert {str(g): str(w) for g, w in owners.items()} == {
            str(group_a.id): str(ws_a),
            str(group_b.id): str(ws_b),
        }, name

        # B's groups neither admit nor refuse anyone on A's copy
        for who, in_a, in_b in (
            ("a@x.test", {"shared"}, set()),
            ("x@a.test", {"shared"}, set()),
            ("b@x.test", set(), {"shared", "only-b"}),
            ("x@b.test", set(), {"shared", "only-b"}),
            ("nobody@x.test", set(), set()),
        ):
            forms = ["shared", "only-b"]
            assert await repo.get_form_ids_accessible_to(forms, who, ws_a) == in_a, (
                name,
                who,
            )
            assert await repo.get_form_ids_accessible_to(forms, who, ws_b) == in_b, (
                name,
                who,
            )


async def test_both_form_stores_list_only_the_workspaces_own_groups(sessions):
    """The Mongo $lookup and the Postgres twin (over either store's groups)
    return the workspace's own groups, and a private shared form is open to its
    own groups' respondents only."""
    ws_a, ws_b = PydanticObjectId(), PydanticObjectId()
    for groups in (
        ResponderGroupsRepository(),
        PostgresResponderGroupsRepository(sessions),
    ):
        # a fresh form id per groups repository: each is seeded once
        form_id = f"shared-{type(groups).__name__}"
        responses = FormResponseRepository(crypto=container.crypto())
        mongo = FormRepository()
        postgres = PostgresFormRepository(sessions, groups, responses)
        mongo_wf = WorkspaceFormRepository()
        postgres_wf = PostgresWorkspaceFormRepository(sessions, groups)
        document = form(form_id, "Shared", 1)
        await seed_both((mongo, postgres), "save_form", document)
        await seed_both(
            (mongo_wf, postgres_wf),
            "save",
            workspace_form(ws_a, form_id, "u1", 1, private=True),
            workspace_form(ws_b, form_id, "u2", 2, private=True),
        )
        await _shared_form(groups, ws_a, ws_b, form_id)

        # the Mongo originals read the groups from Mongo only
        mongo_side = isinstance(groups, ResponderGroupsRepository)
        for repo in (mongo, postgres) if mongo_side else (postgres,):
            for ws, expected in ((ws_a, ["Group A"]), (ws_b, ["Group B"])):
                rows = await repo.get_forms_in_workspace(ws, [form_id], True)
                names = sorted(g["name"] for g in rows[0]["groups"])
                assert names == expected, (type(repo).__name__, type(groups).__name__)

        for repo in (mongo_wf, postgres_wf) if mongo_side else (postgres_wf,):
            for email, admitted_in in (
                ("a@x.test", ws_a),
                ("x@a.test", ws_a),
                ("b@x.test", ws_b),
                ("x@b.test", ws_b),
                ("nobody@x.test", None),
            ):
                user = User(id=str(PydanticObjectId()), sub=email)
                for ws in (ws_a, ws_b):
                    ids = await repo.get_form_ids_in_workspace(
                        ws, is_not_admin=True, user=user
                    )
                    assert (form_id in ids) == (ws == admitted_in), (
                        type(repo).__name__,
                        type(groups).__name__,
                        email,
                    )
