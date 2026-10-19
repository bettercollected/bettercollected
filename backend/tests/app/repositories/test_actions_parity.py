"""The Postgres twin of the actions repository behaves like the Mongo original.

Every public method runs on both stores with the same inputs. Secrets are
encrypted (Fernet, a fresh token each time), so they are compared decrypted.
Skipped unless DATABASE_URL points at a *_test database.
"""

import pytest
from beanie import PydanticObjectId
from sqlalchemy import select

from backend.app.container import container
from backend.app.models.dtos.action_dto import ActionDto
from backend.app.repositories.action_repository import ActionRepository
from backend.app.repositories.postgres.actions import PostgresActionRepository
from backend.app.schemas.action_document import ActionDocument, WorkspaceActionsDocument
from backend.db.models import ActionRow, WorkspaceActionRow
from common.models.standard_form import ParameterValue
from common.models.user import User
from tests.app.repositories.parity_helpers import run_on_both

WORKSPACE = PydanticObjectId("65f0a1b2c3d4e5f600000001")
OTHER_WORKSPACE = PydanticObjectId("65f0a1b2c3d4e5f600000002")
UNKNOWN = PydanticObjectId("65f0a1b2c3d4e5f6000000ff")
USER = User(id="65f0a1b2c3d4e5f600000010", sub="creator@example.org")


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def _dto(name, secrets=None):
    return ActionDto(
        name=name,
        title=f"{name} title",
        action_code="print('hi')",
        parameters=[ParameterValue(name="p", value="v", required=True)],
        secrets=[ParameterValue(name=k, value=v) for k, v in (secrets or {}).items()],
        type="script",
    )


def _decrypted(document):
    """The action as the code reads it: secret values decrypted."""
    if document is None:
        return None
    data = document.model_dump(mode="json")
    if data.get("secrets"):
        crypto = container.crypto()
        data["secrets"] = [
            {**secret, "value": crypto.decrypt(secret["value"])}
            for secret in data["secrets"]
        ]
    return data


async def actions_scenario(repo, ids, record):
    record.append(await repo.get_all_actions())
    first = await repo.create_action(
        WORKSPACE, _dto("first", {"token": "s3cret", "other": "two"}), USER
    )
    ids.label(first.id, "first")
    record.append(_decrypted(first))
    unencrypted_dto = _dto("global")
    unencrypted_dto.secrets = None
    global_action = await repo.create_global_action(unencrypted_dto, USER)
    ids.label(global_action.id, "global")
    record.append(_decrypted(global_action))

    record.append([_decrypted(a) for a in await repo.get_all_actions()])
    record.append(_decrypted(await repo.get_action_by_id(first.id)))
    record.append(await repo.get_action_by_id(UNKNOWN))
    record.append(
        [
            _decrypted(a)
            for a in await repo.get_actions_by_ids(
                [global_action.id, first.id, UNKNOWN]
            )
        ]
    )
    record.append(await repo.get_actions_by_ids([]))

    # a workspace's copy: created, then updated in place (same id)
    record.append(await repo.get_workspace_action(WORKSPACE, first.id))
    copy = await repo.create_action_in_workspace_from_action(
        WORKSPACE, first.id, "encrypted-credentials"
    )
    ids.label(copy.id, "copy")
    record.append(copy)
    again = await repo.create_action_in_workspace_from_action(WORKSPACE, first.id)
    record.append((again, again.id == copy.id))
    record.append(await repo.get_workspace_action(WORKSPACE, first.id))
    other_copy = await repo.create_action_in_workspace_from_action(
        OTHER_WORKSPACE, first.id, "other-credentials"
    )
    ids.label(other_copy.id, "other_copy")
    record.append(await repo.get_workspace_action(OTHER_WORKSPACE, first.id))
    record.append(await repo.get_workspace_action(OTHER_WORKSPACE, global_action.id))

    # deleting an action deletes every workspace's copy, and only its own
    global_copy = await repo.create_action_in_workspace_from_action(
        WORKSPACE, global_action.id
    )
    ids.label(global_copy.id, "global_copy")
    record.append(await repo.delete_action(first.id))
    record.append(await repo.get_action_by_id(first.id))
    record.append(await repo.get_workspace_action(WORKSPACE, first.id))
    record.append(await repo.get_workspace_action(OTHER_WORKSPACE, first.id))
    record.append(await repo.get_workspace_action(WORKSPACE, global_action.id))
    record.append([_decrypted(a) for a in await repo.get_all_actions()])
    record.append(await repo.delete_action(UNKNOWN))
    record.append([_decrypted(a) for a in await repo.get_all_actions()])


async def test_actions(sessions):
    crypto = container.crypto()
    await run_on_both(
        actions_scenario,
        ActionRepository(crypto=crypto),
        PostgresActionRepository(sessions, crypto),
        stored=[
            (ActionDocument, ActionRow),
            (WorkspaceActionsDocument, WorkspaceActionRow),
        ],
        sessions=sessions,
    )


async def test_secrets_are_stored_encrypted_in_both_stores(sessions):
    crypto = container.crypto()
    mongo = ActionRepository(crypto=crypto)
    postgres = PostgresActionRepository(sessions, crypto)
    for repo in (mongo, postgres):
        created = await repo.create_action(WORKSPACE, _dto("x", {"k": "plain"}), USER)
        stored = await repo.get_action_by_id(created.id)
        assert stored.secrets[0].value != "plain"
        assert crypto.decrypt(stored.secrets[0].value) == "plain"
    # the Postgres row holds the ciphertext too, never the plain value
    async with sessions() as session:
        docs = (await session.execute(select(ActionRow.doc))).scalars().all()
    assert docs and "plain" not in str(docs)


async def test_a_mirrored_create_stores_the_same_document(sessions):
    """create_action is replayed: the mirror stores the primary's document
    (same id, same ciphertext) instead of encrypting again."""
    crypto = container.crypto()
    created = await ActionRepository(crypto=crypto).create_action(
        WORKSPACE, _dto("mirrored", {"k": "plain"}), USER
    )
    postgres = PostgresActionRepository(sessions, crypto)
    await postgres.replay_write([created])
    copy = await ActionRepository(crypto=crypto).create_action_in_workspace_from_action(
        WORKSPACE, created.id, "creds"
    )
    await postgres.replay_write([copy])
    assert (await postgres.get_action_by_id(created.id)).model_dump() == (
        await ActionDocument.get(created.id)
    ).model_dump()
    assert (
        await postgres.get_workspace_action(WORKSPACE, created.id)
    ).model_dump() == (await WorkspaceActionsDocument.get(copy.id)).model_dump()
