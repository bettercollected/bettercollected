"""The one pass that moves stored respondent identities to the keyed scheme
(backend.identity_rekey): converts every table that stores one, resumes after
an interruption, is idempotent, and reports counts only.

Keys are generated per run; the identities below are made from them."""

import json
import secrets

import pytest
from sqlalchemy import text

from backend import identity_rekey
from backend.app.container import container
from backend.app.utils import respondent_identity as identity
from backend.app.utils.hash import hash_string
from backend.app.utils.respondent_identity import key_check_value

EMAILS = [f"person{i}@example.org" for i in range(7)]


@pytest.fixture
def key() -> bytes:
    return secrets.token_bytes(32)


def _oid(prefix: str, n: int) -> str:
    return f"{prefix}{n:023x}"[-24:]


async def _insert(table: str, oid: str, stored) -> None:
    doc = {"_id": {"$oid": oid}, "form_id": "form-1", "response_id": f"r-{oid}"}
    if stored is not None:
        doc["anonymous_identity"] = stored
    async with container.pg_engine().begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO app.{table} (id, doc, created_at, _bc_checksum) "
                "VALUES (:i, CAST(:d AS jsonb), now(), 'x')"
            ),
            {"i": oid, "d": json.dumps(doc)},
        )


async def _stored(table: str) -> dict:
    async with container.pg_engine().connect() as conn:
        rows = await conn.execute(
            text(f"SELECT id, anonymous_identity, doc->>'anonymous_identity' FROM app.{table}")
        )
        values = {}
        for oid, column, in_doc in rows:
            assert column == in_doc  # the generated, indexed column follows the document
            values[oid] = column
        return values


@pytest.fixture
async def legacy_rows(clean_postgres):
    """Seven responses and seven deletion requests holding an MD5, plus rows that
    must not change: one with a JSON null identity."""
    for n, email in enumerate(EMAILS):
        await _insert("form_responses", _oid("a", n), hash_string(email))
        await _insert("responses_deletion_requests", _oid("b", n), hash_string(email))
    await _insert("form_responses", _oid("c", 1), None)


async def _write_check(key: bytes) -> None:
    """The key check row of ``key`` (what the first start or pass writes)."""
    async with container.pg_engine().begin() as conn:
        await conn.execute(
            text("INSERT INTO app.respondent_identity_key_check (id, check_value) VALUES (1, :v)"),
            {"v": key_check_value(key)},
        )


async def test_every_stored_identity_converts_without_the_address(legacy_rows, key):
    # one value that is already v2, made with this key and recorded
    await _insert("form_responses", _oid("c", 2), identity.identity_of("kept@example.org", key))
    await _write_check(key)
    report = await identity_rekey.rekey_identities(container.pg_engine(), key, batch_size=3)

    assert report.converted == {"form_responses": 7, "responses_deletion_requests": 7}
    assert report.remaining == {"form_responses": 0, "responses_deletion_requests": 0}
    assert report.done and not report.locked
    for n, email in enumerate(EMAILS):
        expected = identity.identity_of(email, key)
        assert (await _stored("form_responses"))[_oid("a", n)] == expected
        assert (await _stored("responses_deletion_requests"))[_oid("b", n)] == expected
    # nothing but identities changed: the others are as they were
    responses = await _stored("form_responses")
    assert responses[_oid("c", 1)] is None
    assert responses[_oid("c", 2)] == identity.identity_of("kept@example.org", key)
    # no plain MD5 remains anywhere
    for table in identity_rekey.TABLES:
        assert all(
            v is None or v.startswith("v2:") for v in (await _stored(table)).values()
        )


async def test_the_converted_value_is_what_a_sign_in_computes(legacy_rows, key):
    await identity_rekey.rekey_identities(container.pg_engine(), key)
    stored = (await _stored("form_responses"))[_oid("a", 3)]
    assert identity.matches(stored, EMAILS[3], key)
    assert not identity.matches(stored, EMAILS[4], key)


async def test_a_second_run_changes_nothing(legacy_rows, key):
    engine = container.pg_engine()
    await identity_rekey.rekey_identities(engine, key, batch_size=2)
    before = {t: await _stored(t) for t in identity_rekey.TABLES}
    again = await identity_rekey.rekey_identities(engine, key, batch_size=2)
    assert again.converted == {"form_responses": 0, "responses_deletion_requests": 0}
    assert again.done
    assert {t: await _stored(t) for t in identity_rekey.TABLES} == before


