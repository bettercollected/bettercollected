"""The audit writer, its database guards and chain verification, on real Postgres."""

from __future__ import annotations

import asyncio
import base64
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

import backend.admin as admin_package
from backend.admin.config import DATABASE_URL_KEY, MASTER_KEY_KEY
from backend.admin.security.keys import derive_key
from backend.admin.services import audit
from tests.admin.conftest import MASTER_KEY, needs_postgres

pytestmark = needs_postgres

BACKEND_ROOT = Path(admin_package.__file__).resolve().parents[2]
ACTOR = dict(actor_kind="admin", actor_email="ops@example.org")


async def add(conn, n: int = 1, **overrides):
    entries = []
    for i in range(n):
        args = dict(
            action="setting.update",
            target_type="setting",
            target_id=f"s{i}",
            before={"value": i},
            after={"value": i + 1},
            outcome="success",
            **ACTOR,
        )
        args.update(overrides)
        action, target_type, target_id, before, after, outcome = (
            args.pop(k)
            for k in (
                "action",
                "target_type",
                "target_id",
                "before",
                "after",
                "outcome",
            )
        )
        entries.append(
            await audit.write(
                conn, action, target_type, target_id, before, after, outcome, **args
            )
        )
    return entries


async def verify(engine, **kw):
    async with engine.connect() as conn:
        return await audit.verify_chain(conn, **kw)


async def seeded(runtime_engine, n: int = 5):
    async with runtime_engine.begin() as conn:
        return await add(conn, n)


async def as_owner(owner_engine, sql: str, **params):
    async with owner_engine.begin() as conn:
        await conn.execute(text(sql), params)


# -- database guards ----------------------------------------------------------------
async def test_runtime_role_cannot_update_delete_or_truncate(runtime_engine):
    await seeded(runtime_engine, 2)
    for sql in (
        "UPDATE admin.audit_log SET outcome = 'denied'",
        "DELETE FROM admin.audit_log",
        "TRUNCATE admin.audit_log",
    ):
        async with runtime_engine.connect() as conn:
            with pytest.raises(DBAPIError, match="permission denied"):
                await conn.execute(text(sql))


async def test_triggers_stop_the_owner_too(owner_engine, runtime_engine):
    await seeded(runtime_engine, 2)
    for sql, what in (
        ("UPDATE admin.audit_log SET outcome = 'denied'", "UPDATE"),
        ("DELETE FROM admin.audit_log", "DELETE"),
        ("TRUNCATE admin.audit_log", "TRUNCATE"),
    ):
        async with owner_engine.connect() as conn:
            with pytest.raises(DBAPIError, match=f"append-only.*{what}"):
                await conn.execute(text(sql))
    assert (await verify(runtime_engine)).rows == 2


async def _raw_insert(conn, prev_hash: bytes):
    await conn.execute(
        text(
            "INSERT INTO admin.audit_log (id, at, actor_kind, action, outcome, prev_hash, row_hash) "
            "VALUES (:id, now(), 'system', 'x', 'success', :p, :h)"
        ),
        {"id": uuid.uuid4(), "p": prev_hash, "h": os.urandom(32)},
    )


async def test_insert_with_a_wrong_prev_hash_is_refused(runtime_engine):
    # empty log: only the genesis hash is acceptable
    async with runtime_engine.connect() as conn:
        with pytest.raises(DBAPIError, match="not the chain head"):
            await _raw_insert(conn, os.urandom(32))
    async with runtime_engine.begin() as conn:
        await _raw_insert(conn, audit.GENESIS_HASH)  # the genesis hash is accepted
    # non-empty: a stale or invented hash is refused, even the genesis one
    for bad in (audit.GENESIS_HASH, os.urandom(32)):
        async with runtime_engine.connect() as conn:
            with pytest.raises(DBAPIError, match="not the chain head"):
                await _raw_insert(conn, bad)


