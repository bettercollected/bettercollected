"""An API key acts as the person who created it, so it must not outlive their
place in the workspace: removing a member and deleting an account revoke the
keys they made (the rows stay), whatever the form-access switch says. A person
invited again starts with no keys, as they start with no grants."""

from unittest.mock import patch

import pytest
from common.ids import RecordId
from common.models.user import User
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.repositories.postgres import member_removal
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.schemas.workspace_audit_event import (
    API_KEY_REVOKED,
    REVOKED_ACCOUNT_DELETED,
    REVOKED_MEMBER_REMOVED,
)
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services import workspace_service
from backend.app.services.ai.api_keys import APIKeyService, _hash
from tests.app.controllers.data import testUser
from tests.app.form_access.helpers import (
    add_member,
    api,
    audit_events,
    cookies,
    fail_audit,
)

pytestmark = pytest.mark.asyncio

KEY_NAME = "ci-pipeline-key"


@pytest.fixture()
def auth_lookup():
    """The auth service's user lookup, which removing a member calls."""

    async def get(*args, **kwargs):
        ids = [str(i) for i in (kwargs.get("params") or {}).get("user_ids", [])]
        return {"users_info": [{"_id": i, "email": f"{i}@example.com"} for i in ids]}

    with patch("common.services.http_client.HttpClient.get", side_effect=get):
        yield


@pytest.fixture()
def no_storage(monkeypatch):
    monkeypatch.setattr(
        container.aws_service(), "delete_folder_from_s3", lambda *a, **k: None
    )


def new_token() -> str:
    return "bc_" + str(RecordId()) + str(RecordId())


async def make_key(workspace, creator, token=None) -> WorkspaceAPIKeyDocument:
    token = token or new_token()
    return await container.workspace_api_key_repo().save(
        WorkspaceAPIKeyDocument(
            workspace_id=workspace.id,
            name=KEY_NAME,
            key_hash=_hash(token),
            prefix=token[:11],
            scopes=["forms:read"],
            created_by=str(creator.id),
        )
    )


async def stored(key) -> WorkspaceAPIKeyDocument:
    return await container.workspace_api_key_repo().get_or_404(key.id)


async def remove(client, workspace, member, by=testUser):
    return await client.delete(
        f"{api(workspace)}/members/{member.id}", cookies=cookies(by)
    )


async def invite_again(workspace, person, role="ADMIN"):
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id, user_id=person.id, roles=[role]
        )
    )


# -- a member removal ---------------------------------------------------------------------
async def test_removing_a_member_revokes_their_keys_and_inviting_them_again_does_not_revive_them(
    client: AsyncClient, workspace, workspace_1, auth_lookup
):
    person = await add_member(workspace, "ADMIN")
    bystander = await add_member(workspace, "ADMIN")
    mine = [await make_key(workspace, person), await make_key(workspace, person)]
    theirs = await make_key(workspace, bystander)
    owners = await make_key(workspace, testUser)
    # the same person's key in another workspace is that workspace's business
    await invite_again(workspace_1, person)
    elsewhere = await make_key(workspace_1, person)

    assert (await remove(client, workspace, person)).status_code == 200

    for key in mine:
        row = await stored(key)
        assert row.revoked is True
        # the row stays: the audit and "last used" remain
        assert row.name == KEY_NAME and row.key_hash == key.key_hash
    for key in (theirs, owners, elsewhere):
        assert (await stored(key)).revoked is False

    # invited again, with the same user id and a role as high as before
    await invite_again(workspace, person)
    repo = container.workspace_api_key_repo()
    assert await repo.live_created_by(person.id, workspace.id) == []
    assert await repo.live_created_by(person.id) == [
        (str(elsewhere.id), str(workspace_1.id))
    ]
    assert (await stored(theirs)).revoked is False


async def test_a_revoked_key_no_longer_authenticates_after_the_removal(
    client: AsyncClient, workspace, auth_lookup
):
    person = await add_member(workspace, "ADMIN")
    token = new_token()
    key = await make_key(workspace, person, token)
    await APIKeyService.authenticate(token)

    assert (await remove(client, workspace, person)).status_code == 200
    await invite_again(workspace, person)

    with pytest.raises(HTTPException) as refused:
        await APIKeyService.authenticate(token)
    assert refused.value.status_code == 401
    assert (await stored(key)).revoked is True


async def test_each_revoked_key_is_recorded_with_ids_only(
    client: AsyncClient, workspace, auth_lookup
):
    person = await add_member(workspace, "ADMIN")
    bystander = await add_member(workspace, "ADMIN")
    mine = [await make_key(workspace, person), await make_key(workspace, person)]
    await make_key(workspace, bystander)

    assert (await remove(client, workspace, person)).status_code == 200

    events = await audit_events(workspace, API_KEY_REVOKED)
    assert sorted(e.key_id for e in events) == sorted(str(k.id) for k in mine)
    assert {(e.reason, e.target_user_id, e.user_id) for e in events} == {
        (REVOKED_MEMBER_REMOVED, person.id, testUser.id)
    }
    text = str([e.model_dump(mode="json") for e in events])
    assert KEY_NAME not in text and "bc_" not in text and "@" not in text


