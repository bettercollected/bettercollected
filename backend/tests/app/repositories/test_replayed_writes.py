"""Replayed writes in dual-write mode: the Postgres mirror stores whatever the
Mongo primary persisted, including the documents a repository writes to its
group's other tables (form versions, deletion requests, workspace tags)."""

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.form_response_repository import FormResponseRepository
from backend.app.repositories.postgres.forms import PostgresFormRepository
from backend.app.repositories.postgres.responses import (
    PostgresFormResponseRepository,
    PostgresWorkspaceRespondersRepository,
)
from backend.app.repositories.responder_groups_repository import (
    ResponderGroupsRepository,
)
from backend.app.schemas.form_versions import FormVersionsDocument
from backend.app.schemas.standard_form_response import FormResponseDeletionRequest
from backend.app.schemas.workspace_responder import WorkspaceTags
from tests.app.repositories.test_forms_parity import form, sessions  # noqa: F401


def responses_repo():
    return FormResponseRepository(crypto=container.crypto())


async def test_a_published_version_is_mirrored_to_its_table(sessions):
    pg = PostgresFormRepository(sessions, ResponderGroupsRepository(), responses_repo())
    version = FormVersionsDocument(
        **form("pub1", "Published", 1).model_dump(mode="json"), version=1
    )
    version.id = PydanticObjectId()
    await pg.replay_write([version])
    stored = await pg.get_form_by_by_version("pub1", 1)
    assert stored is not None and stored.version == 1


async def test_a_deletion_request_is_mirrored_to_its_table(sessions):
    pg = PostgresFormResponseRepository(sessions, None, None)
    request = FormResponseDeletionRequest(
        id=PydanticObjectId(), form_id="f-del", response_id="r-del", provider="self"
    )
    await pg.replay_write([request])
    stored = await pg.find_deletion_request_by_response_id("r-del")
    assert stored is not None and stored.form_id == "f-del"


async def test_a_workspace_tag_is_mirrored_to_its_table(sessions):
    pg = PostgresWorkspaceRespondersRepository(sessions)
    workspace_id = PydanticObjectId()
    tag = WorkspaceTags(id=PydanticObjectId(), workspace_id=workspace_id, title="vip")
    await pg.replay_write([tag])
    assert [t.title for t in await pg.get_workspace_tags(workspace_id)] == ["vip"]


async def test_an_unknown_document_type_is_still_refused(sessions):
    pg = PostgresWorkspaceRespondersRepository(sessions)
    with pytest.raises(TypeError):
        await pg.replay_write(
            [FormResponseDeletionRequest(form_id="x", response_id="y")]
        )
