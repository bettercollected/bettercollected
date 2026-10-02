"""Saving a form's groups replaces its set of groups, and leaves the links of
groups it keeps alone, in both stores."""

from beanie import PydanticObjectId

from backend.app.repositories.postgres.responses import (
    PostgresResponderGroupsRepository,
)
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.schemas.responder_group import ResponderGroupFormDocument
from backend.db.models import ResponderGroupFormRow
from tests.app.repositories.test_forms_parity import sessions  # noqa: F401


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
