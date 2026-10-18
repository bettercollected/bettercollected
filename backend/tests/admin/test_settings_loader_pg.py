"""The settings loader against the real store schema (views, reader role,
``report_state``) on Postgres."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from common.settings.loader import LoaderConfig, SettingsRuntime, SourceUnavailable
from common.settings.loader.source import PgSnapshotSource
from common.settings.registry import default_registry
from tests.admin.conftest import MASTER_KEY, needs_postgres
from tests.admin.test_settings_store import (  # noqa: F401 - fixtures and helpers
    PLANT,
    T1,
    as_superuser_raw,
    put,
    scalar,
    superuser,
    svc,
)

pytestmark = needs_postgres

SECRET = "SSO_POLIS_API_KEY"  # a secret the backend and auth services both read


def runtime_for(server, migrated, tmp_path, mode="required", service="backend", logical="app"):
    url = server.url(migrated, f"reader:{logical}")
    cfg = LoaderConfig(
        service=service,
        mode=mode,
        database_url=url,
        master_key=MASTER_KEY,
        snapshot_dir=str(tmp_path / "snap"),
    )
    return SettingsRuntime(cfg, registry=default_registry(), env={}, sleep=lambda s: None)


@pytest.mark.asyncio(loop_scope="session")
async def test_fresh_store_is_empty_and_trusted(server, migrated, tmp_path):
    rt = runtime_for(server, migrated, tmp_path)
    rt.start()
    assert rt.revision == 0 and rt.origin == "store"
    assert rt.resolve_key(T1) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_loads_verifies_polls_and_reports(server, migrated, tmp_path, svc, superuser):  # noqa: F811
    await put(svc, T1, 7)
    await put(svc, SECRET, PLANT)
    rt = runtime_for(server, migrated, tmp_path)
    rt.start()
    assert rt.revision == 2
    assert rt.live_value(T1) == (True, 7)
    assert rt.resolve_key(SECRET).value == PLANT
    assert rt.state().rejected_keys == ()
    assert (tmp_path / "snap" / "settings-backend.json").exists()
    assert PLANT not in (tmp_path / "snap" / "settings-backend.json").read_text()

    rt.report()
    async with superuser.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT revision_applied, env_overrides, rejected_keys, restart_pending, "
                    "keyset_fp FROM settings.service_state WHERE service = 'backend'"
                )
            )
        ).one()
    assert row.revision_applied == 2 and row.rejected_keys == [] and row.keyset_fp

    assert rt.poll_once() is False
    await put(svc, T1, 9)
    assert rt.poll_once() is True
    assert rt.live_value(T1) == (True, 9) and rt.revision == 3
    assert await scalar(superuser, "SELECT revision_applied FROM settings.service_state") == 3


@pytest.mark.asyncio(loop_scope="session")
async def test_a_service_sees_only_its_own_rows(server, migrated, tmp_path, svc):  # noqa: F811
    await put(svc, T1, 7)  # backend only
    rt = runtime_for(server, migrated, tmp_path, service="auth", logical="auth")
    rt.start()
    assert rt.revision == 1 and rt.resolve_key(T1) is None
    assert rt.state().rejected_keys == ()  # not a missing row: auth may not read it


@pytest.mark.asyncio(loop_scope="session")
async def test_a_tampered_row_is_refused_and_the_snapshot_is_not_used(
    server, migrated, tmp_path, svc, superuser  # noqa: F811
):
    await put(svc, T1, 7)
    rt = runtime_for(server, migrated, tmp_path)
    rt.start()  # writes a good snapshot
    await as_superuser_raw(
        superuser, "UPDATE settings.entries SET value = '99'::jsonb WHERE key = :k", k=T1
    )
    rt2 = runtime_for(server, migrated, tmp_path)
    rt2.start()
    assert rt2.origin == "store" and rt2.live_value(T1) == (False, None)
    assert T1 in rt2.state().rejected_keys
    # the running process keeps the last good value
    rt.source.fetch_revision = lambda: 99  # force a reload
    rt.poll_once()
    assert rt.live_value(T1) == (True, 7) and rt.current.is_stale(T1)


@pytest.mark.asyncio(loop_scope="session")
async def test_database_down_uses_the_snapshot(server, migrated, tmp_path, svc):  # noqa: F811
    await put(svc, T1, 7)
    runtime_for(server, migrated, tmp_path).start()
    cfg = LoaderConfig(
        service="backend",
        mode="required",
        database_url="postgresql://nobody:x@127.0.0.1:1/none",
        master_key=MASTER_KEY,
        snapshot_dir=str(tmp_path / "snap"),
        connect_timeout=0.5,
        total_budget=3,
    )
    rt = SettingsRuntime(cfg, registry=default_registry(), env={}, sleep=lambda s: None)
    rt.start()
    assert rt.origin == "snapshot" and rt.live_value(T1) == (True, 7)


@pytest.mark.asyncio(loop_scope="session")
async def test_source_reports_unavailable_without_details(server, migrated):
    source = PgSnapshotSource("postgresql+asyncpg://u:secretpw@127.0.0.1:1/none", "backend", connect_timeout=0.5)
    with pytest.raises(SourceUnavailable) as err:
        source.fetch()
    assert "secretpw" not in str(err.value)
    with pytest.raises(ValueError):
        PgSnapshotSource("postgresql://x/y", "backend; drop table x")