async def test_a_run_interrupted_midway_resumes_where_it_stopped(legacy_rows, key, monkeypatch):
    engine = container.pg_engine()
    real = identity_rekey.convert_legacy
    calls = []

    def crash_on_the_fifth(k, stored):
        calls.append(1)
        if len(calls) == 5:
            raise RuntimeError("interrupted")
        return real(k, stored)

    monkeypatch.setattr(identity_rekey, "convert_legacy", crash_on_the_fifth)
    with pytest.raises(RuntimeError, match="interrupted"):
        await identity_rekey.rekey_identities(engine, key, batch_size=2)

    # the two batches before the crash were committed, the crashing one rolled back
    partial = await _stored("form_responses")
    legacy_left = [v for v in partial.values() if v and not v.startswith("v2:")]
    assert len(legacy_left) == 3

    resumed_on = []
    monkeypatch.setattr(
        identity_rekey,
        "convert_legacy",
        lambda k, stored: resumed_on.append(stored) or real(k, stored),
    )
    resumed = await identity_rekey.rekey_identities(engine, key, batch_size=2)
    assert resumed.done
    # only what was left: 3 responses and 7 deletion requests; the 4 converted
    # rows were skipped, the lock the crashed run held was released
    assert len(resumed_on) == 10
    for table in identity_rekey.TABLES:
        assert all(v is None or v.startswith("v2:") for v in (await _stored(table)).values())


async def test_a_row_changed_after_it_was_read_is_not_overwritten(clean_postgres, key):
    """The update is conditional on the value that was read: a concurrent change
    (here a transaction holding the row) wins and the pass counts it, no more."""
    import asyncio

    engine = container.pg_engine()
    await _insert("form_responses", _oid("a", 1), hash_string(EMAILS[0]))
    newer = identity.identity_of(EMAILS[0], secrets.token_bytes(32))
    async with engine.connect() as other:
        await other.execute(
            text(
                "UPDATE app.form_responses SET doc = jsonb_set(doc, "
                "'{anonymous_identity}', to_jsonb(CAST(:v AS text)))"
            ),
            {"v": newer},
        )  # uncommitted: the row is locked, readers still see the old value
        task = asyncio.create_task(identity_rekey.rekey_identities(engine, key))
        for _ in range(100):
            async with engine.connect() as probe:
                waiting = await probe.scalar(
                    text("SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'")
                )
            if waiting:
                break
            await asyncio.sleep(0.05)
        assert waiting, "the pass never reached the locked row"
        await other.commit()
        report = await task
    assert report.changed_meanwhile["form_responses"] == 1
    assert report.converted["form_responses"] == 0
    assert (await _stored("form_responses"))[_oid("a", 1)] == newer


async def test_a_value_of_any_shape_ends_up_v2(clean_postgres, key):
    """A stray value (not an MD5) is wrapped too, so nothing is left unconverted."""
    await _insert("form_responses", _oid("a", 1), "forged-hash")
    await _insert("form_responses", _oid("a", 2), "")
    report = await identity_rekey.rekey_identities(container.pg_engine(), key)
    assert report.done
    assert all(v.startswith("v2:") for v in (await _stored("form_responses")).values())


async def test_dry_run_counts_and_changes_nothing(legacy_rows, key):
    before = {t: await _stored(t) for t in identity_rekey.TABLES}
    report = await identity_rekey.rekey_identities(container.pg_engine(), key, dry_run=True)
    assert report.remaining == {"form_responses": 7, "responses_deletion_requests": 7}
    assert report.converted == {}
    assert not report.done
    assert {t: await _stored(t) for t in identity_rekey.TABLES} == before


async def test_only_one_process_runs_the_pass(legacy_rows, key):
    engine = container.pg_engine()
    async with engine.connect() as holder:
        assert await holder.scalar(
            text("SELECT pg_try_advisory_lock(:k)"), {"k": identity_rekey.LOCK_KEY}
        )
        try:
            report = await identity_rekey.rekey_identities(engine, key)
            assert report.locked and not report.done
            assert (await _stored("form_responses"))[_oid("a", 0)] == hash_string(EMAILS[0])
        finally:
            await holder.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": identity_rekey.LOCK_KEY}
            )
    assert (await identity_rekey.rekey_identities(engine, key)).done


