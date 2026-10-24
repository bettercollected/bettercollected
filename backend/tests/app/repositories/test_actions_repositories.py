"""The actions repository (actions and each workspace's copy of one), Postgres
only since 4.1. The behaviour it had under the dual run (where these steps ran
against the Mongo original too) stays pinned here, with the stored rows and
what the action runner is handed. Secrets are encrypted (Fernet, a fresh
token each time), so they are compared decrypted. Skipped unless DATABASE_URL
points at a *_test database."""

import json

import pytest
from sqlalchemy import select

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.models.workspace import WorkspaceRequestWithActionDto
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.repositories.postgres.identity import PostgresWorkspaceRepository
from backend.app.schemas.action_document import ActionDocument, WorkspaceActionsDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.db.models import ActionRow, WorkspaceActionRow
from common.models.standard_form import ParameterValue
from common.models.user import User
from common.records import RecordId
from tests.app.db import beanie_originals

WORKSPACE = RecordId("65f0a1b2c3d4e5f600000001")
OTHER_WORKSPACE = RecordId("65f0a1b2c3d4e5f600000002")
UNKNOWN = RecordId("65f0a1b2c3d4e5f6000000ff")
USER = User(id="65f0a1b2c3d4e5f600000010", sub="creator@example.org")


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


@pytest.fixture
def repo(sessions):
    return PostgresActionRepository(sessions, container.crypto())


def _dto(name, secrets=None):
    return ActionDto(
        name=name,
        title=f"{name} title",
        action_code="print('hi')",
        parameters=[ParameterValue(name="p", value="v", required=True)],
        secrets=[ParameterValue(name=k, value=v) for k, v in (secrets or {}).items()],
        type="script",
    )


def _secrets(document):
    """The action's secrets as the code reads them: decrypted."""
    crypto = container.crypto()
    return {s.name: crypto.decrypt(s.value) for s in document.secrets or []}


async def _rows(sessions, row):
    async with sessions() as session:
        return (
            (await session.execute(select(row).order_by(row.created_at, row.id)))
            .scalars()
            .all()
        )


async def test_actions_are_created_read_and_listed(repo):
    assert await repo.get_all_actions() == []
    first = await repo.create_action(
        WORKSPACE, _dto("first", {"token": "s3cret", "other": "two"}), USER
    )
    unencrypted = _dto("global")
    unencrypted.secrets = None
    global_action = await repo.create_global_action(unencrypted, USER)

    assert isinstance(first, ActionDocument) and first.id is not None
    assert first.created_by == RecordId(USER.id)
    assert _secrets(first) == {"token": "s3cret", "other": "two"}
    assert global_action.secrets is None
    assert [a.name for a in await repo.get_all_actions()] == ["first", "global"]

    found = await repo.get_action_by_id(first.id)
    assert found.model_dump() == first.model_dump()
    assert await repo.get_action_by_id(UNKNOWN) is None
    # in stored order, whatever the order asked for; unknown ids are skipped
    by_ids = await repo.get_actions_by_ids([global_action.id, first.id, UNKNOWN])
    assert [a.id for a in by_ids] == [first.id, global_action.id]
    assert await repo.get_actions_by_ids([]) == []


async def test_secrets_are_stored_encrypted(repo, sessions):
    created = await repo.create_action(WORKSPACE, _dto("x", {"k": "plain"}), USER)
    stored = await repo.get_action_by_id(created.id)
    assert stored.secrets[0].value != "plain"
    assert _secrets(stored) == {"k": "plain"}
    docs = [row.doc for row in await _rows(sessions, ActionRow)]
    assert docs and "plain" not in json.dumps(docs)


async def test_a_workspace_copy_is_created_then_updated_in_place(repo):
    first = await repo.create_action(WORKSPACE, _dto("first"), USER)
    assert await repo.get_workspace_action(WORKSPACE, first.id) is None

    copy = await repo.create_action_in_workspace_from_action(
        WORKSPACE, first.id, "encrypted-credentials"
    )
    assert isinstance(copy, WorkspaceActionsDocument)
    assert (copy.workspace_id, copy.action_id) == (WORKSPACE, first.id)
    assert copy.secrets == [
        ParameterValue(name="Credentials", value="encrypted-credentials")
    ]
    again = await repo.create_action_in_workspace_from_action(WORKSPACE, first.id)
    assert again.id == copy.id and again.secrets is None
    stored = await repo.get_workspace_action(WORKSPACE, first.id)
    assert stored.id == copy.id and stored.secrets is None

    other = await repo.create_action_in_workspace_from_action(
        OTHER_WORKSPACE, first.id, "other-credentials"
    )
    assert other.id != copy.id
    found = await repo.get_workspace_action(OTHER_WORKSPACE, first.id)
    assert found.secrets[0].value == "other-credentials"
    assert await repo.get_workspace_action(OTHER_WORKSPACE, UNKNOWN) is None


