"""The settings store: schema, grants, views, write service and CLI, on real Postgres."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import backend.admin as admin_package
from backend.admin.config import DATABASE_URL_KEY, MASTER_KEY_KEY
from backend.admin.migration_support import READER_SERVICES
from backend.admin.services import audit
from backend.admin.services.settings_store import (
    Actor,
    SettingsError,
    SettingsService,
    StepUp,
    store_registry,
)
from common.settings.canonical import SettingRow
from common.settings.keys import SectionKeys
from common.settings.registry import Tier
from common.settings.signing import Manifest
from common.settings.snapshot import verify_snapshot
from tests.admin.conftest import MASTER_KEY, ROLES_SCRIPT, needs_postgres

pytestmark = needs_postgres

BACKEND_ROOT = Path(admin_package.__file__).resolve().parents[2]
ADMIN = Actor("admin", "ops@example.org")
CLI = Actor("cli")
PLANT = "planted-secret-ZXCV-0123456789-abcdef"

T1 = "API_FLOW_EVENTS_PER_WINDOW"
T2 = "AI_DEFAULT_PROVIDER"
T3 = "AI_COMPAT_BASE_URL"
SECRET = "SSO_POLIS_API_KEY"  # secret, T3, read by backend
AUTH_ONLY = "MAIL_PASSWORD"  # secret, T3, read by auth and admin
T4 = "AUTH_JWT_SECRET"


def make_keys(previous: str | None = None, master: str = MASTER_KEY) -> SectionKeys:
    return SectionKeys(
        master,
        sections={s.section for s in store_registry()},
        master_previous=previous,
    )


@pytest_asyncio.fixture(loop_scope="session")
async def svc(server, migrated):
    engine = create_async_engine(server.url(migrated, "runtime"), poolclass=NullPool)
    service = SettingsService(engine, store_registry(), make_keys())
    yield service
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def superuser(server, migrated):
    engine = create_async_engine(server.url(migrated), poolclass=NullPool)
    yield engine
    await engine.dispose()


def step_up(service: SettingsService, action: str, key: str, material=None, actor=ADMIN, version=0):
    return StepUp(
        service.action_hash(action, key, material, version),
        actor.email,
        datetime.now(timezone.utc) + timedelta(seconds=60),
    )


async def ver(service, key):
    """The version the admin's page would show (0 when never written)."""
    async with service._engine.connect() as conn:
        v = (await conn.execute(text("SELECT version FROM settings.entries WHERE key = :k"), {"k": key})).scalar()
    return v or 0


async def put(service, key, value, actor=ADMIN):
    spec = service.registry.get(key)
    v = await ver(service, key)
    kwargs = {"expected_version": v}
    if spec.tier in (Tier.T2, Tier.T3):
        material = service.registry.coerce(key, value) if not spec.is_secret else value
        kwargs["step_up"] = step_up(service, "set", key, material, version=v)
    if spec.tier is Tier.T3:
        kwargs["confirmation"] = key
    return await service.set(key, value, actor, **kwargs)


async def scalar(engine, sql, **params):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql), params)).scalar()


async def as_superuser_raw(engine, sql, **params):
    """Run SQL with the guards (user triggers) off, as an attacker with DB access would."""
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        await conn.execute(text(sql), params)


async def read_view(server, migrated, service="backend"):
    engine = create_async_engine(
        server.url(migrated, f"reader:{READER_SERVICES[service]}"), poolclass=NullPool
    )
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        f"SELECT key, section, readers, is_secret, reload_class, value::text AS value, "
                        f"blob, version, updated_at, sig FROM settings.v_{service}"
                    )
                )
            ).all()
            m = (
                await conn.execute(
                    text(
                        f"SELECT revision, entries::text AS entries, sig FROM settings.v_{service}_manifest"
                    )
                )
            ).one()
    finally:
        await engine.dispose()
    import json

    parsed = [
        SettingRow(
            key=r.key,
            section=r.section,
            readers=tuple(r.readers),
            is_secret=r.is_secret,
            reload_class=r.reload_class,
            version=r.version,
            updated_at=r.updated_at,
            value=None if r.value is None else json.loads(r.value),
            blob=r.blob,
            sig=r.sig,
        )
        for r in rows
    ]
    manifest = Manifest.from_json(
        {"revision": m.revision, "entries": json.loads(m.entries), "sig": m.sig}
    )
    return parsed, manifest