async def test_the_pass_logs_counts_only(legacy_rows, key, capsys):
    from loguru import logger

    lines = []
    sink = logger.add(lines.append, format="{message}")
    try:
        report = await identity_rekey.rekey_identities(container.pg_engine(), key)
        identity_rekey.log_report(report)
    finally:
        logger.remove(sink)
    text_out = "".join(str(m) for m in lines) + json.dumps(report.to_dict())
    assert "converted" in text_out
    for email in EMAILS:
        assert email not in text_out and hash_string(email) not in text_out
        assert identity.identity_of(email, key) not in text_out
    assert key.hex() not in text_out


async def test_a_failure_at_startup_is_logged_by_class_and_never_stops_the_start(
    legacy_rows, monkeypatch
):
    from loguru import logger

    class Leaky(Exception):
        pass

    async def boom(*args, **kwargs):
        raise Leaky(hash_string(EMAILS[0]))  # a driver error can carry parameters

    monkeypatch.setattr(identity_rekey, "rekey_identities", boom)
    lines = []
    sink = logger.add(lines.append, format="{message}")
    try:
        assert await identity_rekey.run_at_startup(container.pg_engine()) is None
    finally:
        logger.remove(sink)
    logged = "".join(str(m) for m in lines)
    assert "Leaky" in logged and hash_string(EMAILS[0]) not in logged


async def test_startup_without_a_database_is_a_no_op():
    assert await identity_rekey.run_at_startup(None) is None


async def test_the_start_converts_what_it_finds_with_the_configured_key(legacy_rows):
    """What the API runs at every start: the configured key, one pass, counts."""
    report = await identity_rekey.run_at_startup(container.pg_engine())
    assert report.done
    assert report.converted == {"form_responses": 7, "responses_deletion_requests": 7}
    stored = (await _stored("form_responses"))[_oid("a", 2)]
    assert identity.matches(stored, EMAILS[2])  # the configured key
    again = await identity_rekey.run_at_startup(container.pg_engine())
    assert again.converted == {"form_responses": 0, "responses_deletion_requests": 0}


# ------------------------------------------------------------------- the CLI


def _cli(*args, env_key=None):
    import asyncio
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = dict(os.environ)
    if env_key is None:
        env.pop("RESPONDENT_IDENTITY_KEY", None)
    else:
        env["RESPONDENT_IDENTITY_KEY"] = env_key
    env["DOTENV_PATH"] = "/nonexistent.env"
    backend_dir = Path(__file__).resolve().parents[3]
    return asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "backend.identity_rekey", *args],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


async def test_the_command_converts_prints_counts_and_exits_zero(legacy_rows):
    cli_key = secrets.token_hex(32)
    dry = await _cli("--dry-run", env_key=cli_key)
    assert dry.returncode == 1  # values remain (a dry run changes nothing)
    assert json.loads(dry.stdout)["remaining"] == {
        "form_responses": 7,
        "responses_deletion_requests": 7,
    }

    done = await _cli("--batch-size", "3", env_key=cli_key)
    assert done.returncode == 0, done.stderr[-1500:]
    report = json.loads(done.stdout)
    assert report["converted"] == {"form_responses": 7, "responses_deletion_requests": 7}
    assert report["remaining"] == {"form_responses": 0, "responses_deletion_requests": 0}
    for stream in (done.stdout, done.stderr):
        assert cli_key not in stream
        assert not any(hash_string(e) in stream for e in EMAILS)
    stored = (await _stored("form_responses"))[_oid("a", 1)]
    assert identity.matches(stored, EMAILS[1], bytes.fromhex(cli_key))

    again = await _cli(env_key=cli_key)
    assert again.returncode == 0
    assert json.loads(again.stdout)["converted"] == {
        "form_responses": 0,
        "responses_deletion_requests": 0,
    }


async def test_the_command_refuses_without_a_usable_key(legacy_rows):
    for bad in (None, secrets.token_hex(8)):
        result = await _cli(env_key=bad)
        assert result.returncode == 3
        assert "RESPONDENT_IDENTITY_KEY" in result.stderr
        if bad:
            assert bad not in result.stderr + result.stdout
    assert (await _stored("form_responses"))[_oid("a", 0)] == hash_string(EMAILS[0])


# ------------------------------------------------------------ the key check


async def _key_check():
    async with container.pg_engine().connect() as conn:
        return await identity_rekey.read_key_check(conn)


