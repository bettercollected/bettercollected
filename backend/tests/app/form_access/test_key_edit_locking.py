"""An edit of a key's limits and the requests made with that key share one row.

Every request made with a key updates its last-used time, which locks the key's
row. An edit of the key's role or list of forms used to hold that lock across
several round trips (reading the list, checking every form, recording the
entries), so under load the key's requests waited up to the database's
``lock_timeout`` and then failed. The edit is now worked out before the lock; the
lock covers a check that the key is still as read, one batch of entries and the
write; and the last-used update skips a row somebody holds instead of waiting for
it. Everything here is synthetic."""

import asyncio
import datetime as dt
import time

import pytest
from common.ids import RecordId
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.container import container
from backend.app.repositories.postgres.identity import WorkspaceApiKeyRow
from backend.app.schemas.workspace_audit_event import (
    API_KEY_ROLE_CHANGED,
    API_KEY_SCOPE_CHANGED,
)
from backend.app.services.ai import api_keys as service_module
from backend.app.services.ai.api_keys import APIKeyService
from tests.app.form_access.helpers import audit_events
from tests.app.form_access.test_key_roles import (
    BASE,
    TOKENS,
    admin_creator,
    make_key,
    roles_on,  # noqa: F401
)
from tests.app.form_access.test_key_routes import (
    READ,
    code,
    create,
    forms,  # noqa: F401
    patch,
    stored,
)

pytestmark = pytest.mark.asyncio

# how long a request made with the key may take while an edit holds its row: far
# below the database's lock_timeout (5 s), so a wait for the lock fails the test
FAST = 2.0


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def row_is_held(key_id) -> bool:
    """Whether somebody holds the key's row right now (seen from another
    connection, without waiting)."""
    async with container.workspace_api_key_repo()._session() as session:
        free = (
            await session.execute(
                select(WorkspaceApiKeyRow.id)
                .where(WorkspaceApiKeyRow.id == str(key_id))
                .with_for_update(skip_locked=True)
            )
        ).first()
    return free is None


async def test_a_request_with_the_key_is_not_held_up_by_an_edit_of_the_key(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch  # noqa: F811
):
    """While the edit holds the key's row (it is recording its entries), a
    request authenticating with the key goes through at once, with the key as it
    was read."""
    made = (await create(client, workspace, role="VIEWER")).json()
    real = service_module.record_many_or_refuse
    seen = []

    async def watched(*args, **kwargs):
        assert await row_is_held(made["id"]), "the edit must hold the key's row here"
        started = time.monotonic()
        got = await asyncio.wait_for(
            client.get(f"{BASE}/forms", headers=bearer(made["token"])), FAST
        )
        seen.append((got.status_code, time.monotonic() - started))
        return await real(*args, **kwargs)

    monkeypatch.setattr(service_module, "record_many_or_refuse", watched)
    edited = await patch(client, workspace, made["id"], role="REVIEWER")
    assert edited.status_code == 200, edited.text
    assert len(seen) == 1 and seen[0][0] == 200, seen
    assert seen[0][1] < FAST
    assert (await stored(made["id"])).role == "REVIEWER"


async def test_authenticating_never_waits_for_a_row_somebody_holds(workspace):
    """``touch_last_used`` skips a held row (the key is live, the request goes
    on, nothing is written) and writes once it is free; a revoked or missing key
    is still told apart from a held one."""
    admin = await admin_creator(workspace)
    key = await make_key(workspace, admin, scopes=READ)
    repo = container.workspace_api_key_repo()
    before = (await stored(key.id)).last_used_at
    async with repo._session() as holder, holder.begin():
        (
            await holder.execute(
                select(WorkspaceApiKeyRow.id)
                .where(WorkspaceApiKeyRow.id == str(key.id))
                .with_for_update()
            )
        ).all()
        now = dt.datetime.now(dt.timezone.utc)
        started = time.monotonic()
        assert await asyncio.wait_for(repo.touch_last_used(key.id, now), FAST) is True
        assert time.monotonic() - started < FAST
        assert (await stored(key.id)).last_used_at == before  # skipped, not written
        # and the whole authentication, which is what a request runs
        got = await asyncio.wait_for(
            APIKeyService.authenticate(TOKENS[str(key.id)]), FAST
        )
        assert str(got.id) == str(key.id)
    after = dt.datetime.now(dt.timezone.utc)
    assert await repo.touch_last_used(key.id, after) is True
    assert (await stored(key.id)).last_used_at == after
    # gone and revoked keys are not "held"
    assert await repo.revoke_one(workspace.id, key.id) is True
    assert await repo.touch_last_used(key.id, after) is False
    assert await repo.touch_last_used(RecordId(), after) is False