def verified(rows, manifest, service="backend", keys=None):
    return verify_snapshot(
        rows, manifest, keys or make_keys(), registry=store_registry(), service=service
    )


# ----------------------------------------------------------------- schema and grants


async def test_writer_grants_and_no_delete_on_entries(server, migrated, superuser):
    role = server.runtime_role

    async def can(table, privilege):
        return await scalar(
            superuser, "SELECT has_table_privilege(:r, :t, :p)", r=role, t=table, p=privilege
        )

    for table in ("entries", "manifest"):
        assert await can(f"settings.{table}", "SELECT")
        assert await can(f"settings.{table}", "INSERT")
        assert await can(f"settings.{table}", "UPDATE")
        assert not await can(f"settings.{table}", "DELETE")
        assert not await can(f"settings.{table}", "TRUNCATE")
    assert await can("settings.history", "INSERT")
    assert not await can("settings.history", "UPDATE")
    assert await scalar(
        superuser,
        "SELECT has_column_privilege(:r, 'settings.history', 'blob', 'UPDATE')",
        r=role,
    )
    assert await can("settings.service_state", "SELECT")
    assert not await can("settings.service_state", "INSERT")
    assert not await can("settings.service_state", "UPDATE")
    assert await can("admin.notifications", "INSERT")


async def test_the_runtime_role_cannot_delete_entries(svc, server, migrated):
    await put(svc, T1, 5)
    engine = create_async_engine(server.url(migrated, "runtime"), poolclass=NullPool)
    try:
        async with engine.connect() as conn:
            with pytest.raises(DBAPIError, match="permission denied"):
                await conn.execute(text("DELETE FROM settings.entries"))
    finally:
        await engine.dispose()


async def test_guards_bind_the_owner_too(svc, server, migrated):
    await put(svc, T1, 5)
    owner = create_async_engine(server.url(migrated, "owner"), poolclass=NullPool)
    try:
        for sql in (
            "DELETE FROM settings.entries",
            "TRUNCATE settings.entries CASCADE",
            "UPDATE settings.entries SET version = version + 5",
            "UPDATE settings.entries SET value = '1'::jsonb",
            "UPDATE settings.manifest SET revision = 1",
            "DELETE FROM settings.history",
            "UPDATE settings.history SET actor = 'x'",
        ):
            async with owner.connect() as conn:
                with pytest.raises(DBAPIError):
                    await conn.execute(text(sql))
    finally:
        await owner.dispose()


async def test_readers_see_only_their_view_and_rows(svc, server, migrated):
    await put(svc, T1, 7)  # backend only
    await put(svc, SECRET, PLANT)  # backend only
    await put(svc, AUTH_ONLY, PLANT + "-auth")  # auth (and admin, which has no view)
    backend_rows, _ = await read_view(server, migrated, "backend")
    auth_rows, auth_manifest = await read_view(server, migrated, "auth")
    google_rows, _ = await read_view(server, migrated, "google")
    assert {r.key for r in backend_rows} == {T1, SECRET}
    assert {r.key for r in auth_rows} == {AUTH_ONLY}
    assert google_rows == []
    # the manifest is whole: auth sees that backend's keys exist, and that it may not read them
    assert set(auth_manifest.entries) == {T1, SECRET, AUTH_ONLY}
    assert auth_manifest.keys_for("auth") == (AUTH_ONLY,)
    # no base table, no other view
    engine = create_async_engine(server.url(migrated, "reader:auth"), poolclass=NullPool)
    try:
        for sql in (
            "SELECT * FROM settings.entries",
            "SELECT * FROM settings.history",
            "SELECT * FROM settings.manifest",
            "SELECT * FROM settings.v_backend",
            "SELECT * FROM settings.reader_roles",
            "INSERT INTO settings.service_state (service, instance, revision_applied) VALUES ('auth', 'x', 1)",
        ):
            async with engine.connect() as conn:
                with pytest.raises(DBAPIError, match="permission denied"):
                    await conn.execute(text(sql))
    finally:
        await engine.dispose()