async def test_hash_columns_must_be_32_bytes(runtime_engine):
    async with runtime_engine.connect() as conn:
        with pytest.raises(DBAPIError, match="hash_lengths"):
            await conn.execute(
                text(
                    "INSERT INTO admin.audit_log (id, at, actor_kind, action, outcome, prev_hash, row_hash) "
                    "VALUES (:id, now(), 'system', 'x', 'success', :p, :h)"
                ),
                {"id": uuid.uuid4(), "p": audit.GENESIS_HASH, "h": b"short"},
            )


# -- the chain ------------------------------------------------------------------------
async def test_a_written_chain_verifies_and_links_rows(runtime_engine):
    async with runtime_engine.begin() as conn:
        entries = await add(conn, 3)
        await add(
            conn,
            action="session.revoke",
            target_type=None,
            target_id=None,
            before=None,
            after=None,
            outcome="denied",
            actor_kind="anonymous",
            actor_email=None,
            session_id=str(uuid.uuid4()),
            ip="2001:db8::1",
            ua="Mozilla/5.0 é中",
            request_id="req-1",
            detail={"big": 2**70, "flag": True, "emoji": "\U0001f600", "f": 1.25},
        )
        await add(conn, ip="10.1.2.3")
    result = await verify(runtime_engine)
    assert result.ok and result.rows == 5 and result.head_seq == entries[0].seq + 4
    async with runtime_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT seq, prev_hash, row_hash FROM admin.audit_log ORDER BY seq"
                )
            )
        ).all()
    assert bytes(rows[0].prev_hash) == audit.GENESIS_HASH
    for before_row, row in zip(rows, rows[1:]):
        assert bytes(row.prev_hash) == bytes(before_row.row_hash)


async def test_verification_with_another_key_fails_at_the_first_row(runtime_engine):
    entries = await seeded(runtime_engine, 3)
    other = derive_key("pepper")
    result = await verify(runtime_engine, key=other)
    assert (result.ok, result.break_seq, result.reason) == (
        False,
        entries[0].seq,
        "row_hash_mismatch",
    )


async def _disable_triggers(owner_engine):
    await as_owner(owner_engine, "ALTER TABLE admin.audit_log DISABLE TRIGGER USER")


async def test_a_tampered_row_is_detected(owner_engine, runtime_engine):
    entries = await seeded(runtime_engine)
    await _disable_triggers(owner_engine)
    await as_owner(
        owner_engine,
        "UPDATE admin.audit_log SET after = '{\"value\": 999}' WHERE seq = :s",
        s=entries[2].seq,
    )
    result = await verify(runtime_engine)
    assert (result.ok, result.break_seq, result.reason) == (
        False,
        entries[2].seq,
        "row_hash_mismatch",
    )
    assert result.rows == 2


async def test_a_deleted_row_is_detected(owner_engine, runtime_engine):
    entries = await seeded(runtime_engine)
    await _disable_triggers(owner_engine)
    await as_owner(
        owner_engine, "DELETE FROM admin.audit_log WHERE seq = :s", s=entries[1].seq
    )
    result = await verify(runtime_engine)
    assert (result.ok, result.break_seq, result.reason) == (
        False,
        entries[2].seq,
        "prev_hash_mismatch",
    )


async def test_a_reordered_row_is_detected(owner_engine, runtime_engine):
    entries = await seeded(runtime_engine)
    await _disable_triggers(owner_engine)
    a, b = entries[1].seq, entries[2].seq
    await as_owner(
        owner_engine,
        "ALTER TABLE admin.audit_log ALTER COLUMN seq SET GENERATED BY DEFAULT",
    )
    async with owner_engine.begin() as conn:
        await conn.execute(
            text("UPDATE admin.audit_log SET seq = 1000 WHERE seq = :a"), {"a": a}
        )
        await conn.execute(
            text("UPDATE admin.audit_log SET seq = :a WHERE seq = :b"), {"a": a, "b": b}
        )
        await conn.execute(
            text("UPDATE admin.audit_log SET seq = :b WHERE seq = 1000"), {"b": b}
        )
    result = await verify(runtime_engine)
    assert (result.ok, result.break_seq, result.reason) == (
        False,
        a,
        "prev_hash_mismatch",
    )