async def test_working_out_an_edit_holds_no_lock(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch  # noqa: F811
):
    """The key's list is read and every form checked before the row is locked: a
    revocation made then is not held up, wins, and the edit records nothing."""
    made = (await create(client, workspace, role="VIEWER")).json()
    service = container.api_key_service()
    real = service._plan_edit
    revoked = []

    async def watched(*args, **kwargs):
        plan = await real(*args, **kwargs)
        assert not await row_is_held(made["id"])
        revoked.append(
            await asyncio.wait_for(
                container.workspace_api_key_repo().revoke_one(
                    workspace.id, RecordId(made["id"])
                ),
                FAST,
            )
        )
        return plan

    monkeypatch.setattr(service, "_plan_edit", watched)
    refused = await patch(client, workspace, made["id"], role="EDITOR")
    assert revoked == [True]
    assert refused.status_code == 409 and code(refused) == "key_revoked"
    assert await audit_events(workspace, API_KEY_ROLE_CHANGED, API_KEY_SCOPE_CHANGED) == []
    assert (await stored(made["id"])).role == "VIEWER"


async def test_a_key_changed_while_the_edit_was_worked_out_is_worked_out_again(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch  # noqa: F811
):
    """Another edit lands between the read and the lock: the check under the lock
    notices, the edit is planned again from the key as it is now, and its entries
    name that key's role as the one before, never a stale one."""
    made = (await create(client, workspace, role="VIEWER")).json()
    service = container.api_key_service()
    real = service._plan_edit
    calls = []

    async def watched(*args, **kwargs):
        plan = await real(*args, **kwargs)
        calls.append(1)
        if len(calls) == 1:

            async def meanwhile(document):
                return document.name, "REVIEWER", document.form_scope

            await container.workspace_api_key_repo().update_limits(
                workspace.id, RecordId(made["id"]), meanwhile
            )
        return plan

    monkeypatch.setattr(service, "_plan_edit", watched)
    edited = await patch(client, workspace, made["id"], role="EDITOR")
    assert edited.status_code == 200, edited.text
    assert len(calls) == 2
    assert (await stored(made["id"])).role == "EDITOR"
    (entry,) = await audit_events(workspace, API_KEY_ROLE_CHANGED)
    assert (entry.key_role, entry.key_role_before) == ("EDITOR", "REVIEWER")


async def test_an_edit_that_keeps_finding_the_key_changed_gives_up_with_409(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch  # noqa: F811
):
    made = (await create(client, workspace, role="VIEWER")).json()
    service = container.api_key_service()
    real = service._plan_edit
    calls = []

    async def watched(*args, **kwargs):
        plan = await real(*args, **kwargs)
        calls.append(1)

        async def renamed(document):
            return f"renamed {len(calls)}", document.role, document.form_scope

        await container.workspace_api_key_repo().update_limits(
            workspace.id, RecordId(made["id"]), renamed
        )
        return plan

    monkeypatch.setattr(service, "_plan_edit", watched)
    refused = await patch(client, workspace, made["id"], role="EDITOR")
    assert refused.status_code == 409 and code(refused) == "key_changed"
    assert len(calls) == service_module.EDIT_ATTEMPTS
    assert (await stored(made["id"])).role == "VIEWER"
    assert await audit_events(workspace, API_KEY_ROLE_CHANGED) == []


async def test_a_last_used_update_does_not_make_an_edit_start_over(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch  # noqa: F811
):
    """Every request with the key rewrites its last-used time: that is not a
    change an edit reads."""
    made = (await create(client, workspace, role="VIEWER")).json()
    service = container.api_key_service()
    real = service._plan_edit
    calls = []

    async def watched(*args, **kwargs):
        plan = await real(*args, **kwargs)
        calls.append(1)
        used = await client.get(f"{BASE}/forms", headers=bearer(made["token"]))
        assert used.status_code == 200
        return plan

    monkeypatch.setattr(service, "_plan_edit", watched)
    edited = await patch(client, workspace, made["id"], role="EDITOR")
    assert edited.status_code == 200, edited.text
    assert len(calls) == 1
    assert (await stored(made["id"])).last_used_at is not None