async def test_report_state_touches_only_the_callers_row(svc, server, migrated, superuser):
    sql = (
        "SELECT settings.report_state(:i, :r, CAST(:e AS text[]), CAST(:k AS text[]), :p, :f)"
    )
    args = dict(i="inst-1", r=3, e=["MAIL_PASSWORD"], k=[], p=True, f="ab12")
    for logical in ("app", "auth"):
        engine = create_async_engine(server.url(migrated, f"reader:{logical}"), poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql), args)
                await conn.execute(text(sql), {**args, "r": 4})
        finally:
            await engine.dispose()
    async with superuser.connect() as conn:
        found = (
            await conn.execute(
                text("SELECT service, instance, revision_applied, restart_pending FROM settings.service_state ORDER BY service")
            )
        ).all()
    assert [(r.service, r.instance, r.revision_applied, r.restart_pending) for r in found] == [
        ("auth", "inst-1", 4, True),
        ("backend", "inst-1", 4, True),
    ]
    # invalid input is refused; a non-reader role cannot call it at all
    bad = create_async_engine(server.url(migrated, "reader:app"), poolclass=NullPool)
    try:
        for override in ({"i": "bad name!"}, {"r": -1}, {"e": ["lower"]}, {"f": "x" * 70}):
            async with bad.connect() as conn:
                with pytest.raises(DBAPIError):
                    await conn.execute(text(sql), {**args, **override})
    finally:
        await bad.dispose()
    runtime = create_async_engine(server.url(migrated, "runtime"), poolclass=NullPool)
    try:
        async with runtime.connect() as conn:
            with pytest.raises(DBAPIError, match="permission denied"):
                await conn.execute(text(sql), args)
    finally:
        await runtime.dispose()


async def test_reader_role_mapping_matches_the_roles_script():
    script = ROLES_SCRIPT.read_text()
    for service, logical in READER_SERVICES.items():
        assert f"['{service}', 'bc_{logical}']" in script


# ----------------------------------------------------------------- the write service


async def test_set_clear_restore_round_trip_verifies_through_the_views(svc, server, migrated):
    first = await put(svc, T1, 10)
    second = await put(svc, T1, 20)
    assert (first.version, second.version) == (1, 2)
    unchanged = await put(svc, T1, 20)
    assert not unchanged.changed
    rows, manifest = await read_view(server, migrated)
    result = verified(rows, manifest)
    assert result.rejections == []
    assert result.accepted[T1].value == 20 and result.revision == manifest.revision

    restored = await svc.restore(T1, 1, ADMIN)
    assert restored.version == 3
    rows, manifest = await read_view(server, migrated)
    assert verified(rows, manifest).accepted[T1].value == 10

    cleared = await svc.clear(T1, ADMIN)
    assert cleared.version == 4
    rows, manifest = await read_view(server, migrated)
    result = verified(rows, manifest)
    assert result.rejections == [] and T1 not in result.accepted
    # versions keep going up after a clear
    assert (await put(svc, T1, 11)).version == 5
    assert await svc.verify() == []


async def test_secrets_are_sealed_and_restore_reseals_with_a_fresh_key(svc, server, migrated, superuser):
    await put(svc, SECRET, PLANT)
    await put(svc, SECRET, PLANT + "-two")
    stored = await scalar(superuser, "SELECT blob FROM settings.entries WHERE key = :k", k=SECRET)
    assert stored.startswith("v2:") and PLANT not in stored
    spec = svc.registry.get(SECRET)
    result = await svc.restore(
        SECRET, 1, ADMIN, step_up=step_up(svc, "restore", SECRET, 1, version=2), confirmation=SECRET,
        expected_version=2,
    )
    assert result.version == 3
    rows, manifest = await read_view(server, migrated)
    row = verified(rows, manifest).accepted[SECRET]
    assert svc.keys.open(spec.section, SECRET, 3, row.blob) == PLANT
    old = await scalar(superuser, "SELECT blob FROM settings.history WHERE key = :k AND version = 1", k=SECRET)
    assert old != row.blob  # a fresh data key and nonce, not a copy