async def test_a_fresh_database_gets_the_check_row_before_the_first_conversion(
    clean_postgres, key, monkeypatch
):
    """No row and no v2 value: the row is written, then the pass converts. A crash
    mid-pass leaves the row behind, so the next start already knows the key."""
    await _insert("form_responses", _oid("a", 1), hash_string(EMAILS[0]))
    await _insert("form_responses", _oid("a", 2), hash_string(EMAILS[1]))
    assert await _key_check() is None

    def crash(k, stored):
        raise RuntimeError("interrupted")

    monkeypatch.setattr(identity_rekey, "convert_legacy", crash)
    with pytest.raises(RuntimeError, match="interrupted"):
        await identity_rekey.rekey_identities(container.pg_engine(), key)
    assert await _key_check() == key_check_value(key)  # written before the crash
    assert (await _stored("form_responses"))[_oid("a", 1)] == hash_string(EMAILS[0])


async def test_the_report_names_how_the_key_was_checked(clean_postgres, key):
    await _insert("form_responses", _oid("a", 1), hash_string(EMAILS[0]))
    engine = container.pg_engine()
    first = await identity_rekey.rekey_identities(engine, key)
    assert first.key_check == "written"
    assert first.fingerprint == key_check_value(key)[:8]
    second = await identity_rekey.rekey_identities(engine, key)
    assert second.key_check == "matched" and second.fingerprint == first.fingerprint
    assert set(first.to_dict()) >= {"key_check", "key_fingerprint"}


async def test_v2_values_without_a_check_row_are_not_adopted_by_a_pass(clean_postgres, key):
    await _insert("form_responses", _oid("a", 1), identity.identity_of(EMAILS[0], key))
    await _insert("form_responses", _oid("a", 2), hash_string(EMAILS[1]))
    for dry_run in (False, True):
        with pytest.raises(identity.IdentityKeyUnconfirmed) as refused:
            await identity_rekey.rekey_identities(container.pg_engine(), key, dry_run=dry_run)
        message = str(refused.value)
        assert key_check_value(key) not in message and key.hex() not in message
        assert "--expect-fingerprint <the recorded fingerprint>" in message
    assert await _key_check() is None
    assert (await _stored("form_responses"))[_oid("a", 2)] == hash_string(EMAILS[1])


async def test_the_operator_can_adopt_the_key_of_v2_values_stored_without_a_check_row(
    clean_postgres, key
):
    from loguru import logger

    await _insert("form_responses", _oid("a", 1), identity.identity_of(EMAILS[0], key))
    await _insert("form_responses", _oid("a", 2), hash_string(EMAILS[1]))
    lines = []
    sink = logger.add(lines.append, format="{level}|{message}")
    try:
        report = await identity_rekey.rekey_identities(container.pg_engine(), key, adopt=True)
    finally:
        logger.remove(sink)
    assert report.key_check == "adopted" and report.done
    assert await _key_check() == key_check_value(key)
    warned = [m for m in map(str, lines) if m.startswith("WARNING")]
    assert warned and all(key_check_value(key) not in w and key.hex() not in w for w in warned)


async def test_another_keys_check_row_refuses_and_converts_nothing(clean_postgres, key):
    engine = container.pg_engine()
    other = secrets.token_bytes(32)
    await _insert("form_responses", _oid("a", 1), hash_string(EMAILS[0]))
    await identity_rekey.rekey_identities(engine, other)  # the key that converted
    await _insert("form_responses", _oid("a", 2), hash_string(EMAILS[1]))  # a 4.0 straggler

    for dry_run in (False, True):
        with pytest.raises(identity.IdentityKeyMismatch) as refused:
            await identity_rekey.rekey_identities(engine, key, dry_run=dry_run)
        message = str(refused.value)
        assert key_check_value(key) not in message and key_check_value(other) not in message
        assert key.hex() not in message and other.hex() not in message
        assert key_check_value(key)[:8] in message  # the short fingerprints only
    assert (await _stored("form_responses"))[_oid("a", 2)] == hash_string(EMAILS[1])
    assert await _key_check() == key_check_value(other)  # untouched
    # the right key still finishes the job
    assert (await identity_rekey.rekey_identities(engine, other)).done