async def test_a_checkpoint_proves_the_tail_is_still_there(
    owner_engine, runtime_engine
):
    entries = await seeded(runtime_engine)
    last = entries[-1]
    await _disable_triggers(owner_engine)
    await as_owner(
        owner_engine, "DELETE FROM admin.audit_log WHERE seq = :s", s=last.seq
    )
    assert (await verify(runtime_engine)).ok  # a chain alone cannot see a cut tail
    result = await verify(runtime_engine, checkpoint=(last.seq, last.row_hash))
    assert (result.ok, result.break_seq, result.reason) == (
        False,
        last.seq,
        "checkpoint_missing",
    )
    ok = await verify(runtime_engine, checkpoint=(entries[1].seq, entries[1].row_hash))
    assert ok.ok
    bad = await verify(runtime_engine, checkpoint=(entries[1].seq, os.urandom(32)))
    assert bad.reason == "checkpoint_mismatch"


async def test_checkpoints_print_every_100_rows_and_only_after_commit(
    owner_engine, runtime_engine, capsys
):
    await as_owner(
        owner_engine, "ALTER TABLE admin.audit_log ALTER COLUMN seq RESTART WITH 99"
    )
    async with runtime_engine.begin() as conn:
        first, second = await add(conn, 2)  # seq 99, 100
    assert (first.seq, second.seq) == (99, 100)
    out = capsys.readouterr().out
    assert out.splitlines() == [
        f"audit.checkpoint seq=100 row_hash={second.row_hash.hex()}"
    ]

    await as_owner(
        owner_engine, "ALTER TABLE admin.audit_log ALTER COLUMN seq RESTART WITH 200"
    )
    with pytest.raises(RuntimeError, match="abort"):
        async with runtime_engine.begin() as conn:
            await add(conn)  # seq 200, rolled back
            raise RuntimeError("abort")
    assert "audit.checkpoint" not in capsys.readouterr().out


# -- writer behaviour ------------------------------------------------------------------
async def test_masking_applies_before_anything_is_stored(runtime_engine):
    async with runtime_engine.begin() as conn:
        await add(
            conn,
            before={
                "name": "a",
                "password": "hunter2",
                "nested": {"api_token": "tok-123"},
            },
            after={"otp": "654321", "note": "x" * 5000},
            detail={"Authorization": "Bearer abc"},
        )
    async with runtime_engine.connect() as conn:
        stored = (
            await conn.execute(
                text(
                    "SELECT before::text, after::text, detail::text FROM admin.audit_log"
                )
            )
        ).one()
    blob = " ".join(stored)
    for secret in ("hunter2", "tok-123", "654321", "Bearer abc"):
        assert secret not in blob
    assert "[redacted]" in blob and "truncated" in blob
    assert (await verify(runtime_engine)).ok


async def test_oversize_payloads_are_refused_and_nothing_is_written(runtime_engine):
    big = {"items": ["y" * 200 for _ in range(50)]}  # ~10 KB after truncation
    for field in ("before", "after", "detail"):
        async with runtime_engine.connect() as conn:
            with pytest.raises(audit.AuditPayloadTooLarge):
                await add(conn, **{field: big})
    assert (await verify(runtime_engine)).rows == 0


async def test_bad_arguments_are_refused(runtime_engine):
    async with runtime_engine.connect() as conn:
        for bad in (
            dict(outcome="maybe"),
            dict(actor_kind="root"),
            dict(action=""),
            dict(ip="not-an-ip"),
            dict(session_id="nope"),
        ):
            with pytest.raises(audit.AuditError):
                await add(conn, **bad)


