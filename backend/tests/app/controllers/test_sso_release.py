"""Releasing IdP entity IDs in Polis (docs/sso.md, "Releasing an entity ID"):
a deleted workspace's connections Polis could not delete are kept as
``release_pending`` and retried, and the support command releases orphaned
or squatted entity IDs. Polis is a stand-in (tests/app/sso_helpers)."""

import pytest
from common.ids import RecordId

from backend import sso as sso_cli
from backend.app.container import container
from backend.app.schemas.sso_connection import SsoConnectionStatus
from backend.app.services.sso.polis_client import PolisUnavailable
from backend.config import settings
from backend.jobs import tasks
from tests.app.controllers.data import testUser
from tests.app.sso_helpers import (  # noqa: F401 — fixtures
    add_connection,
    sso_on,
    verify_domain,
)

ENTITY = "https://idp.acme-sso.org/entity"


def _service():
    return container.sso_connection_service()


def _repo():
    return container.sso_connection_repo()


async def test_a_failed_polis_delete_keeps_the_connection_pending(workspace, sso_on):
    polis, _ = sso_on
    polis.fail_tenant = PolisUnavailable()
    connection = await add_connection(workspace.id)

    removed = await _service().release_workspaces([workspace.id])

    assert removed == 0
    kept = await _repo().get(connection.id)
    assert kept.status == SsoConnectionStatus.RELEASE_PENDING
    assert not kept.is_enabled  # never signs anyone in
    assert await _repo().find_enabled(workspace.id) is None
    assert [c.id for c in await _repo().list_release_pending(10)] == [connection.id]


async def test_the_retry_releases_pending_connections(workspace, sso_on):
    polis, _ = sso_on
    polis.fail_tenant = PolisUnavailable()
    await add_connection(workspace.id)
    await add_connection(workspace.id, enabled=False)
    await _service().release_workspaces([workspace.id])

    # Polis still down: nothing goes
    assert await _service().retry_pending_releases() == {
        "workspaces": 1,
        "released": 0,
        "failed": 1,
        "overdue": 0,
    }
    assert len(await _repo().list_release_pending(10)) == 2

    polis.fail_tenant = None
    assert await _service().retry_pending_releases() == {
        "workspaces": 1,
        "released": 1,
        "failed": 0,
        "overdue": 0,
    }
    assert polis.calls.count(("delete_tenant", str(workspace.id))) == 3
    assert await _repo().list_release_pending(10) == []
    assert await _repo().list_by_workspace(workspace.id) == []


async def test_the_daily_job_runs_the_retry(workspace, sso_on):
    polis, _ = sso_on
    polis.fail_tenant = PolisUnavailable()
    await add_connection(workspace.id)
    await _service().release_workspaces([workspace.id])
    polis.fail_tenant = None

    assert await tasks.sso_release_retry.func(0) == "1 released, 0 failed"
    assert await _repo().list_by_workspace(workspace.id) == []


async def test_with_sso_off_connections_wait_for_polis(workspace):
    connection = await add_connection(workspace.id)

    assert await _service().release_workspaces([workspace.id]) == 0
    assert (await _repo().get(connection.id)).status == (
        SsoConnectionStatus.RELEASE_PENDING
    )
    assert (await _service().retry_pending_releases())["skipped"] is True


async def test_a_successful_delete_still_removes_the_records(workspace, sso_on):
    polis, _ = sso_on
    await add_connection(workspace.id)
    assert await _service().release_workspaces([workspace.id]) == 1
    assert await _repo().list_release_pending(10) == []


async def test_a_connection_not_recorded_is_deleted_in_polis(
    workspace, sso_on, monkeypatch
):
    polis, _ = sso_on
    await verify_domain(workspace.id)

    async def broken(document):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(_repo(), "create", broken)
    with pytest.raises(RuntimeError):
        await _service().create_connection(
            workspace.id,
            _create_dto(),
            testUser,
        )
    assert ("delete", "polis-client-1") in polis.calls
    assert polis.connections == {}


