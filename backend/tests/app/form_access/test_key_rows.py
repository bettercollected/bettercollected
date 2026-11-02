"""An API key's rows (``form_access_grants`` with ``subject_type='key'``) and
the member-facing grant paths. A key's row is its allow-list entry for a form
and the most its role may do there; it is never a grant of the access routes. A
form's Editor, who may share the form, can neither see a key's row nor delete
it, and no audit entry of the grant routes ever names a key. Everything here is
synthetic."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.form_access_grant import (
    ROLE_EDITOR,
    ROLE_VIEWER,
    SUBJECT_KEY,
)
from backend.app.schemas.workspace_audit_event import (
    ACCESS_GRANT_ADDED,
    ACCESS_GRANT_CHANGED,
    ACCESS_GRANT_REMOVED,
)
from backend.app.repositories.postgres.form_access import AccessTargetNotFound
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    create_form,
    grant,
)
from tests.app.form_access.test_key_roles import admin_creator, make_key

pytestmark = pytest.mark.asyncio

GRANT_EVENTS = (ACCESS_GRANT_ADDED, ACCESS_GRANT_CHANGED, ACCESS_GRANT_REMOVED)


def form_url(workspace, form, tail="") -> str:
    return f"{api(workspace)}/forms/{form.form_id}{tail}"


@pytest.fixture()
async def keyed(workspace, workspace_form, switch_on):
    """A form with a key's row and a person's grant on it, and a form's Editor
    (who holds ``form.share``)."""
    admin = await admin_creator(workspace)
    key = await make_key(
        workspace, admin, form_scope="listed", forms=[workspace_form.form_id]
    )
    editor = await add_member(workspace, "COLLABORATOR")
    viewer = await add_member(workspace, "VIEWER")
    await grant(workspace, workspace_form.form_id, viewer.id, ROLE_VIEWER)
    row = await container.form_access_grant_repo().for_key_on_form(
        workspace.id, key.id, workspace_form.form_id
    )
    assert row is not None
    return {"key": key, "row": row, "editor": editor, "viewer": viewer}


# -- the access summary --------------------------------------------------------------
async def test_the_access_summary_never_lists_a_key_row(
    client: AsyncClient, workspace, workspace_form, keyed
):
    for user in (testUser, keyed["editor"]):
        body = (
            await client.get(
                form_url(workspace, workspace_form, "/access"), cookies=cookies(user)
            )
        ).json()
        assert body["grants"] is not None
        subjects = {(g["subjectType"], g["subjectId"]) for g in body["grants"]}
        assert subjects == {("user", keyed["viewer"].id)}
        assert str(keyed["row"].id) not in str(body)
        assert str(keyed["key"].id) not in str(body)


# -- deleting -----------------------------------------------------------------------
@pytest.mark.parametrize("who", ["owner", "editor"])
async def test_no_one_deletes_a_key_row_through_the_grant_route(
    client: AsyncClient, workspace, workspace_form, keyed, who
):
    user = testUser if who == "owner" else keyed["editor"]
    refused = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{keyed['row'].id}"),
        cookies=cookies(user),
    )
    assert refused.status_code == 404, refused.text
    # the same answer as for a grant id that is not there
    ghost = await client.delete(
        form_url(workspace, workspace_form, f"/grants/{'0' * 24}"), cookies=cookies(user)
    )
    assert (refused.status_code, refused.json()) == (ghost.status_code, ghost.json())
    # the row stays, and nothing was written to the audit log (least of all
    # the key's id as a team's)
    assert await container.form_access_grant_repo().for_key_on_form(
        workspace.id, keyed["key"].id, workspace_form.form_id
    ) is not None
    assert not await audit_events(workspace, *GRANT_EVENTS)
    assert str(keyed["key"].id) not in str(await audit_events(workspace))


async def test_a_grant_to_a_key_cannot_be_made_through_the_grant_route(
    client: AsyncClient, workspace, workspace_form, keyed
):
    put = await client.put(
        form_url(workspace, workspace_form, "/grants"),
        cookies=cookies(testUser),
        json={"subjectType": "key", "subjectId": str(keyed["key"].id), "role": "EDITOR"},
    )
    assert put.status_code == 422
    assert not await audit_events(workspace, *GRANT_EVENTS)


async def test_a_person_grant_with_a_keys_id_is_a_different_row(
    workspace, workspace_form, keyed
):
    """Id spaces never clash: every key-row read filters on the subject type
    and every member read filters on its own."""
    grants = container.form_access_grant_repo()
    stranger = await grant(
        workspace, workspace_form.form_id, keyed["key"].id, ROLE_EDITOR, subject_type="user"
    )
    assert stranger.id != keyed["row"].id
    assert [str(g.id) for g in await grants.for_key(workspace.id, keyed["key"].id)] == [
        str(keyed["row"].id)
    ]
    assert str(stranger.id) in {
        str(g.id) for g in await grants.list_for_form(workspace.id, workspace_form.form_id)
    }


# -- the repository -------------------------------------------------------------------
async def test_the_member_facing_reads_and_deletes_skip_key_rows(
    workspace, workspace_form, keyed
):
    grants = container.form_access_grant_repo()
    form_id, row = workspace_form.form_id, keyed["row"]
    assert str(row.id) not in {
        str(g.id) for g in await grants.list_for_form(workspace.id, form_id)
    }
    assert await grants.find(workspace.id, form_id, row.id) is None
    assert not await grants.delete(workspace.id, form_id, row.id)
    held = await grants.held_on_form(workspace.id, form_id)
    assert str(keyed["key"].id) not in held
    assert set(held) == {keyed["viewer"].id}
    assert await grants.for_user_on_form(workspace.id, form_id, str(keyed["key"].id)) == []
    assert await grants.for_user(workspace.id, str(keyed["key"].id)) == []
    # the key's own reads still see it
    assert (await grants.for_key_on_form(workspace.id, keyed["key"].id, form_id)).id == row.id
    assert [g.id for g in await grants.for_key(workspace.id, keyed["key"].id)] == [row.id]


async def test_the_decision_for_a_member_never_counts_a_key_row(
    workspace, workspace_form, keyed, switch_on
):
    """A key row naming a member's id (it cannot, ids differ in kind, but the
    decision must not depend on that) gives that member nothing."""
    from backend.app.models.enum.permission import Permission

    viewer = await add_member(workspace, "VIEWER")
    await grant(
        workspace, workspace_form.form_id, viewer.id, ROLE_EDITOR, subject_type=SUBJECT_KEY
    )
    held = await container.authorization_service().effective_permissions(
        viewer, workspace.id, form_id=workspace_form.form_id
    )
    assert Permission.FORM_EDIT not in held


async def test_a_forms_rows_go_with_the_form_and_a_keys_rows_with_the_key_only(
    workspace, workspace_form, keyed
):
    grants = container.form_access_grant_repo()
    other = await create_form(workspace, testUser)
    await grant(workspace, other.form_id, keyed["key"].id, ROLE_VIEWER, subject_type=SUBJECT_KEY)
    assert await grants.delete_for_subject(workspace.id, SUBJECT_KEY, keyed["key"].id) == 2
    assert await grants.for_key(workspace.id, keyed["key"].id) == []
    # the person's grant is still there
    assert len(await grants.list_for_form(workspace.id, workspace_form.form_id)) == 1
    # a form's deletion removes every row on it, a key's included
    await grant(workspace, other.form_id, keyed["key"].id, ROLE_VIEWER, subject_type=SUBJECT_KEY)
    assert await grants.delete_for_form(workspace.id, other.form_id) == 1
    assert await grants.for_key(workspace.id, keyed["key"].id) == []


# -- replace_for_key ---------------------------------------------------------------------
async def test_replace_for_key_makes_the_named_forms_the_keys_rows(
    workspace, workspace_form, keyed
):
    grants = container.form_access_grant_repo()
    other = await create_form(workspace, testUser)
    key_id = keyed["key"].id
    from backend.app.schemas.form_access_grant import FormAccessGrantDocument

    def doc(form, role=ROLE_VIEWER):
        return FormAccessGrantDocument(
            workspace_id=workspace.id, form_id=str(form.form_id),
            subject_type="user", subject_id="ignored", role=role,
        )

    saved = await grants.replace_for_key(
        workspace.id, key_id, [doc(other), doc(other, ROLE_EDITOR)]
    )
    # one row per form, always written as the key's, the last one named wins
    assert [(r.subject_type, str(r.subject_id), r.role) for r in saved] == [
        (SUBJECT_KEY, str(key_id), ROLE_EDITOR)
    ]
    rows = await grants.for_key(workspace.id, key_id)
    assert {r.form_id for r in rows} == {str(other.form_id)}  # the first form's row went
    # a person's grant on the same forms is untouched
    assert len(await grants.list_for_form(workspace.id, workspace_form.form_id)) == 1
    # naming nothing removes every row of the key
    assert await grants.replace_for_key(workspace.id, key_id, []) == []
    assert await grants.for_key(workspace.id, key_id) == []


async def test_replace_for_key_refuses_a_foreign_form_a_foreign_key_and_a_revoked_one(
    workspace, workspace_1, workspace_form, workspace_form_1, keyed
):
    from backend.app.schemas.form_access_grant import FormAccessGrantDocument

    grants = container.form_access_grant_repo()
    key = keyed["key"]

    def doc(form_id):
        return FormAccessGrantDocument(
            workspace_id=workspace.id, form_id=str(form_id),
            subject_type="key", subject_id=str(key.id), role=ROLE_VIEWER,
        )

    before = await grants.for_key(workspace.id, key.id)
    with pytest.raises(AccessTargetNotFound):  # a form of another workspace
        await grants.replace_for_key(workspace.id, key.id, [doc(workspace_form_1.form_id)])
    with pytest.raises(AccessTargetNotFound):  # a key of another workspace
        await grants.replace_for_key(workspace_1.id, key.id, [])
    # nothing changed
    assert [r.id for r in await grants.for_key(workspace.id, key.id)] == [r.id for r in before]
    key.revoked = True
    await container.workspace_api_key_repo().save(key)
    with pytest.raises(AccessTargetNotFound):
        await grants.replace_for_key(workspace.id, key.id, [doc(workspace_form.form_id)])