async def test_deleting_an_action_deletes_every_copy_of_it_and_nothing_else(repo):
    first = await repo.create_action(WORKSPACE, _dto("first"), USER)
    kept = await repo.create_global_action(_dto("kept"), USER)
    for workspace_id in (WORKSPACE, OTHER_WORKSPACE):
        await repo.create_action_in_workspace_from_action(workspace_id, first.id, "c")
    kept_copy = await repo.create_action_in_workspace_from_action(WORKSPACE, kept.id)

    assert await repo.delete_action(first.id) == first.id
    assert await repo.get_action_by_id(first.id) is None
    assert await repo.get_workspace_action(WORKSPACE, first.id) is None
    assert await repo.get_workspace_action(OTHER_WORKSPACE, first.id) is None
    assert (await repo.get_workspace_action(WORKSPACE, kept.id)).id == kept_copy.id
    assert [a.id for a in await repo.get_all_actions()] == [kept.id]
    # an unknown id deletes nothing and is handed back
    assert await repo.delete_action(UNKNOWN) == UNKNOWN
    assert [a.id for a in await repo.get_all_actions()] == [kept.id]


async def test_the_stored_rows_keep_their_4_0_shape(repo, sessions):
    """Ids as ObjectIds, the spine columns filled; the workspace an action is
    created in is not part of the stored action (it never was)."""
    action = await repo.create_action(WORKSPACE, _dto("a", {"k": "v"}), USER)
    copy = await repo.create_action_in_workspace_from_action(
        WORKSPACE, action.id, "creds"
    )
    (row,) = await _rows(sessions, ActionRow)
    assert (row.id, row.name, row.created_by, row.type) == (
        str(action.id),
        "a",
        USER.id,
        "script",
    )
    assert row.doc["_id"] == {"$oid": str(action.id)}
    assert row.doc["created_by"] == {"$oid": USER.id}
    assert set(row.doc) == {
        "_id",
        "created_at",
        "updated_at",
        "name",
        "title",
        "description",
        "action_code",
        "created_by",
        "parameters",
        "secrets",
        "type",
        "predefined",
        "url",
    }
    (copy_row,) = await _rows(sessions, WorkspaceActionRow)
    assert (copy_row.id, copy_row.workspace_id, copy_row.action_id) == (
        str(copy.id),
        str(WORKSPACE),
        str(action.id),
    )
    assert copy_row.doc["workspace_id"] == {"$oid": str(WORKSPACE)}
    assert copy_row.doc["action_id"] == {"$oid": str(action.id)}
    assert copy_row.doc["settings"] == {"is_public": False}
    assert copy_row.doc["secrets"] == [
        {"name": "Credentials", "value": "creds", "required": False}
    ]
    assert copy_row.doc["parameters"] is None


async def test_the_action_runner_is_handed_the_same_action(repo):
    """The job input carries ``action.json()``: the same JSON the Beanie
    document gave before the move."""
    action = await repo.create_action(WORKSPACE, _dto("a", {"k": "v"}), USER)
    stored = await repo.get_action_by_id(action.id)
    original = beanie_originals.ActionDocument.model_validate(
        stored.model_dump(by_alias=True)
    )
    assert stored.model_dump_json() == original.model_dump_json()
    assert json.loads(stored.model_dump_json())["id"] == str(action.id)


async def test_a_workspace_is_read_with_its_copy_of_an_action(repo, sessions):
    """The action runner's workspace: the stored workspace with the copy's
    parameters and secrets under the action's id (the 4.0 ``$lookup`` shape),
    read through the actions repository; 404 without either."""
    workspaces = PostgresWorkspaceRepository(sessions, repo)
    workspace = WorkspaceDocument(
        id=WORKSPACE, title="delta", workspace_name="delta", owner_id=USER.id
    )
    await workspaces.save(workspace)
    action = await repo.create_global_action(_dto("sheet"), USER)
    await repo.create_action_in_workspace_from_action(WORKSPACE, action.id, "creds")

    found = await workspaces.get_workspace_with_action_by_id(WORKSPACE, action.id)
    assert found["id"] == WORKSPACE
    assert found["_id"] == WORKSPACE
    assert found["secrets"] == {
        str(action.id): [{"name": "Credentials", "value": "creds", "required": False}]
    }
    assert found["parameters"] == {str(action.id): None}
    dto = WorkspaceRequestWithActionDto(**found)
    assert dto.id == WORKSPACE
    assert dto.secrets[str(action.id)][0].value == "creds"

    for workspace_id, action_id in ((WORKSPACE, UNKNOWN), (UNKNOWN, action.id)):
        with pytest.raises(HTTPException) as missing:
            await workspaces.get_workspace_with_action_by_id(workspace_id, action_id)
        assert missing.value.status_code == 404
