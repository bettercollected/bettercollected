"""Two edits of one key at once.

An edit is worked out before the key's row is locked, so another edit can commit
in between. The edit that comes second must notice (the key, or its list of
forms, is no longer what it planned from) and plan again; and the key, its rows
and its audit entries are stored in one transaction under the lock, so they
commit or fail together. Everything here is synthetic."""

import asyncio

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.repositories.postgres.form_access import AccessTargetNotFound
from backend.app.schemas.workspace_audit_event import (
    API_KEY_FORM_ADDED,
    API_KEY_FORM_REMOVED,
    API_KEY_ROLE_CHANGED,
    API_KEY_SCOPE_CHANGED,
)
from tests.app.form_access.helpers import audit_events
from tests.app.form_access.test_key_roles import roles_on  # noqa: F401
from tests.app.form_access.test_key_routes import (
    code,
    create,
    forms,  # noqa: F401
    ids,
    patch,
    rows_of,
    stored,
)

pytestmark = pytest.mark.asyncio


async def form_ids_of(events):
    return [e.form_id for e in events]


async def test_an_edit_of_the_role_does_not_put_back_a_form_another_edit_removed(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch  # noqa: F811
):
    """B changes only the role and plans with the list as it was read; A removes a
    form and commits before B takes the lock. B must see that the stored list is
    no longer the one it planned from and plan again: the form stays removed, the
    role changes, and the log says exactly that."""
    first, second = ids(forms)[:2]
    made = (
        await create(client, workspace, formScope="listed", formIds=[first, second])
    ).json()
    service = container.api_key_service()
    real = service._plan_edit
    calls = []

    async def watched(*args, **kwargs):
        plan = await real(*args, **kwargs)
        calls.append(1)
        if len(calls) == 1:
            removed = await patch(
                client, workspace, made["id"], formScope="listed", formIds=[first]
            )
            assert removed.status_code == 200, removed.text
        return plan

    monkeypatch.setattr(service, "_plan_edit", watched)
    edited = await patch(client, workspace, made["id"], role="REVIEWER")
    assert edited.status_code == 200, edited.text
    assert len(calls) == 3  # B, then A (inside B), then B again
    assert await rows_of(workspace, made["id"]) == [first]
    assert [f["id"] for f in edited.json()["forms"]] == [first]
    assert (await stored(made["id"])).role == "REVIEWER"
    assert await form_ids_of(await audit_events(workspace, API_KEY_FORM_REMOVED)) == [second]
    # (the two forms added by the creation, and none since)
    assert sorted(await form_ids_of(await audit_events(workspace, API_KEY_FORM_ADDED))) == sorted(
        [first, second]
    )
    (changed,) = await audit_events(workspace, API_KEY_ROLE_CHANGED)
    assert (changed.key_role_before, changed.key_role) == ("creator", "REVIEWER")


async def test_two_edits_started_together_both_apply_whatever_the_order(
    client: AsyncClient, workspace, forms, roles_on  # noqa: F811
):
    """One edit changes the list, the other only the role: the final rows are the
    list's, the role is the other's, and the log has no entry for a form being
    added."""
    first, second = ids(forms)[:2]
    made = (
        await create(client, workspace, formScope="listed", formIds=[first, second])
    ).json()
    removed, reroled = await asyncio.gather(
        patch(client, workspace, made["id"], formScope="listed", formIds=[first]),
        patch(client, workspace, made["id"], role="REVIEWER"),
    )
    assert (removed.status_code, reroled.status_code) == (200, 200)
    assert await rows_of(workspace, made["id"]) == [first]
    assert (await stored(made["id"])).role == "REVIEWER"
    assert await form_ids_of(await audit_events(workspace, API_KEY_FORM_REMOVED)) == [second]
    # (the two forms added by the creation, and none since)
    assert sorted(await form_ids_of(await audit_events(workspace, API_KEY_FORM_ADDED))) == sorted(
        [first, second]
    )


async def test_the_key_its_rows_and_its_entries_commit_or_fail_together(
    client: AsyncClient, workspace, forms, roles_on, monkeypatch  # noqa: F811
):
    """The rows are written in the transaction that stores the key and its audit
    entries: when they cannot be written (a form deleted meanwhile), the key keeps
    its role and list and no entry is left for a change that was not made."""
    made = (
        await create(
            client, workspace, role="VIEWER", formScope="listed", formIds=ids(forms)[:1]
        )
    ).json()
    entries_before = len(await audit_events(workspace))

    async def vanished(session, *args, **kwargs):
        raise AccessTargetNotFound("form")

    monkeypatch.setattr(container.form_access_grant_repo(), "replace_for_key_in", vanished)
    refused = await patch(
        client, workspace, made["id"], role="EDITOR", formIds=ids(forms)[:2]
    )
    assert refused.status_code == 400 and code(refused) == "form_not_in_workspace"
    assert (await stored(made["id"])).role == "VIEWER"
    assert await rows_of(workspace, made["id"]) == ids(forms)[:1]
    assert len(await audit_events(workspace)) == entries_before
    assert await audit_events(workspace, API_KEY_ROLE_CHANGED, API_KEY_SCOPE_CHANGED) == []
