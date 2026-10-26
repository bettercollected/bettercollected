"""Replayed writes in dual-write mode: the Postgres mirror stores whatever the
Mongo primary persisted, including the documents a repository writes to its
group's other tables (deletion requests, workspace tags)."""

import pytest
from common.ids import RecordId

from backend.app.repositories.postgres.responses import (
    PostgresFormResponseRepository,
    PostgresWorkspaceRespondersRepository,
)
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from backend.app.schemas.workspace_responder import WorkspaceTags
from tests.app.repositories.parity import sessions  # noqa: F401
from tests.app.response_helpers import unlinked_scope


async def test_a_deletion_request_is_mirrored_to_its_table(sessions):
    pg = PostgresFormResponseRepository(sessions, None, None)
    request = FormResponseDeletionRequest(
        id=RecordId(), form_id="f-del", response_id="r-del", provider="self"
    )
    await pg.replay_write([request])
    (stored,) = await pg.list_deletion_requests_for_form_ids(
        unlinked_scope(RecordId(), "f-del")
    )
    assert stored.response_id == "r-del" and stored.form_id == "f-del"


async def test_a_workspace_tag_is_mirrored_to_its_table(sessions):
    pg = PostgresWorkspaceRespondersRepository(sessions)
    workspace_id = RecordId()
    tag = WorkspaceTags(id=RecordId(), workspace_id=workspace_id, title="vip")
    await pg.replay_write([tag])
    assert [t.title for t in await pg.get_workspace_tags(workspace_id)] == ["vip"]


async def test_an_unknown_document_type_is_still_refused(sessions):
    pg = PostgresWorkspaceRespondersRepository(sessions)
    with pytest.raises(TypeError):
        await pg.replay_write(
            [FormResponseDeletionRequest(form_id="x", response_id="y")]
        )