async def test_the_start_records_its_key_and_refuses_a_different_one(
    clean_postgres, key, monkeypatch
):
    engine = container.pg_engine()
    monkeypatch.setattr(identity, "_key_mismatch_seen", [False])
    monkeypatch.setattr(identity_rekey, "configured_key", lambda: key)
    await identity_rekey.check_key_at_startup(engine)  # nothing stored yet: its row is written
    assert await _key_check() == key_check_value(key)
    await identity_rekey.check_key_at_startup(engine)  # the same key again: fine

    other = secrets.token_bytes(32)
    monkeypatch.setattr(identity_rekey, "configured_key", lambda: other)
    with pytest.raises(identity.IdentityKeyMismatch, match="will not start"):
        await identity_rekey.check_key_at_startup(engine)
    assert await _key_check() == key_check_value(key)  # untouched
    # the background pass logs the refusal, never raises, and stops this process
    # from writing identities with the wrong key
    assert not identity.key_mismatch_seen()
    assert await identity_rekey.run_at_startup(engine) is None
    assert identity.key_mismatch_seen()
    assert await identity_rekey.check_key_at_startup(None) is None


async def test_a_replica_with_the_wrong_key_cannot_start_before_any_row_exists(clean_postgres):
    """Two replicas starting together with different keys and no row yet: the
    unique row decides; exactly one of them serves, whichever is first."""
    import asyncio

    engine = container.pg_engine()
    keys = [secrets.token_bytes(32), secrets.token_bytes(32)]
    results = await asyncio.gather(
        *(identity_rekey.check_key_at_startup(engine, k) for k in keys),
        return_exceptions=True,
    )
    assert sorted(type(r).__name__ for r in results) == ["IdentityKeyMismatch", "NoneType"]
    winner = keys[results.index(None)]
    loser = keys[1 - results.index(None)]
    assert await _key_check() == key_check_value(winner)

    # later starts: the wrong key never passes once the row exists
    with pytest.raises(identity.IdentityKeyMismatch):
        await identity_rekey.check_key_at_startup(engine, loser)
    await identity_rekey.check_key_at_startup(engine, winner)


async def test_the_start_refuses_v2_values_without_a_check_row(clean_postgres, key, monkeypatch):
    """The API never adopts a key: only the command does, once confirmed."""
    engine = container.pg_engine()
    await _insert("form_responses", _oid("a", 1), identity.identity_of(EMAILS[0], key))
    monkeypatch.setattr(identity_rekey, "configured_key", lambda: key)
    with pytest.raises(identity.IdentityKeyUnconfirmed, match="will not start"):
        await identity_rekey.check_key_at_startup(engine)
    assert await _key_check() is None  # nothing was written
    # the background pass refuses too, and stops the process writing identities
    monkeypatch.setattr(identity, "_key_mismatch_seen", [False])
    assert await identity_rekey.run_at_startup(engine) is None
    assert identity.key_mismatch_seen()


def test_a_known_key_mismatch_stops_new_identities(monkeypatch):
    monkeypatch.setattr(identity, "_key_mismatch_seen", [False])
    assert identity.identity_of(EMAILS[0]).startswith("v2:")
    identity.mark_key_mismatch()
    with pytest.raises(identity.IdentityKeyMismatch, match="refusing to write or match"):
        identity.identity_of(EMAILS[0])
    # an explicit key (the pass converting under its own key) is unaffected
    assert identity.identity_of(EMAILS[0], secrets.token_bytes(32)).startswith("v2:")


def test_the_lifespan_checks_the_key_then_converts_in_the_background():
    import inspect

    from backend.app import asgi

    source = inspect.getsource(asgi.lifespan)
    assert source.index("check_key_at_startup") < source.index("yield")
    assert source.index("start_background_passes") < source.index("yield")
    after = source.split("yield", 1)[1]
    assert "identity_task.cancel()" in after
    assert "except Exception" in after.split("identity_task.cancel()", 1)[1].split("mcp_stop.set()")[0]


async def test_the_background_task_runs_twice_and_stops_when_cancelled(monkeypatch):
    import asyncio

    runs = []

    async def fake(engine):
        runs.append(engine)

    async def verified(engine, *args, **kwargs):
        return True

    monkeypatch.setattr(identity_rekey, "run_at_startup", fake)
    monkeypatch.setattr(identity_rekey, "verify_key_until_known", verified)
    await identity_rekey.background_passes("engine", rerun_delay=0)
    assert runs == ["engine", "engine"]

    runs.clear()
    task = identity_rekey.start_background_passes(container.pg_engine())
    assert task is not None
    for _ in range(100):
        if runs:
            break
        await asyncio.sleep(0.01)
    task.cancel()  # during the wait for the second pass
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(runs) == 1
    assert identity_rekey.start_background_passes(None) is None


