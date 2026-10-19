"""The admin service's background loops, on real Postgres: leader election, the
notification sender, retention and the integrity monitor."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import timedelta, timezone, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from backend.admin.asgi import get_admin_application
from backend.admin.gate.settings import GateSettings
from backend.admin.loops.base import Loop, LoopRunner
from backend.admin.loops.config import LoopSettings
from backend.admin.loops.integrity import IntegrityMonitor
from backend.admin.loops.notifications import (
    BadPayload,
    NotificationSender,
    render,
)
from backend.admin.loops.retention import RetentionLoop
from backend.admin.loops.status import StatusBoard
from backend.admin.portal_config import PortalConfigError
from backend.admin.security.clock import FakeClock
from backend.admin.security.mailer import (
    AdminMailer,
    EnvMailConfigProvider,
    FakeTransport,
)
from backend.admin.services.settings_store import SettingsService, store_registry
from tests.admin.conftest import _execute, needs_postgres, roles_sql
from tests.admin.test_settings_store import (
    PLANT,
    SECRET,
    T1,
    T3,
    as_superuser_raw,
    make_keys,
    put,
    scalar,
)

pytestmark = needs_postgres

ADMINS = ["first@example.org", "second@example.org"]


@pytest_asyncio.fixture(loop_scope="session")
async def superuser(server, migrated):
    engine = create_async_engine(server.url(migrated), poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
def now_clock():
    return FakeClock(time.time())  # outbox rows carry real database times


class SelectiveTransport(FakeTransport):
    """Fails for the addresses in ``bad`` only."""

    def __init__(self, bad=()):
        super().__init__()
        self.bad = set(bad)

    async def send(self, to, subject, body):
        if to in self.bad:
            raise ConnectionError("simulated failure for " + to)
        await super().send(to, subject, body)


def make_sender(engine, clock, transport, **kw):
    board = kw.pop("board", StatusBoard())
    sender = NotificationSender(
        engine,
        clock,
        AdminMailer.for_transport(transport),
        lambda: ADMINS,
        board,
        **kw,
    )
    return sender, board


async def enqueue(engine, kind="settings.changed", payload=None, dedupe=None):
    payload = payload or {
        "setting": T3,
        "tier": "T3",
        "action": "set",
        "version": 4,
        "actor": "ops@example.org",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO admin.notifications (kind, payload, dedupe_key) "
                "VALUES (:k, CAST(:p AS jsonb), :d)"
            ),
            {"k": kind, "p": json.dumps(payload), "d": dedupe},
        )


async def make_due(engine):
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE admin.notifications SET next_attempt_at = now() - interval '1 day' WHERE status = 'pending'")
        )


async def scalar_delay(engine) -> float:
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text("SELECT extract(epoch FROM next_attempt_at - now()) FROM admin.notifications")
            )
        ).scalar_one()


async def rows(engine, columns="kind, status, attempts, last_error_code, delivered_to"):
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text(f"SELECT {columns} FROM admin.notifications ORDER BY created_at, id")
            )
        ).all()


# --------------------------------------------------------------------- sender


async def test_every_admin_gets_exactly_one_mail_per_notification(
    runtime_engine, superuser, now_clock
):
    transport = FakeTransport()
    sender, board = make_sender(runtime_engine, now_clock, transport)
    await enqueue(runtime_engine)
    await enqueue(runtime_engine, "settings.keyset_changed", {"action": "promote", "version": 2, "actor": "ops@example.org"})
    outcome = await sender.run_once()
    assert outcome == "sent 2, retry 0, failed 0, mails 4"
    assert sorted(transport.recipients) == sorted(ADMINS * 2)
    first = transport.sent[0]
    assert first.subject == "Security notice: an admin setting was changed"
    assert T3 in first.body and "Version: 4" in first.body and "ops@example.org" in first.body
    assert {r.status for r in await rows(runtime_engine)} == {"sent"}
    assert board.mail == "ok"
    assert await sender.run_once() == "idle: nothing pending"
    assert len(transport.sent) == 4  # nothing is mailed twice


async def test_one_summary_audit_row_per_batch_with_counts_only(
    runtime_engine, superuser, now_clock
):
    transport = FakeTransport()
    sender, _ = make_sender(runtime_engine, now_clock, transport)
    for _ in range(3):
        await enqueue(runtime_engine)
    await sender.run_once()
    async with superuser.connect() as conn:
        audit_rows = (
            await conn.execute(
                text(
                    "SELECT actor_kind, actor_email, action, after::text AS a "
                    "FROM admin.audit_log WHERE action = 'notifications.batch'"
                )
            )
        ).all()
    assert len(audit_rows) == 1
    row = audit_rows[0]
    assert row.actor_kind == "system" and row.actor_email is None
    assert json.loads(row.a) == {"sent": 3, "retried": 0, "failed": 0, "mails": 6}
    assert not any(addr in row.a for addr in ADMINS)


async def test_unknown_kind_fails_with_a_fixed_code_and_is_never_rendered(
    runtime_engine, now_clock
):
    transport = FakeTransport()
    sender, _ = make_sender(runtime_engine, now_clock, transport)
    await enqueue(runtime_engine, "made.up_kind", {"anything": PLANT})
    assert (await sender.run_once()).startswith("sent 0, retry 0, failed 1")
    (row,) = await rows(runtime_engine)
    assert (row.status, row.last_error_code) == ("failed", "unknown_kind")
    assert transport.sent == []


async def test_a_payload_that_does_not_fit_its_template_fails_and_is_not_rendered(
    runtime_engine, now_clock
):
    transport = FakeTransport()
    sender, _ = make_sender(runtime_engine, now_clock, transport)
    # a value smuggled into a field the template prints
    await enqueue(
        runtime_engine,
        payload={"setting": PLANT, "tier": "T3", "action": "set", "version": 1, "actor": "a@example.org"},
    )
    await sender.run_once()
    (row,) = await rows(runtime_engine)
    assert (row.status, row.last_error_code) == ("failed", "bad_payload")
    assert transport.sent == []


async def test_secrets_in_the_payload_never_reach_mail_logs_or_audit(
    runtime_engine, superuser, now_clock, caplog
):
    transport = FakeTransport()
    sender, _ = make_sender(runtime_engine, now_clock, transport)
    keyset = '{"primaryKeyId": 1, "key": [{"keyData": {"value": "AQ' + PLANT + '"}}]}'
    caplog.set_level(logging.DEBUG)
    await enqueue(
        runtime_engine,
        payload={
            "setting": T3,
            "tier": "T3",
            "action": "set",
            "version": 7,
            "actor": "ops@example.org",
            "value": keyset,
            "password": PLANT,
            "params": {"MASTER": PLANT},
            "keyset": keyset,
        },
    )
    await enqueue(
        runtime_engine,
        "tasks.run",
        {"task": "responses.check_undecryptable", "run_id": str(uuid.uuid4()), "state": "queued", "actor": "ops@example.org", "params": {"k": PLANT}},
    )
    await sender.run_once()
    assert len(transport.sent) == 4
    everything = "\n".join(m.subject + "\n" + m.body for m in transport.sent)
    assert PLANT not in everything and "keyData" not in everything
    assert PLANT not in caplog.text
    async with superuser.connect() as conn:
        audit_text = (await conn.execute(text("SELECT string_agg(after::text || detail::text, ' ') FROM admin.audit_log"))).scalar() or ""
    assert PLANT not in audit_text


def test_templates_collapse_control_characters_and_check_shapes():
    message = render(
        "settings.changed",
        {"setting": T3, "tier": "T3", "action": "set", "version": 1, "actor": "a@example.org\r\nBcc: x@evil.test"},
    )
    assert "\r" not in message.body and "\n" + "Bcc" not in message.body
    assert "\n" not in message.subject
    with pytest.raises(KeyError):
        render("nope", {})
    with pytest.raises(BadPayload):
        render("settings.changed", {"setting": T3})
    with pytest.raises(BadPayload):
        render("settings.changed", "not a mapping")
    with pytest.raises(BadPayload):
        render("settings.changed", {"setting": T3, "tier": "T3", "action": "set", "version": True, "actor": "a"})


async def test_transport_failure_retries_with_backoff_then_gives_up(
    runtime_engine, now_clock
):
    transport = FakeTransport(fail=True)
    sender, _ = make_sender(runtime_engine, now_clock, transport, max_attempts=3)
    await enqueue(runtime_engine)
    assert (await sender.run_once()).startswith("sent 0, retry 1, failed 0")
    (row,) = await rows(runtime_engine)
    assert (row.status, row.attempts, row.last_error_code) == ("pending", 1, "delivery_failed")
    assert await sender.run_once() == "idle: nothing pending"  # backing off
    delay = await scalar_delay(runtime_engine)
    assert 55 <= delay <= 65
    await make_due(runtime_engine)
    assert (await sender.run_once()).startswith("sent 0, retry 1")
    delay = await scalar_delay(runtime_engine)
    assert 115 <= delay <= 125  # doubled
    await make_due(runtime_engine)
    assert (await sender.run_once()).startswith("sent 0, retry 0, failed 1")
    (row,) = await rows(runtime_engine)
    assert (row.status, row.attempts) == ("failed", 3)
    await make_due(runtime_engine)
    assert await sender.run_once() == "idle: nothing pending"  # no infinite retry


async def test_a_partial_failure_is_not_marked_sent_and_only_the_rest_is_retried(
    runtime_engine, now_clock
):
    transport = SelectiveTransport(bad={ADMINS[1]})
    sender, _ = make_sender(runtime_engine, now_clock, transport)
    await enqueue(runtime_engine)
    await sender.run_once()
    (row,) = await rows(runtime_engine)
    assert (row.status, row.attempts) == ("pending", 1)
    assert len(row.delivered_to) == 1 and ADMINS[0] not in row.delivered_to[0]
    assert transport.recipients == [ADMINS[0]]
    transport.bad.clear()
    await make_due(runtime_engine)
    await sender.run_once()
    (row,) = await rows(runtime_engine)
    assert row.status == "sent" and len(row.delivered_to) == 2
    assert transport.recipients == [ADMINS[0], ADMINS[1]]  # the first admin was not mailed again


async def test_the_sender_rate_limits_itself(runtime_engine, now_clock):
    transport = FakeTransport()
    sender, _ = make_sender(runtime_engine, now_clock, transport, max_per_minute=3)
    for _ in range(3):
        await enqueue(runtime_engine)
    await sender.run_once()
    assert len(transport.sent) == 3
    assert await sender.run_once() == "idle: rate limited"
    states = [(r.status, r.attempts) for r in await rows(runtime_engine)]
    assert states == [("sent", 1), ("pending", 0), ("pending", 0)]  # no attempt spent
    now_clock.advance(61)
    await sender.run_once()
    assert len(transport.sent) == 6
    assert {r.status for r in await rows(runtime_engine)} == {"sent"}


async def test_unconfigured_mail_idles_without_errors(runtime_engine, now_clock):
    mailer = AdminMailer(EnvMailConfigProvider({}))
    board = StatusBoard()
    sender = NotificationSender(runtime_engine, now_clock, mailer, lambda: ADMINS, board)
    await enqueue(runtime_engine)
    assert await sender.run_once() == "idle: mail not configured"
    assert board.mail == "mail not configured"
    (row,) = await rows(runtime_engine)
    assert (row.status, row.attempts) == ("pending", 0)


async def test_two_senders_never_mail_the_same_row_twice(runtime_engine, now_clock):
    transport = FakeTransport()
    one, _ = make_sender(runtime_engine, now_clock, transport)
    two, _ = make_sender(runtime_engine, now_clock, transport)
    for _ in range(4):
        await enqueue(runtime_engine)
    await asyncio.gather(one.run_once(), two.run_once())
    assert len(transport.sent) == 8


# ------------------------------------------------------------------ the runner


class CountingLoop(Loop):
    name = "counting"
    lock_number = 41
    interval = 0.05

    def __init__(self):
        self.runs = 0

    async def run_once(self):
        self.runs += 1
        return f"ran {self.runs}"


async def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not reached")


async def lock_free(engine, name) -> bool:
    """Whether nobody holds an unexpired lease on the loop ``name``."""
    async with engine.connect() as conn:
        held = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM admin.loop_leases "
                    "WHERE name = :n AND expires_at > clock_timestamp()"
                ),
                {"n": name},
            )
        ).scalar_one()
        return held == 0


async def test_only_one_runner_runs_a_loop_and_the_other_takes_over(runtime_engine, now_clock):
    a, b = CountingLoop(), CountingLoop()
    one = LoopRunner(runtime_engine, now_clock, [a], standby_retry=0.05)
    two = LoopRunner(runtime_engine, now_clock, [b], standby_retry=0.05)
    await one.start()
    await wait_for(lambda: a.runs > 0)
    await two.start()
    await asyncio.sleep(0.4)
    assert b.runs == 0
    assert one.status()["counting"].leader and not two.status()["counting"].leader
    assert two.status()["counting"].last_outcome == "standby"
    assert not await lock_free(runtime_engine, "counting")
    await one.stop()
    await wait_for(lambda: b.runs > 0)  # idle takeover
    assert two.status()["counting"].leader
    await two.stop()
    assert await lock_free(runtime_engine, "counting")  # released on cancel


async def test_a_failing_loop_is_counted_logged_by_class_and_never_crashes(
    runtime_engine, now_clock, caplog
):
    class Failing(Loop):
        name = "failing"
        lock_number = 42
        interval = 0.02

        async def run_once(self):
            raise ValueError("secret-value admin@example.org " + PLANT)

    caplog.set_level(logging.DEBUG)
    runner = LoopRunner(runtime_engine, now_clock, [Failing()], jitter=lambda: 0)
    await runner.start()
    await wait_for(lambda: runner.status()["failing"].consecutive_failures >= 2)
    status = runner.status()["failing"]
    assert status.last_ok is False and status.last_outcome == "failed: ValueError"
    assert "ValueError" in caplog.text
    assert PLANT not in caplog.text and "admin@example.org" not in caplog.text
    await runner.stop()
    assert await lock_free(runtime_engine, "failing")


async def test_a_loop_survives_database_errors_and_recovers(runtime_engine, now_clock):
    class Flaky(Loop):
        name = "flaky"
        lock_number = 43
        interval = 0.02
        broken = True

        async def run_once(self):
            async with runtime_engine.connect() as conn:
                await conn.execute(text("SELECT * FROM no_such_table" if self.broken else "SELECT 1"))
            return "fine"

    flaky = Flaky()
    runner = LoopRunner(runtime_engine, now_clock, [flaky], jitter=lambda: 0)
    await runner.start()
    await wait_for(lambda: runner.status()["flaky"].consecutive_failures >= 1)
    assert "ProgrammingError" in runner.status()["flaky"].last_outcome
    flaky.broken = False
    await wait_for(lambda: runner.status()["flaky"].last_ok is True, timeout=8)
    assert runner.status()["flaky"].consecutive_failures == 0
    await runner.stop()


def test_loop_numbers_must_be_unique():
    class One(CountingLoop):
        pass

    with pytest.raises(ValueError):
        LoopRunner(None, FakeClock(), [CountingLoop(), One()])


# -------------------------------------------------------- lifespan and modes


async def run_lifespan(app, during):
    async with app.inner.router.lifespan_context(app.inner):
        await during()


def loop_tasks():
    return [t for t in asyncio.all_tasks() if t.get_name().startswith("admin-loop-")]


async def test_skeleton_mode_starts_no_loops():
    app = get_admin_application(GateSettings.from_env({}))
    seen = []

    async def during():
        seen.append(loop_tasks())

    await run_lifespan(app, during)
    assert seen == [[]]


async def test_the_portal_lifespan_starts_the_loops_and_shutdown_cancels_them(
    portal, app, runtime_engine
):
    portal.loop_settings = LoopSettings(notify_interval=1, retention_interval=10, integrity_interval=10)
    seen = []

    async def during():
        await wait_for(lambda: len(loop_tasks()) == 3)
        await wait_for(lambda: all(s.runs > 0 for s in portal.loop_status().values()))
        seen.append(dict(portal.loop_status()))
        assert portal.integrity_status().ok is True
        assert portal.mail_status() in ("ok", "mail not configured")

    await run_lifespan(app, during)
    assert set(seen[0]) == {"notifications", "retention", "integrity"}
    assert loop_tasks() == [] and portal.runner is None
    for name in ("notifications", "retention", "integrity"):
        assert await lock_free(runtime_engine, name)


async def test_the_loops_can_be_switched_off(portal, app):
    portal.loop_settings = LoopSettings(enabled=False)

    async def during():
        assert loop_tasks() == []

    await run_lifespan(app, during)


def test_loop_settings_parse_and_refuse_bad_values():
    assert LoopSettings.from_env({}) == LoopSettings()
    assert LoopSettings.from_env({"ADMIN_LOOPS_ENABLED": "false"}).enabled is False
    for bad in ({"ADMIN_NOTIFY_MAX_PER_MINUTE": "0"}, {"ADMIN_LOOPS_ENABLED": "maybe"}, {"ADMIN_INTEGRITY_INTERVAL_SECONDS": "x1"}):
        with pytest.raises(PortalConfigError):
            LoopSettings.from_env(bad)


# ------------------------------------------------------------------ retention


async def seed_retention(superuser, now):
    day = timedelta(days=1)

    async def run(state, finished):
        rid = uuid.uuid4()
        await as_superuser_raw(
            superuser,
            "INSERT INTO tasks.runs (id, task, version, params, params_hash, dry_run, requested_by, "
            "requested_at, nonce, request_sig, created_at, state, finished_at) "
            "VALUES (:id, 't', 1, '{}'::jsonb, repeat('h', 64), false, 'a', :at, :n, :sig, :at, :st, :fin)",
            id=rid, at=now - 100 * day, n=str(rid), sig=b"x" * 32, st=state, fin=finished,
        )
        return rid

    old_run = await run("succeeded", now - 40 * day)
    recent_run = await run("succeeded", now - 10 * day)
    live_run = await run("running", None)
    seq = 0
    for rid, age in ((old_run, 100), (old_run, 80), (recent_run, 120), (live_run, 91)):
        seq += 1
        await as_superuser_raw(
            superuser,
            "INSERT INTO tasks.run_events (run_id, seq, at, code) VALUES (:r, :s, :at, 'x')",
            r=rid, s=seq, at=now - age * day,
        )
    for rid in (old_run, recent_run, live_run):
        await as_superuser_raw(
            superuser,
            "INSERT INTO tasks.checkpoints (run_id, at, cursor) VALUES (:r, :at, '{}'::jsonb)",
            r=rid, at=now - 200 * day,
        )
    for service, instance, age in (
        ("backend", "stale", 20), ("backend", "fresh", 0),  # a live service: its stale row is report_state's job
        ("ghost", "gone", 30),  # stopped reporting entirely
        ("auth", "fresh", 1),
    ):
        await as_superuser_raw(
            superuser,
            "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied) "
            "VALUES (:s, :i, :at, 1)",
            s=service, i=instance, at=now - age * day,
        )
    # expired and fresh challenges, old and fresh counters
    for age in (10, 0):
        await as_superuser_raw(
            superuser,
            "INSERT INTO admin.signin_challenges (code_hash, created_at, expires_at) VALUES (:h, :at, :at)",
            h=b"h" * 32, at=now - age * day,
        )
    for key, age in (("old", 5), ("new", 0)):
        await as_superuser_raw(
            superuser,
            "INSERT INTO admin.attempts (key, window_start, count) VALUES (:k, :at, 1)",
            k=key, at=now - age * day,
        )


async def test_retention_removes_exactly_what_it_should(
    portal, runtime_engine, superuser, clock
):
    clock.set(time.time())  # the portal's sessions and limiter share this clock
    now_clock = clock
    now = clock.now()
    await seed_retention(superuser, now)
    await put(SettingsService(runtime_engine, store_registry(), make_keys()), T1, 5)
    audit_before = await scalar(superuser, "SELECT count(*) FROM admin.audit_log")
    entries_before = await scalar(superuser, "SELECT count(*) FROM settings.entries")
    history_before = await scalar(superuser, "SELECT count(*) FROM settings.history")
    loop = RetentionLoop(
        runtime_engine, now_clock, portal.sessions.cleanup, portal.limiter.cleanup
    )
    outcome = await loop.run_once()
    assert outcome.startswith("removed: ")

    events = await scalar(superuser, "SELECT array_agg(seq ORDER BY seq) FROM tasks.run_events")
    assert events == [2]  # events older than 90 days went (even of a live run)
    cp = await scalar(superuser, "SELECT count(*) FROM tasks.checkpoints")
    assert cp == 2  # the old finished run's checkpoint went; recent and running stay
    left = await scalar(superuser, "SELECT array_agg(c.run_id::text) FROM tasks.checkpoints c JOIN tasks.runs r ON r.id = c.run_id WHERE r.state = 'succeeded'")
    assert len(left) == 1
    states = await scalar(
        superuser,
        "SELECT array_agg(service || '/' || instance ORDER BY service, instance) FROM settings.service_state",
    )
    assert states == ["auth/fresh", "backend/fresh", "backend/stale"]
    assert await scalar(superuser, "SELECT count(*) FROM admin.signin_challenges") == 1
    assert await scalar(superuser, "SELECT array_agg(key) FROM admin.attempts") == ["new"]
    # never touched
    assert await scalar(superuser, "SELECT count(*) FROM tasks.runs") == 3
    assert await scalar(superuser, "SELECT count(*) FROM admin.audit_log") == audit_before
    assert await scalar(superuser, "SELECT count(*) FROM settings.entries") == entries_before
    assert await scalar(superuser, "SELECT count(*) FROM settings.history") == history_before
    assert await scalar(superuser, "SELECT count(*) FROM settings.manifest") == 1


async def test_retention_work_is_bounded_per_pass(runtime_engine, superuser, now_clock):
    now = now_clock.now()
    rid = uuid.uuid4()
    await as_superuser_raw(
        superuser,
        "INSERT INTO tasks.runs (id, task, version, params, params_hash, dry_run, requested_by, "
        "requested_at, nonce, request_sig, created_at) "
        "VALUES (:id, 't', 1, '{}'::jsonb, repeat('h', 64), false, 'a', :at, 'n', :sig, :at)",
        id=rid, at=now, sig=b"x" * 32,
    )
    for i in range(5):
        await as_superuser_raw(
            superuser,
            "INSERT INTO tasks.run_events (run_id, seq, at, code) VALUES (:r, :s, :at, 'x')",
            r=rid, s=i, at=now - timedelta(days=200),
        )

    async def nothing():
        return 0

    loop = RetentionLoop(runtime_engine, now_clock, nothing, nothing, bound=2)
    await loop.run_once()
    assert await scalar(superuser, "SELECT count(*) FROM tasks.run_events") == 3
    await loop.run_once()
    await loop.run_once()
    assert await scalar(superuser, "SELECT count(*) FROM tasks.run_events") == 0


async def test_one_failing_retention_step_does_not_stop_the_others(
    runtime_engine, superuser, now_clock
):
    now = now_clock.now()
    await seed_retention(superuser, now)

    async def broken():
        raise RuntimeError("boom " + PLANT)

    async def nothing():
        return 0

    loop = RetentionLoop(runtime_engine, now_clock, broken, nothing)
    with pytest.raises(Exception) as caught:
        await loop.run_once()
    assert type(caught.value).__name__ == "StepsFailed" and PLANT not in str(caught.value)
    assert await scalar(superuser, "SELECT count(*) FROM tasks.run_events") == 1  # the rest ran


async def test_the_admin_role_can_delete_only_the_two_task_tables_and_stale_state(
    runtime_engine, superuser, server
):
    role = server.runtime_role

    async def can(table, privilege):
        return await scalar(superuser, "SELECT has_table_privilege(:r, :t, :p)", r=role, t=table, p=privilege)

    deletable = {"tasks.run_events", "tasks.checkpoints"}
    for table in ("runs", "run_events", "checkpoints", "locks"):
        full = f"tasks.{table}"
        assert await can(full, "DELETE") == (full in deletable), full
        assert not await can(full, "TRUNCATE"), full
    for table in ("admin.audit_log", "settings.entries", "settings.manifest", "admin.notifications"):
        assert not await can(table, "DELETE"), table
        assert not await can(table, "TRUNCATE"), table
    assert await can("settings.service_state", "DELETE")
    assert not await can("settings.service_state", "INSERT")
    assert not await can("settings.service_state", "UPDATE")
    # the runner may still only append
    runner_role = server.tasks_role
    assert not await scalar(superuser, "SELECT has_table_privilege(:r, 'tasks.run_events', 'DELETE')", r=runner_role)

    # and the privilege is real, not only a catalogue entry
    for table in ("tasks.runs", "admin.audit_log", "settings.entries", "settings.manifest"):
        with pytest.raises(DBAPIError):
            async with runtime_engine.begin() as conn:
                await conn.execute(text(f"DELETE FROM {table}"))
    async with runtime_engine.begin() as conn:
        await conn.execute(text("DELETE FROM tasks.run_events"))
        await conn.execute(text("DELETE FROM tasks.checkpoints"))
        await conn.execute(text("DELETE FROM settings.service_state"))


async def test_the_roles_script_keeps_the_loop_grants_when_it_runs_again(server, migrated, superuser):
    await _execute(
        server.url(migrated),
        roles_sql(server.suffix, server.admin_pw, server.mig_pw, server.tasks_pw),
    )
    role = server.runtime_role

    async def can(table, privilege):
        return await scalar(superuser, "SELECT has_table_privilege(:r, :t, :p)", r=role, t=table, p=privilege)

    assert await can("tasks.run_events", "DELETE") and await can("tasks.checkpoints", "DELETE")
    assert await can("settings.service_state", "DELETE")
    assert not await can("tasks.locks", "DELETE") and not await can("admin.audit_log", "DELETE")
    for column in ("next_attempt_at", "last_error_code", "delivered_to", "status"):
        assert await scalar(
            superuser,
            "SELECT has_column_privilege(:r, 'admin.notifications', :c, 'UPDATE')",
            r=role, c=column,
        ), column
    for column in ("payload", "kind", "dedupe_key"):
        assert not await scalar(
            superuser,
            "SELECT has_column_privilege(:r, 'admin.notifications', :c, 'UPDATE')",
            r=role, c=column,
        ), column


# ------------------------------------------------------------------ integrity


@pytest_asyncio.fixture(loop_scope="session")
async def store(runtime_engine):
    return SettingsService(runtime_engine, store_registry(), make_keys())


def monitor(engine, clock, store, board=None):
    board = board or StatusBoard()
    return IntegrityMonitor(engine, clock, store.verify, board), board


async def notices(superuser):
    async with superuser.connect() as conn:
        return (
            await conn.execute(
                text("SELECT kind, payload::text AS p, dedupe_key FROM admin.notifications WHERE kind = 'settings.integrity' ORDER BY created_at")
            )
        ).all()


async def test_integrity_monitor_notifies_once_per_incident_and_recovers(
    runtime_engine, superuser, store, now_clock
):
    await put(store, T1, 5)
    mon, board = monitor(runtime_engine, now_clock, store)
    assert await mon.run_once() == "ok"
    assert board.integrity.ok is True and board.integrity.problems == ()

    original = await scalar(superuser, "SELECT value::text FROM settings.entries WHERE key = :k", k=T1)
    await as_superuser_raw(superuser, "UPDATE settings.entries SET value = '12345'::jsonb WHERE key = :k", k=T1)
    assert (await mon.run_once()).endswith("notified")
    assert board.integrity.ok is False
    assert (T1, "bad_signature") in board.integrity.problems
    assert all(isinstance(k, str) and isinstance(r, str) for k, r in board.integrity.problems)
    (notice,) = await notices(superuser)
    assert json.loads(notice.p)["problems"][0] == {"key": T1, "reason": "bad_signature"}
    assert notice.dedupe_key.startswith("integrity:")
    assert "12345" not in notice.p

    # the same problem set within 24 h: no second notice
    now_clock.advance(3600)
    assert (await mon.run_once()).endswith("already notified")
    assert len(await notices(superuser)) == 1
    # a restarted process asks the outbox and stays quiet too
    fresh, _ = monitor(runtime_engine, now_clock, store)
    assert (await fresh.run_once()).endswith("already notified")
    assert len(await notices(superuser)) == 1
    # after 24 h the open problem is mailed again
    now_clock.advance(24 * 3600)
    await mon.run_once()
    assert len(await notices(superuser)) == 2

    # repaired: ok again
    await as_superuser_raw(superuser, "UPDATE settings.entries SET value = CAST(:v AS jsonb) WHERE key = :k", k=T1, v=original)
    assert await mon.run_once() == "ok"
    assert board.integrity.ok is True and board.integrity.problems == ()
    # a recurrence is a new incident
    await as_superuser_raw(superuser, "UPDATE settings.entries SET value = '12345'::jsonb WHERE key = :k", k=T1)
    await mon.run_once()
    assert len(await notices(superuser)) == 3


async def test_integrity_flags_a_store_behind_what_running_services_report(
    runtime_engine, superuser, store, now_clock
):
    """The rollback floor that does not live in a container: a restored backup or a
    replaced database shows a lower manifest revision than the services accepted."""
    await put(store, T1, 5)
    revision = await scalar(superuser, "SELECT revision FROM settings.manifest WHERE id = 1")
    mon, board = monitor(runtime_engine, now_clock, store)
    assert await mon.run_once() == "ok"
    insert = (
        "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied, "
        "env_overrides, rejected_keys, restart_pending, keyset_fp) "
        "VALUES ('backend', :i, :at, :rev, '{}', '{}', false, '')"
    )
    # equal to the store: fine
    await as_superuser_raw(superuser, insert, i="backend:a", at=now_clock.now(), rev=revision)
    assert await mon.run_once() == "ok"
    # a stale report (older than an hour) from before a legitimate restore is not counted
    await as_superuser_raw(
        superuser, insert, i="backend:old", at=now_clock.now() - timedelta(hours=3), rev=revision + 50
    )
    assert await mon.run_once() == "ok"
    # a live instance that accepted a higher revision than the store now shows
    await as_superuser_raw(superuser, insert, i="backend:b", at=now_clock.now(), rev=revision + 3)
    assert (await mon.run_once()).endswith("notified")
    assert ("*", "store_behind_services") in board.integrity.problems
    (notice,) = await notices(superuser)
    assert json.loads(notice.p)["problems"][0] == {"key": "*", "reason": "store_behind_services"}


async def test_the_integrity_notice_renders_and_is_mailed_without_values(
    runtime_engine, superuser, store, now_clock
):
    await put(store, SECRET, PLANT)
    await as_superuser_raw(superuser, "UPDATE settings.entries SET version = version + 5 WHERE key = :k", k=SECRET)
    mon, board = monitor(runtime_engine, now_clock, store)
    await mon.run_once()
    assert board.integrity.ok is False, board.integrity
    transport = FakeTransport()
    sender, _ = make_sender(runtime_engine, now_clock, transport)
    # the settings change notice and the integrity notice both go out
    await sender.run_once()
    integrity = [m for m in transport.sent if "integrity" in m.subject]
    assert len(integrity) == 2
    assert SECRET in integrity[0].body and "bad_signature" in integrity[0].body
    assert PLANT not in "".join(m.body + m.subject for m in transport.sent)


async def test_keys_rejected_by_services_count_as_a_problem(
    runtime_engine, superuser, store, now_clock
):
    await as_superuser_raw(
        superuser,
        "INSERT INTO settings.service_state (service, instance, reported_at, revision_applied, rejected_keys) "
        "VALUES ('backend', 'b1', :at, 1, ARRAY['MAIL_PASSWORD'])",
        at=now_clock.now(),
    )
    mon, board = monitor(runtime_engine, now_clock, store)
    await mon.run_once()
    assert ("MAIL_PASSWORD", "rejected_by_reader") in board.integrity.problems
    await as_superuser_raw(superuser, "DELETE FROM settings.service_state")
    assert await mon.run_once() == "ok"


async def test_a_verify_error_is_a_loop_failure_not_a_green_status(
    runtime_engine, now_clock
):
    async def broken():
        raise RuntimeError("db down")

    board = StatusBoard()
    mon = IntegrityMonitor(runtime_engine, now_clock, broken, board)
    with pytest.raises(RuntimeError):
        await mon.run_once()
    assert board.integrity.ok is None  # never claims ok without a check