def _create_dto():
    from backend.app.services.sso.connection_service import CreateSsoConnectionDto
    from tests.app.sso_helpers import SAML_XML

    return CreateSsoConnectionDto(type="saml", metadata_xml=SAML_XML)


# -- the support command -------------------------------------------------------
def _holder(client_id, tenant, product="bettercollected"):
    return {"clientID": client_id, "tenant": tenant, "product": product}


@pytest.fixture()
async def holders(workspace, workspace_1, sso_on):
    """An entity ID held four times: a deleted workspace's connection, a live
    workspace's recorded one, a live workspace's unrecorded one and another
    product's."""
    polis, _ = sso_on
    gone = str(RecordId())
    recorded = await add_connection(workspace.id, client_id="c-in-use")
    polis.entity_holders = [
        _holder("c-orphaned", gone),
        _holder("c-in-use", str(workspace.id)),
        _holder("c-unrecorded", str(workspace_1.id)),
        _holder("c-other", str(workspace.id), product="another-product"),
    ]
    return polis, gone, recorded


async def test_holders_are_classified(holders, workspace, workspace_1):
    _, gone, recorded = holders
    found = {h["client_id"]: h for h in await _service().entity_id_holders(ENTITY)}

    assert found["c-orphaned"]["state"] == "orphaned"
    assert found["c-orphaned"]["tenant"] == gone
    assert found["c-in-use"]["state"] == "in_use"
    assert found["c-in-use"]["status"] == "enabled"
    assert found["c-in-use"]["connection_id"] == str(recorded.id)
    assert found["c-unrecorded"]["state"] == "unrecorded"
    assert found["c-other"]["state"] == "other_product"


async def test_a_dry_run_changes_nothing(holders):
    polis, _, recorded = holders
    result = await _service().release_entity_id(ENTITY)

    assert result["applied"] is False
    assert sorted(result["released"]) == ["c-orphaned", "c-unrecorded"]
    assert not [c for c in polis.calls if c[0] == "delete"]
    assert await _repo().get(recorded.id) is not None


async def test_apply_releases_only_orphaned_holders(holders):
    polis, _, recorded = holders
    result = await _service().release_entity_id(ENTITY, apply=True)

    deleted = sorted(c[1] for c in polis.calls if c[0] == "delete")
    assert deleted == ["c-orphaned", "c-unrecorded"] == sorted(result["released"])
    # the live workspace's connection and another product's stay
    assert await _repo().get(recorded.id) is not None


async def test_naming_the_workspace_releases_its_connection(holders, workspace):
    polis, _, recorded = holders
    result = await _service().release_entity_id(
        ENTITY, workspace_id=str(workspace.id), apply=True
    )

    assert "c-in-use" in result["released"]
    assert ("delete", "c-in-use") in polis.calls
    assert await _repo().get(recorded.id) is None
    assert ("delete", "c-other") not in polis.calls


async def test_never_while_the_workspace_requires_sso(holders, workspace):
    polis, _, recorded = holders
    await container.workspace_repo().set_fields(workspace, {"sso_required": True})

    result = await _service().release_entity_id(
        ENTITY, workspace_id=str(workspace.id), apply=True
    )

    assert result["refused_sso_required"] == ["c-in-use"]
    assert ("delete", "c-in-use") not in polis.calls
    assert await _repo().get(recorded.id) is not None


async def test_the_command_needs_sso_configured(capsys):
    assert not settings.sso.is_configured
    assert await sso_cli.main(["release-pending"]) == 2
    assert "not configured" in capsys.readouterr().out


# -- review follow-ups -------------------------------------------------------
async def test_a_failed_insert_never_deletes_a_live_polis_connection(
    workspace, sso_on, monkeypatch
):
    """Polis updates the tenant's existing connection for the same IdP in
    place and answers with its clientID: the failed insert then concerns a
    connection we record (and may be the enabled one)."""
    polis, _ = sso_on
    await verify_domain(workspace.id)
    live = await add_connection(workspace.id, client_id="polis-client-1")
    polis.connections["polis-client-1"] = {"clientID": "polis-client-1"}
    polis._n = 0  # Polis answers with the existing clientID

    async def broken(document):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(_repo(), "create", broken)
    with pytest.raises(RuntimeError):
        await _service().create_connection(workspace.id, _create_dto(), testUser)
    assert ("delete", "polis-client-1") not in polis.calls
    assert "polis-client-1" in polis.connections
    assert (await _repo().get(live.id)).is_enabled