async def test_history_keeps_five_secret_versions_and_purge_removes_the_rest(svc, superuser):
    for i in range(8):
        await put(svc, SECRET, f"{PLANT}-{i}")
    versions = await scalar(
        superuser, "SELECT array_agg(version ORDER BY version) FROM settings.history WHERE key = :k", k=SECRET
    )
    assert versions == [4, 5, 6, 7, 8]
    deleted = await svc.purge_history(
        SECRET, ADMIN, step_up=step_up(svc, "purge_history", SECRET, version=8), confirmation=SECRET,
        expected_version=8,
    )
    assert deleted == 4
    assert await scalar(superuser, "SELECT count(*) FROM settings.history WHERE key = :k", k=SECRET) == 1
    # ordinary settings keep every version and cannot be purged
    for i in range(7):
        await put(svc, T1, i + 1)
    assert await scalar(superuser, "SELECT count(*) FROM settings.history WHERE key = :k", k=T1) == 7
    with pytest.raises(SettingsError) as err:
        await svc.purge_history(T1, ADMIN)
    assert err.value.code == "not_secret"


async def test_a_deleted_row_and_a_tampered_row_are_detected(svc, server, migrated, superuser):
    await put(svc, T1, 1)
    await put(svc, SECRET, PLANT)
    await as_superuser_raw(superuser, "DELETE FROM settings.entries WHERE key = :k", k=T1)
    rows, manifest = await read_view(server, migrated)
    result = verified(rows, manifest)
    assert [(r.key, r.reason) for r in result.rejections] == [(T1, "row_missing")]
    assert SECRET in result.accepted
    assert (T1, "row_missing") in {(p.key, p.reason) for p in await svc.verify()}

    # writing the deleted key again collides with its history: versions never restart
    with pytest.raises(Exception):
        await put(svc, T1, 2)
    other = "API_FLOW_EVENTS_WINDOW_SECONDS"
    await put(svc, other, 30)
    await as_superuser_raw(superuser, "UPDATE settings.entries SET value = '999'::jsonb WHERE key = :k", k=other)
    rows, manifest = await read_view(server, migrated)
    assert (other, "bad_signature") in {(r.key, r.reason) for r in verified(rows, manifest).rejections}
    problems = {(p.key, p.reason) for p in await svc.verify()}
    assert (other, "bad_signature") in problems


async def test_audit_rows_exist_and_hold_no_secret_values(svc, superuser):
    await put(svc, SECRET, PLANT)
    await put(svc, SECRET, PLANT + "-b")
    await svc.restore(SECRET, 1, ADMIN, step_up=step_up(svc, "restore", SECRET, 1, version=2), confirmation=SECRET, expected_version=2)
    await put(svc, T1, 5)
    async with superuser.connect() as conn:
        found = (
            await conn.execute(
                text("SELECT action, target_id, before::text AS b, after::text AS a, detail::text AS d FROM admin.audit_log ORDER BY seq")
            )
        ).all()
    assert [r.action for r in found] == ["settings.set"] * 2 + ["settings.restore", "settings.set"]
    blob = " ".join((r.b or "") + (r.a or "") + (r.d or "") for r in found)
    assert PLANT not in blob and "v2:" not in blob
    assert '"secret": "set"' in blob
    # the ordinary value is recorded
    assert '"value": 5' in found[-1].a


async def test_a_failing_audit_write_rolls_the_change_back(svc, superuser, monkeypatch):
    await put(svc, T1, 1)

    async def boom(*args, **kwargs):
        raise audit.AuditError("forced")

    monkeypatch.setattr(audit, "write", boom)
    with pytest.raises(audit.AuditError):
        await put(svc, T1, 2)
    assert await scalar(superuser, "SELECT version FROM settings.entries WHERE key = :k", k=T1) == 1
    assert await scalar(superuser, "SELECT count(*) FROM settings.history WHERE key = :k", k=T1) == 1
    assert await scalar(superuser, "SELECT revision FROM settings.manifest") == 1


async def test_the_outbox_gets_rows_for_t2_and_t3_only(svc, superuser):
    await put(svc, T1, 3)
    assert await scalar(superuser, "SELECT count(*) FROM admin.notifications") == 0
    await put(svc, T2, "openai")
    await put(svc, T3, "https://llm.example.org/v1")
    await put(svc, SECRET, PLANT)
    async with superuser.connect() as conn:
        rows = (await conn.execute(text("SELECT kind, payload::text AS p, status FROM admin.notifications ORDER BY created_at"))).all()
    assert len(rows) == 3 and {r.status for r in rows} == {"pending"}
    assert all(PLANT not in r.p and "llm.example.org" not in r.p for r in rows)


