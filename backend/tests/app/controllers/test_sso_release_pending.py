"""A stack rolled back from release 4.1 reads SSO connections 4.1 left in
``release_pending`` (a deleted workspace's connection Polis had not released
yet). Here such a connection behaves like a disabled one that nothing can act
on: it never signs anyone in, never counts as the workspace's enabled
connection, and the admin API treats it as not found."""

import pytest

from backend.app.container import container
from backend.app.schemas.sso_connection import (
    SsoConnectionDocument,
    SsoConnectionStatus,
)
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser
from tests.app.controllers.test_sso_login import (
    CALLBACK,
    sso_error,
    start,
)
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    add_connection,
    sso_on,
    state_of,
    verify_domain,
)

W = "/api/v1/workspaces/{ws}/sso"


def _cookies() -> dict:
    token = access_token(testUser)
    return {"Authorization": token, "RefreshToken": token}


async def release_pending(workspace_id, **kwargs) -> SsoConnectionDocument:
    connection = await add_connection(workspace_id, **kwargs)
    connection.status = SsoConnectionStatus.RELEASE_PENDING
    await container.sso_connection_repo().save(connection)
    return connection


def test_the_status_enum_reads_what_release_41_writes():
    status = SsoConnectionStatus("release_pending")
    assert status is SsoConnectionStatus.RELEASE_PENDING
    assert status.value == "release_pending"
    # 4.1's order: ENABLED stays the last member (the codec golden fixtures
    # sample an enum's last member)
    assert list(SsoConnectionStatus)[-1] is SsoConnectionStatus.ENABLED


async def test_a_release_pending_row_is_read_and_is_never_enabled(workspace):
    stored = await release_pending(workspace.id, enabled=False)
    repo = container.sso_connection_repo()

    found = await repo.get(stored.id)

    assert found.status is SsoConnectionStatus.RELEASE_PENDING
    assert found.is_release_pending and not found.is_enabled
    assert [c.id for c in await repo.list_by_workspace(workspace.id)] == [stored.id]
    assert await repo.find_enabled(workspace.id) is None
    # the by-client-id lookup (a sign-in code, a recorded test) finds it too
    assert (await repo.find_by_polis_client_id(stored.polis_client_id)).id == stored.id


async def test_a_release_pending_connection_is_not_the_enabled_one(workspace):
    repo = container.sso_connection_repo()
    pending = await release_pending(workspace.id, enabled=False)
    live = await add_connection(workspace.id, enabled=True)

    assert (await repo.find_enabled(workspace.id)).id == live.id
    # disabling the others never touches it either
    assert await repo.disable_others(workspace.id, live.id, "u", live.enabled_at) == 0
    assert (await repo.get(pending.id)).status is SsoConnectionStatus.RELEASE_PENDING


async def test_it_signs_nobody_in_like_a_disabled_connection(client, workspace, sso_on):
    await verify_domain(workspace.id)
    await release_pending(workspace.id)
    assert sso_error(await start(client)) == "sso_not_configured"


async def test_a_connection_that_became_release_pending_mid_sign_in_is_refused(
    client, workspace, sso_on
):
    await verify_domain(workspace.id)
    connection = await add_connection(workspace.id)
    started = await start(client)
    assert started.status_code == 307
    connection.status = SsoConnectionStatus.RELEASE_PENDING
    await container.sso_connection_repo().save(connection)

    reply = await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )

    assert sso_error(reply) == "sso_not_configured"


async def test_it_cannot_satisfy_sso_required(client, workspace, sso_on):
    await verify_domain(workspace.id)
    await release_pending(workspace.id)

    reply = await client.put(
        W.format(ws=workspace.id) + "/settings",
        json={"ssoRequired": True},
        cookies=_cookies(),
    )

    assert reply.status_code == 409
    assert reply.json()["code"] == "sso_connection_required"


@pytest.mark.parametrize(
    "method,suffix",
    [
        ("POST", "/enable"),
        ("POST", "/disable"),
        ("DELETE", ""),
        ("GET", "/test"),
    ],
)
async def test_the_admin_api_cannot_act_on_it(
    client, workspace, sso_on, method, suffix
):
    pending = await release_pending(workspace.id, tested=True)

    reply = await client.request(
        method,
        W.format(ws=workspace.id) + f"/connections/{pending.id}{suffix}",
        cookies=_cookies(),
    )

    assert reply.status_code == 404, reply.text
    # untouched: still release_pending (not enabled although it was tested)
    stored = await container.sso_connection_repo().get(pending.id)
    assert stored.status is SsoConnectionStatus.RELEASE_PENDING