async def test_the_scans_use_the_partial_index_of_the_identities_still_to_convert(clean_postgres):
    """The queries carry the index's literal predicate, so a start that finds
    nothing left reads the (empty) index and not the tables."""
    for oid in (_oid("a", 1), _oid("a", 2)):
        await _insert("form_responses", oid, "v2:" + "0" * 64)
    async with container.pg_engine().begin() as conn:
        await conn.execute(text("SET LOCAL enable_seqscan = off"))
        for table, index in (
            ("form_responses", "ix_form_responses_legacy_identity"),
            ("responses_deletion_requests", "ix_deletion_requests_legacy_identity"),
        ):
            for statement in (
                f"SELECT id, anonymous_identity FROM app.{table} WHERE id > '' AND anonymous_identity "
                f"IS NOT NULL AND anonymous_identity NOT LIKE 'v2:%' ORDER BY id LIMIT 500",
                f"SELECT count(*) FROM app.{table} WHERE anonymous_identity IS NOT NULL "
                f"AND anonymous_identity NOT LIKE 'v2:%'",
            ):
                plan = "\n".join(
                    r[0] for r in await conn.execute(text("EXPLAIN " + statement))
                )
                assert index in plan, plan


async def test_a_failed_unlock_drops_the_lock_connection(legacy_rows, key, monkeypatch):
    """A session lock would otherwise live as long as its pooled connection."""
    from sqlalchemy.ext.asyncio import AsyncConnection

    engine = container.pg_engine()
    real_execute, real_invalidate = AsyncConnection.execute, AsyncConnection.invalidate
    invalidated = []

    async def failing_unlock(self, statement, *args, **kwargs):
        if "pg_advisory_unlock" in str(statement):
            raise RuntimeError("unlock failed")
        return await real_execute(self, statement, *args, **kwargs)

    async def spy(self, *args, **kwargs):
        invalidated.append(1)
        return await real_invalidate(self, *args, **kwargs)

    monkeypatch.setattr(AsyncConnection, "execute", failing_unlock)
    monkeypatch.setattr(AsyncConnection, "invalidate", spy)
    report = await identity_rekey.rekey_identities(engine, key)
    monkeypatch.undo()
    assert report.done and invalidated
    # the lock is gone with the connection: the next run is not locked out
    again = await identity_rekey.rekey_identities(engine, key)
    assert not again.locked


async def test_the_command_checks_the_expected_fingerprint_and_the_stored_key(legacy_rows):
    cli_key = secrets.token_hex(32)
    fingerprint = key_check_value(bytes.fromhex(cli_key))[:8]

    wrong = await _cli("--expect-fingerprint", "deadbeef", env_key=cli_key)
    assert wrong.returncode == 4
    assert (await _stored("form_responses"))[_oid("a", 0)] == hash_string(EMAILS[0])
    assert cli_key not in wrong.stdout + wrong.stderr

    right = await _cli("--expect-fingerprint", fingerprint.upper(), env_key=cli_key)
    assert right.returncode == 0, right.stderr[-1500:]
    assert json.loads(right.stdout)["key_fingerprint"] == fingerprint

    other = await _cli(env_key=secrets.token_hex(32))  # another key than the one that converted
    assert other.returncode == 4
    assert "will not start" in other.stderr


async def test_the_command_adopts_v2_values_only_with_the_confirmed_fingerprint(clean_postgres):
    cli_key = secrets.token_hex(32)
    raw = bytes.fromhex(cli_key)
    fingerprint = key_check_value(raw)[:8]
    await _insert("form_responses", _oid("a", 1), identity.identity_of(EMAILS[0], raw))
    await _insert("form_responses", _oid("a", 2), hash_string(EMAILS[1]))

    unconfirmed = await _cli(env_key=cli_key)
    assert unconfirmed.returncode == 4
    assert "--expect-fingerprint <the recorded fingerprint>" in unconfirmed.stderr
    wrong = await _cli("--expect-fingerprint", "deadbeef", env_key=cli_key)
    assert wrong.returncode == 4
    assert await _key_check() is None
    assert (await _stored("form_responses"))[_oid("a", 2)] == hash_string(EMAILS[1])

    adopted = await _cli("--expect-fingerprint", fingerprint, env_key=cli_key)
    assert adopted.returncode == 0, adopted.stderr[-1500:]
    assert json.loads(adopted.stdout)["key_check"] == "adopted"
    assert await _key_check() == key_check_value(raw)
    assert all(v.startswith("v2:") for v in (await _stored("form_responses")).values())
    assert cli_key not in adopted.stdout + adopted.stderr