async def test_tier_and_key_rules(svc):
    for key, code in ((T4, "managed_by_task"), ("DATABASE_URL", "env_only"), ("NOT_A_SETTING", "unknown_key")):
        with pytest.raises(SettingsError) as err:
            await svc.set(key, "x" * 40, ADMIN)
        assert err.value.code == code
    with pytest.raises(SettingsError) as err:
        await svc.clear(T4, ADMIN)
    assert err.value.code == "managed_by_task"
    with pytest.raises(SettingsError) as err:
        await svc.set(T1, "not a number", ADMIN)
    assert err.value.code == "invalid_value"
    with pytest.raises(SettingsError) as err:
        await svc.set(T3, "https://169.254.169.254/latest", ADMIN, step_up=step_up(svc, "set", T3, "https://169.254.169.254/latest"), confirmation=T3, expected_version=0)
    assert err.value.code == "invalid_value"
    with pytest.raises(SettingsError) as err:
        await svc.set(SECRET, "  ", ADMIN, step_up=step_up(svc, "set", SECRET, "  "), confirmation=SECRET, expected_version=0)
    assert err.value.code == "invalid_value"


async def test_step_up_is_enforced(svc, superuser):
    value = "https://llm.example.org/v1"
    with pytest.raises(SettingsError) as err:
        await svc.set(T3, value, ADMIN, expected_version=0)
    assert err.value.code == "step_up_required"
    good = step_up(svc, "set", T3, value)
    # bound to another value, another key, another action, another admin, expired, too long-lived
    wrong = [
        step_up(svc, "set", T3, "https://other.example.org/"),
        step_up(svc, "set", T2, value),
        step_up(svc, "clear", T3, value),
        step_up(svc, "set", T3, value, Actor("admin", "other@example.org")),
        StepUp(good.action_hash, ADMIN.email, datetime.now(timezone.utc) - timedelta(seconds=1)),
        StepUp(good.action_hash, ADMIN.email, datetime.now(timezone.utc) + timedelta(hours=1)),
    ]
    for token in wrong:
        with pytest.raises(SettingsError) as err:
            await svc.set(T3, value, ADMIN, step_up=token, confirmation=T3, expected_version=0)
        assert err.value.code == "step_up_invalid"
    with pytest.raises(SettingsError) as err:
        await svc.set(T3, value, ADMIN, step_up=good, expected_version=0)
    assert err.value.code == "confirmation_required"
    assert await scalar(superuser, "SELECT count(*) FROM settings.entries") == 0
    assert (await svc.set(T3, value, ADMIN, step_up=good, confirmation=T3, expected_version=0)).version == 1


async def test_import_once_never_overwrites_and_takes_t4(svc):
    secret = "k" * 40
    first = await svc.import_once(T4, secret, CLI)
    assert first is not None and first.version == 1
    assert await svc.import_once(T4, "z" * 40, CLI) is None
    await svc.import_once(T1, 9, CLI)
    assert await svc.import_once(T1, 10, CLI) is None
    with pytest.raises(SettingsError) as err:
        await svc.import_once(T1, 10, ADMIN)
    assert err.value.code == "not_for_admins"
    with pytest.raises(SettingsError):
        await svc.import_once("DATABASE_URL", "postgresql://x", CLI)
    assert await svc.verify() == []


# ----------------------------------------------------------------- verify and rewrap


async def test_verify_catches_a_manifest_rollback_inside_the_database(svc, superuser):
    await put(svc, T1, 1)
    async with superuser.connect() as conn:
        old = (await conn.execute(text("SELECT revision, digest, entries::text AS e, sig FROM settings.manifest"))).one()
    await put(svc, T1, 2)
    await as_superuser_raw(
        superuser,
        "UPDATE settings.manifest SET revision = :r, digest = :d, entries = CAST(:e AS jsonb), sig = :s",
        r=old.revision, d=old.digest, e=old.e, s=old.sig,
    )
    problems = {(p.key, p.reason) for p in await svc.verify()}
    assert ("*", "manifest_rollback") in problems
    assert (T1, "manifest_mismatch") in problems