async def test_when_the_record_cant_be_checked_polis_is_left_alone(
    workspace, sso_on, monkeypatch
):
    polis, _ = sso_on
    await verify_domain(workspace.id)

    async def broken(*args):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(_repo(), "create", broken)
    monkeypatch.setattr(_repo(), "find_by_polis_client_id", broken)
    with pytest.raises(RuntimeError):
        await _service().create_connection(workspace.id, _create_dto(), testUser)
    assert not [c for c in polis.calls if c[0] == "delete"]


async def test_a_failed_retry_goes_to_the_back_of_the_queue(
    workspace, workspace_1, sso_on, monkeypatch
):
    polis, _ = sso_on
    first = await add_connection(workspace.id)
    second = await add_connection(workspace_1.id)
    polis.fail_tenant = PolisUnavailable()
    await _service().release_workspaces([workspace.id])
    await _service().release_workspaces([workspace_1.id])
    # the oldest attempt first
    assert [c.id for c in await _repo().list_release_pending(1)] == [first.id]

    async def only_the_second(tenant):
        polis.calls.append(("delete_tenant", tenant))
        if tenant != str(workspace_1.id):
            raise PolisUnavailable()

    monkeypatch.setattr(polis, "delete_tenant", only_the_second)
    result = await _service().retry_pending_releases(limit=1)
    assert result["failed"] == 1 and result["released"] == 0
    # the failure moved it back: the next run reaches the other one
    result = await _service().retry_pending_releases(limit=1)
    assert result["released"] == 1
    assert await _repo().get(second.id) is None
    assert (await _repo().get(first.id)).status == SsoConnectionStatus.RELEASE_PENDING


async def test_connections_waiting_too_long_are_reported(workspace, sso_on):
    import datetime as dt

    polis, _ = sso_on
    connection = await add_connection(workspace.id)
    polis.fail_tenant = PolisUnavailable()
    await _service().release_workspaces([workspace.id])
    assert (await _service().retry_pending_releases())["overdue"] == 0

    stored = await _repo().get(connection.id)
    stored.disabled_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=8)
    await _repo().save(stored)
    assert (await _service().retry_pending_releases())["overdue"] == 1


async def test_releasing_never_deletes_another_workspaces_record(
    workspace, workspace_1, sso_on
):
    """A Polis connection held under workspace_1's tenant whose clientID our
    record files under another workspace: Polis's is released, our record
    of the other workspace stays."""
    polis, _ = sso_on
    other = await add_connection(workspace.id, client_id="c-shared")
    polis.entity_holders = [_holder("c-shared", str(workspace_1.id))]

    holders = await _service().entity_id_holders(ENTITY)
    assert holders[0]["state"] == "unrecorded"
    result = await _service().release_entity_id(ENTITY, apply=True)

    assert result["released"] == ["c-shared"]
    assert ("delete", "c-shared") in polis.calls
    assert await _repo().get(other.id) is not None


async def test_a_pending_connection_never_signs_anyone_in(client, workspace, sso_on):
    from tests.app.controllers.test_sso_login import CALLBACK, sso_error, start
    from tests.app.sso_helpers import state_of

    polis, auth = sso_on
    await verify_domain(workspace.id)
    await add_connection(workspace.id)
    started = await start(client)
    assert started.status_code == 307, started.text
    polis.fail_tenant = PolisUnavailable()
    await _service().release_workspaces([workspace.id])

    reply = await client.get(
        CALLBACK, params={"code": "c", "state": state_of(started.headers["location"])}
    )
    assert sso_error(reply) == "sso_not_configured"
    assert auth.created_accounts() == []