# ----------------------------------------------- an unchecked key never serves


async def test_the_start_fails_hard_when_the_key_cannot_be_checked(clean_postgres, key, monkeypatch):
    """A transient database error must not let a replica serve with a key it
    could not check: the start fails (the container restarts)."""
    monkeypatch.setattr(identity, "_key_verified", [False])

    async def broken(*args, **kwargs):
        raise RuntimeError("could not connect: password=hunter2")

    monkeypatch.setattr(identity_rekey, "_ensure_key_check", broken)
    with pytest.raises(identity.IdentityKeyUnverified) as refused:
        await identity_rekey.check_key_at_startup(container.pg_engine(), key)
    assert "hunter2" not in str(refused.value) and "RuntimeError" in str(refused.value)
    assert not identity._key_verified[0]


async def test_a_checked_key_marks_the_process_verified(clean_postgres, key, monkeypatch):
    monkeypatch.setattr(identity, "_key_verified", [False])
    with pytest.raises(identity.IdentityKeyUnverified):
        identity.identity_of(EMAILS[0])  # nothing is created before the check
    await identity_rekey.check_key_at_startup(container.pg_engine(), key)
    monkeypatch.setattr(identity_rekey, "configured_key", lambda: key)
    assert identity.identity_of(EMAILS[0]).startswith("v2:")


async def test_a_failing_background_verification_blocks_identities_until_it_succeeds(
    clean_postgres, key, monkeypatch
):
    monkeypatch.setattr(identity, "_key_verified", [True])
    monkeypatch.setattr(identity, "_key_mismatch_seen", [False])
    real = identity_rekey._ensure_key_check
    calls, seen_during_retry = [], []

    async def flaky(engine, k, **kwargs):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("connection reset")
        seen_during_retry.append(identity._key_verified[0])
        return await real(engine, k, **kwargs)

    monkeypatch.setattr(identity_rekey, "_ensure_key_check", flaky)
    assert await identity_rekey.verify_key_until_known(
        container.pg_engine(), key, retry_seconds=0
    )
    assert len(calls) == 3
    assert seen_during_retry == [False]  # unverified while the check kept failing
    assert identity._key_verified[0]


async def test_a_mismatch_in_the_background_verification_is_final(clean_postgres, key, monkeypatch):
    monkeypatch.setattr(identity, "_key_verified", [True])
    monkeypatch.setattr(identity, "_key_mismatch_seen", [False])
    engine = container.pg_engine()
    await identity_rekey.rekey_identities(engine, secrets.token_bytes(32))
    assert not await identity_rekey.verify_key_until_known(engine, key, retry_seconds=0)
    assert identity.key_mismatch_seen() and not identity._key_verified[0]
    monkeypatch.setattr(identity_rekey, "configured_key", lambda: key)
    ran = []
    monkeypatch.setattr(identity_rekey, "run_at_startup", lambda e: ran.append(e))
    await identity_rekey.background_passes(engine, rerun_delay=0)
    assert ran == []  # no conversion under a key that is not the stored one


async def test_a_dry_run_reports_what_a_real_run_would_do(clean_postgres, key):
    engine = container.pg_engine()
    await _insert("form_responses", _oid("a", 1), hash_string(EMAILS[0]))
    dry = await identity_rekey.rekey_identities(engine, key, dry_run=True)
    assert dry.key_check == "would_write" and await _key_check() is None
    assert (await identity_rekey.rekey_identities(engine, key)).key_check == "written"


async def test_the_unconfirmed_message_has_no_ready_to_paste_command(clean_postgres, key):
    await _insert("form_responses", _oid("a", 1), identity.identity_of(EMAILS[0], key))
    with pytest.raises(identity.IdentityKeyUnconfirmed) as refused:
        await identity_rekey.rekey_identities(container.pg_engine(), key)
    message = str(refused.value)
    assert f"--expect-fingerprint {key_check_value(key)[:8]}" not in message
    assert "--expect-fingerprint <the recorded fingerprint>" in message
    assert f"Only if {key_check_value(key)[:8]} is the fingerprint you recorded" in message