async def test_verify_cross_checks_the_audit_trail(svc, superuser):
    await put(svc, T1, 1)
    # a validly signed row that the audit trail never recorded: forge as the key holder
    await as_superuser_raw(superuser, "DELETE FROM admin.audit_log")
    assert (T1, "no_audit_record") in {(p.key, p.reason) for p in await svc.verify()}


async def test_rewrap_with_the_previous_key_leaves_rows_readable_with_the_new_key_only(svc, server, migrated, superuser):
    await put(svc, SECRET, PLANT)
    await put(svc, SECRET, PLANT + "-b")
    await put(svc, T1, 4)
    new_master = base64.b64encode(bytes(range(100, 148))).decode()
    rotating = SettingsService(svc._engine, store_registry(), make_keys(previous=MASTER_KEY, master=new_master))
    # the audit chain key follows the master key in this process
    result = await rotating.rewrap(CLI)
    assert result.rewrapped == 3 and result.resigned == 2 and result.batches == 1  # 1 entry + 2 history blobs
    again = await rotating.rewrap(CLI)
    assert (again.rewrapped, again.resigned, again.batches) == (0, 0, 0)

    new_only = make_keys(master=new_master)
    rows, manifest = await read_view(server, migrated)
    result = verify_snapshot(rows, manifest, new_only, registry=store_registry(), service="backend")
    assert result.rejections == [] and set(result.accepted) == {T1, SECRET}
    spec = svc.registry.get(SECRET)
    row = result.accepted[SECRET]
    assert new_only.open(spec.section, SECRET, row.version, row.blob) == PLANT + "-b"
    old_hist = await scalar(superuser, "SELECT blob FROM settings.history WHERE key = :k AND version = 1", k=SECRET)
    assert new_only.open(spec.section, SECRET, 1, old_hist) == PLANT
    # the old key alone no longer verifies the rows
    old_result = verified(rows, manifest)
    assert old_result.accepted == {} or SECRET not in old_result.accepted
    assert await SettingsService(svc._engine, store_registry(), new_only).verify() == []


# ----------------------------------------------------------------- the CLI


def run_cli(url, *args, master=MASTER_KEY, extra=None):
    env = {k: v for k, v in os.environ.items() if k not in (MASTER_KEY_KEY, DATABASE_URL_KEY)}
    env[DATABASE_URL_KEY] = url
    if master is not None:
        env[MASTER_KEY_KEY] = master
    env.update(extra or {})
    return subprocess.run(
        [sys.executable, "-m", "backend.admin", *args],
        cwd=BACKEND_ROOT, env=env, capture_output=True, text=True, timeout=120,
    )


async def test_settings_import_is_idempotent_never_overwrites_and_prints_no_values(server, migrated, svc, tmp_path):
    url = server.url(migrated, "runtime")
    env_file = tmp_path / "env"
    env_file.write_text(
        "\n".join(
            [
                f"{T1}=33",
                f"{SECRET}={PLANT}",
                "API_FLOW_EVENTS_WINDOW_SECONDS=",
                "NOT_A_SETTING=x",
                "DATABASE_URL=postgresql://u:p@h/db",
                f"{T4}=jwt-shipped-looking-but-fine-{'q' * 30}",
                "OPENAI_API_KEY=changeme",
            ]
        )
    )
    first = run_cli(url, "settings-import", "--env-file", str(env_file))
    assert PLANT not in first.stdout + first.stderr
    assert "imported=4" in first.stdout and "empty=1" in first.stdout
    assert "unknown=2" in first.stdout
    again = run_cli(url, "settings-import", "--env-file", str(env_file))
    assert "imported=0" in again.stdout and "existing=4" in again.stdout
    # the existing value is untouched
    assert (await svc.import_once(T1, 99, CLI)) is None
    # the audit rows carry actor_kind cli
    async with svc._engine.connect() as conn:
        kinds = (await conn.execute(text("SELECT DISTINCT actor_kind FROM admin.audit_log"))).scalars().all()
    assert kinds == ["cli"]
    verify = run_cli(url, "settings-verify")
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert PLANT not in verify.stdout