async def test_the_audit_write_fails_closed(runtime_engine, monkeypatch):
    """A row the database refuses takes the caller's whole transaction with it."""
    original = audit.repo.head_and_now

    async def stale_head(conn):
        _, now = await original(conn)
        return b"\x01" * 32, now  # the insert trigger will refuse this

    monkeypatch.setattr(audit.repo, "head_and_now", stale_head)
    async with runtime_engine.connect() as conn:
        trans = await conn.begin()
        await conn.execute(
            text(
                "INSERT INTO admin.attempts (key, window_start, count) VALUES ('k', now(), 1)"
            )
        )
        with pytest.raises(DBAPIError, match="not the chain head"):
            await add(conn)
        await trans.rollback()
    async with runtime_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM admin.attempts")) == 0
        assert await conn.scalar(text("SELECT count(*) FROM admin.audit_log")) == 0


async def test_an_error_inside_the_callers_transaction_discards_the_audit_row(
    runtime_engine,
):
    with pytest.raises(RuntimeError):
        async with runtime_engine.begin() as conn:
            await add(conn)
            raise RuntimeError("the action failed after auditing")
    assert (await verify(runtime_engine)).rows == 0


async def test_concurrent_writers_keep_a_single_chain(runtime_engine):
    async def writer(n: int):
        for i in range(5):
            async with runtime_engine.begin() as conn:
                await add(conn, target_id=f"w{n}-{i}")

    await asyncio.gather(*(writer(n) for n in range(8)))
    result = await verify(runtime_engine)
    assert result.ok and result.rows == 40
    async with runtime_engine.connect() as conn:
        heads = await conn.scalar(
            text(
                "SELECT count(*) FROM admin.audit_log a WHERE NOT EXISTS "
                "(SELECT 1 FROM admin.audit_log b WHERE b.prev_hash = a.row_hash)"
            )
        )
    assert heads == 1  # exactly one row nobody points at: the head


# -- the CLI -------------------------------------------------------------------------------
def _cli(url: str, key: str | None = MASTER_KEY, *args: str):
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in (MASTER_KEY_KEY, DATABASE_URL_KEY)
    }
    env[DATABASE_URL_KEY] = url
    if key is not None:
        env[MASTER_KEY_KEY] = key
    return subprocess.run(
        [sys.executable, "-m", "backend.admin", "audit-verify", *args],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


async def test_audit_verify_cli_reports_counts_and_the_first_break(
    server, migrated, owner_engine, runtime_engine
):
    url = server.url(migrated, "runtime")
    async with runtime_engine.begin() as conn:
        entries = await add(conn, 4, before={"note": "CONTENT-MARKER"})
    ok = await asyncio.to_thread(_cli, url)
    assert ok.returncode == 0, ok.stderr
    assert ok.stdout.strip() == f"audit chain OK: 4 rows, head seq {entries[-1].seq}"

    await _disable_triggers(owner_engine)
    await as_owner(
        owner_engine,
        "UPDATE admin.audit_log SET target_id = 'x' WHERE seq = :s",
        s=entries[1].seq,
    )
    broken = await asyncio.to_thread(_cli, url)
    assert broken.returncode == 1
    assert broken.stdout.strip() == (
        f"audit chain BROKEN at seq {entries[1].seq} (row_hash_mismatch); 1 rows checked before the break"
    )
    assert "CONTENT-MARKER" not in broken.stdout + broken.stderr


async def test_audit_verify_cli_refuses_without_a_master_key(server, migrated):
    done = await asyncio.to_thread(_cli, server.url(migrated, "runtime"), None)
    assert done.returncode == 2
    assert MASTER_KEY_KEY in done.stderr
    assert server.admin_pw not in done.stdout + done.stderr
    wrong = await asyncio.to_thread(
        _cli, server.url(migrated, "runtime"), base64.b64encode(os.urandom(48)).decode()
    )
    assert wrong.returncode == 0  # an empty log verifies under any key