async def test_a_removal_with_no_keys_writes_no_key_entry(
    client: AsyncClient, workspace, auth_lookup
):
    person = await add_member(workspace, "VIEWER")
    assert (await remove(client, workspace, person)).status_code == 200
    # only the removal itself is recorded (``member_removed``); no key was held
    assert await audit_events(workspace, API_KEY_REVOKED) == []
    assert len(await audit_events(workspace, "member_removed")) == 1


async def test_a_removal_that_cannot_record_the_revocation_changes_nothing(
    client: AsyncClient, workspace, auth_lookup, monkeypatch
):
    person = await add_member(workspace, "ADMIN")
    key = await make_key(workspace, person)
    fail_audit(monkeypatch)

    response = await remove(client, workspace, person)

    assert response.status_code == 503
    assert response.json()["code"] == "audit_unavailable"
    assert (await stored(key)).revoked is False
    assert (
        await container.workspace_user_repo().find_workspace_user(
            workspace.id, person.id
        )
        is not None
    )


async def test_the_removal_stays_atomic_when_the_revocation_fails(
    client: AsyncClient, workspace, monkeypatch
):
    person = await add_member(workspace, "ADMIN")
    key = await make_key(workspace, person)

    async def failing(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(member_removal, "revoke_live_keys", failing)
    with pytest.raises(RuntimeError):
        await container.member_removal_repo().remove(
            workspace.id, person.id, str(workspace.owner_id)
        )

    # no half removal: the member is still there, the key still as it was
    assert (
        await container.workspace_user_repo().find_workspace_user(
            workspace.id, person.id
        )
        is not None
    )
    assert (await stored(key)).revoked is False


async def test_a_failure_after_the_revocation_rolls_it_back(
    client: AsyncClient, workspace, monkeypatch
):
    """The revocation is part of the removal's transaction: a step that fails
    after it brings the key back to live, with the membership."""
    person = await add_member(workspace, "ADMIN")
    key = await make_key(workspace, person)
    real = member_removal.revoke_live_keys

    async def then_fail(*args, **kwargs):
        await real(*args, **kwargs)
        raise RuntimeError("boom")

    monkeypatch.setattr(member_removal, "revoke_live_keys", then_fail)
    with pytest.raises(RuntimeError):
        await container.member_removal_repo().remove(
            workspace.id, person.id, str(workspace.owner_id)
        )

    assert (await stored(key)).revoked is False
    assert (
        await container.workspace_user_repo().find_workspace_user(
            workspace.id, person.id
        )
        is not None
    )


async def test_a_key_made_during_the_removal_is_revoked_and_recorded_too(
    client: AsyncClient, workspace, auth_lookup, monkeypatch
):
    person = await add_member(workspace, "ADMIN")
    first = await make_key(workspace, person)
    late = {}
    lifecycle = container.api_key_lifecycle()
    real = lifecycle.record_member_keys

    async def then_a_key_appears(*args, **kwargs):
        recorded = await real(*args, **kwargs)
        late["key"] = await make_key(workspace, person)
        return recorded

    monkeypatch.setattr(lifecycle, "record_member_keys", then_a_key_appears)
    assert (await remove(client, workspace, person)).status_code == 200

    assert (await stored(first)).revoked and (await stored(late["key"])).revoked
    events = await audit_events(workspace, API_KEY_REVOKED)
    assert sorted(e.key_id for e in events) == sorted(
        [str(first.id), str(late["key"].id)]
    )


# -- an account deletion ------------------------------------------------------------------
async def test_deleting_an_account_revokes_their_keys_in_every_workspace(
    workspace, workspace_1, no_storage
):
    leaving = User(id=str(RecordId()), sub=f"{RecordId()}@example.org")
    await workspace_service.create_workspace(leaving)
    own = await container.workspace_repo().get_default_workspace_by_owner_id(leaving.id)
    for shared in (workspace, workspace_1):
        await invite_again(shared, leaving, "COLLABORATOR")
    keys = {
        "own": await make_key(own, leaving),
        "here": await make_key(workspace, leaving),
        "there": await make_key(workspace_1, leaving),
    }
    bystander = await add_member(workspace, "ADMIN")
    others = await make_key(workspace, bystander)
    owners = await make_key(workspace, testUser)

    await container.workspace_service().delete_workspaces_of_user_with_forms(leaving)

    for key in keys.values():
        assert (await stored(key)).revoked is True
    for key in (others, owners):
        assert (await stored(key)).revoked is False
    # one entry in each workspace that stays; none in the one that went with
    # the account
    for shared, key in ((workspace, keys["here"]), (workspace_1, keys["there"])):
        (event,) = await audit_events(shared, API_KEY_REVOKED)
        assert (event.key_id, event.reason, event.target_user_id) == (
            str(key.id),
            REVOKED_ACCOUNT_DELETED,
            leaving.id,
        )
    assert not await audit_events(own)


async def test_an_account_deletion_is_not_held_up_by_the_audit_log(
    workspace, no_storage, monkeypatch
):
    leaving = User(id=str(RecordId()), sub=f"{RecordId()}@example.org")
    await workspace_service.create_workspace(leaving)
    await invite_again(workspace, leaving, "COLLABORATOR")
    key = await make_key(workspace, leaving)
    fail_audit(monkeypatch)

    await container.workspace_service().delete_workspaces_of_user_with_forms(leaving)

    assert (await stored(key)).revoked is True