async def test_import_refuses_a_shipped_secret(svc, server, migrated, superuser, tmp_path, monkeypatch):
    import hashlib

    from common.configs import shipped_secrets

    shipped = "this-value-was-published-0123456789"
    monkeypatch.setattr(
        shipped_secrets, "SHIPPED_SECRET_SHA256", frozenset({hashlib.sha256(shipped.encode()).hexdigest()})
    )
    with pytest.raises(SettingsError) as err:
        await svc.import_once(SECRET, shipped, CLI)
    assert err.value.code == "invalid_value" and shipped not in str(err.value)
    env_file = tmp_path / "env"
    env_file.write_text(f"{SECRET}={shipped}\n")
    assert await scalar(superuser, "SELECT count(*) FROM settings.entries") == 0


async def test_settings_import_without_the_master_key_writes_nothing(server, migrated, superuser, tmp_path):
    env_file = tmp_path / "env"
    env_file.write_text(f"{T1}=33\n")
    result = run_cli(server.url(migrated, "runtime"), "settings-import", "--env-file", str(env_file), master=None)
    assert result.returncode == 2
    assert await scalar(superuser, "SELECT count(*) FROM settings.entries") == 0


async def test_settings_verify_cli_reports_a_corrupted_row_and_never_a_value(svc, server, migrated, superuser):
    await put(svc, T1, 1)
    await put(svc, SECRET, PLANT)
    url = server.url(migrated, "runtime")
    assert run_cli(url, "settings-verify").returncode == 0
    await as_superuser_raw(superuser, "UPDATE settings.entries SET value = '12345'::jsonb WHERE key = :k", k=T1)
    result = run_cli(url, "settings-verify")
    assert result.returncode == 1
    assert f"{T1} bad_signature" in result.stdout
    assert "12345" not in result.stdout and PLANT not in result.stdout + result.stderr


async def test_rewrap_cli(svc, server, migrated):
    await put(svc, SECRET, PLANT)
    url = server.url(migrated, "runtime")
    done = run_cli(url, "rewrap", extra={"SETTINGS_MASTER_KEY_PREVIOUS": MASTER_KEY})
    assert done.returncode == 0 and "rewrapped=0 resigned=0" in done.stdout
    assert PLANT not in done.stdout + done.stderr


# ----------------------------------------------------------------- review fixes


async def test_a_wiped_store_is_not_reported_clean(svc, superuser):
    await put(svc, T1, 1)
    await put(svc, T1, 2)
    assert await svc.verify() == []
    for sql in (
        "DELETE FROM settings.history",
        "DELETE FROM settings.entries",
        "UPDATE settings.manifest SET revision = 0, digest = repeat('0', 64), entries = '{}'::jsonb, sig = ''",
    ):
        await as_superuser_raw(superuser, sql)
    problems = {(p.key, p.reason) for p in await svc.verify()}
    assert ("*", "manifest_rollback") in problems
    assert (T1, "row_missing") in problems


async def test_a_cleared_key_without_a_row_is_not_reported_missing_but_a_set_one_is(svc, superuser):
    await put(svc, T1, 1)
    await svc.clear(T1, ADMIN, expected_version=1)
    await as_superuser_raw(superuser, "DELETE FROM settings.history")
    await as_superuser_raw(superuser, "DELETE FROM settings.entries")
    await as_superuser_raw(superuser, "UPDATE settings.manifest SET entries = '{}'::jsonb")
    assert (T1, "row_missing") not in {(p.key, p.reason) for p in await svc.verify()}


async def test_a_missing_manifest_row_is_reported_not_raised(svc, superuser):
    await put(svc, T1, 1)
    await as_superuser_raw(superuser, "DELETE FROM settings.manifest")
    assert ("*", "manifest_missing") in {(p.key, p.reason) for p in await svc.verify()}


async def test_cli_verify_reports_a_missing_manifest(svc, server, migrated, superuser):
    await put(svc, T1, 1)
    await as_superuser_raw(superuser, "DELETE FROM settings.manifest")
    result = run_cli(server.url(migrated, "runtime"), "settings-verify")
    assert result.returncode == 1 and "* manifest_missing" in result.stdout


async def test_a_step_up_cannot_be_replayed_and_stale_forms_are_refused(svc):
    value_a, value_b = "https://a.example.org/v1", "https://b.example.org/v1"
    first = step_up(svc, "set", T3, value_a, version=0)
    await svc.set(T3, value_a, ADMIN, step_up=first, confirmation=T3, expected_version=0)
    second = step_up(svc, "set", T3, value_b, version=1)
    await svc.set(T3, value_b, ADMIN, step_up=second, confirmation=T3, expected_version=1)
    with pytest.raises(SettingsError) as err:  # replay of the first token: bound to version 0
        await svc.set(T3, value_a, ADMIN, step_up=first, confirmation=T3, expected_version=0)
    assert err.value.code == "stale_version"
    with pytest.raises(SettingsError) as err:  # the version is bound into the token
        await svc.set(T3, value_a, ADMIN, step_up=first, confirmation=T3, expected_version=2)
    assert err.value.code == "step_up_invalid"
    with pytest.raises(SettingsError) as err:  # a step-up tier needs the version
        await svc.set(T3, value_a, ADMIN, step_up=first, confirmation=T3)
    assert err.value.code == "expected_version_required"
    # a plain (T1) change with a stale version is refused too
    await put(svc, T1, 1)
    with pytest.raises(SettingsError) as err:
        await svc.set(T1, 2, ADMIN, expected_version=0)
    assert err.value.code == "stale_version"
    assert await ver(svc, T3) == 2


async def test_a_planted_future_history_row_is_refused(svc, server, migrated):
    await put(svc, T1, 1)
    owner = create_async_engine(server.url(migrated, "runtime"), poolclass=NullPool)
    try:
        async with owner.connect() as conn:
            with pytest.raises(DBAPIError):
                await conn.execute(
                    text(
                        "INSERT INTO settings.history (key, version, section, is_secret, value, cleared, "
                        "action, source, actor, at) VALUES (:k, 5, 'rate_limits', false, '1'::jsonb, "
                        "false, 'set', 'portal', 'x', now())"
                    ),
                    {"k": T1},
                )
    finally:
        await owner.dispose()
    # the next real write still works
    assert (await put(svc, T1, 3)).version == 2


async def test_rewrap_skips_and_reports_unknown_keys(svc, superuser):
    from common.settings.registry import Registry

    await put(svc, T1, 1)
    await put(svc, SECRET, PLANT)
    smaller = Registry(
        [s for s in store_registry() if s.key != T1], secret_problems=lambda k, v: []
    )
    service = SettingsService(svc._engine, smaller, make_keys())
    result = await service.rewrap(CLI)
    assert result.skipped == (T1,)


async def test_report_state_prunes_only_the_callers_stale_rows(server, migrated, superuser):
    sql = "SELECT settings.report_state(:i, 1, CAST('{}' AS text[]), CAST('{}' AS text[]), false, '')"
    async with superuser.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied) "
                "SELECT 'backend', 'old-' || g, now() - interval '8 days', 1 FROM generate_series(1, 100) g"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied) "
                "VALUES ('auth', 'old-auth', now() - interval '30 days', 1)"
            )
        )
    engine = create_async_engine(server.url(migrated, "reader:app"), poolclass=NullPool)
    try:
        async with engine.begin() as conn:  # at the cap, but every row is stale: accepted
            await conn.execute(text(sql), {"i": "new-1"})
        count = await scalar(superuser, "SELECT count(*) FROM settings.service_state WHERE service = 'backend'")
        assert count == 1
        assert await scalar(superuser, "SELECT count(*) FROM settings.service_state WHERE service = 'auth'") == 1
        # recent rows are never pruned: 100 instances in the last week fill the cap
        async with superuser.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied) "
                    "SELECT 'backend', 'recent-' || g, now() - interval '6 days', 1 FROM generate_series(1, 99) g"
                )
            )
        async with engine.connect() as conn:
            with pytest.raises(DBAPIError, match="too many instances"):
                await conn.execute(text(sql), {"i": "new-2"})
        assert await scalar(superuser, "SELECT count(*) FROM settings.service_state WHERE service = 'backend'") == 100
    finally:
        await engine.dispose()
    # still callable by readers only
    assert not await scalar(
        superuser,
        "SELECT has_function_privilege('public', 'settings.report_state(text, bigint, text[], text[], boolean, text)', 'EXECUTE')",
    )
