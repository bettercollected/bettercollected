import os
import uuid
from datetime import timedelta

import pytest

from backend.admin.security import ratelimit as rl
from backend.admin.security.clock import FakeClock
from backend.admin.security.ratelimit import (
    AttemptStore,
    Limiter,
    MemoryAttemptStore,
    SqlAttemptStore,
    build_attempts_table,
)

PEPPER = b"p" * 32
# aligned to a 4 h boundary so a test's windows are predictable
T0 = 1_700_006_400.0


def make(store=None):
    clock = FakeClock(T0)
    store = store or MemoryAttemptStore()
    return Limiter(store, clock, PEPPER), clock, store


# ------------------------------------------------------------------ keys


def test_ipv6_clients_share_a_bucket_per_64():
    assert rl.rate_limit_key("2001:db8:1:2:aaaa::1") == rl.rate_limit_key("2001:db8:1:2:bbbb::2")
    assert rl.rate_limit_key("2001:db8:1:3::1") != rl.rate_limit_key("2001:db8:1:2::1")


def test_keys_hide_identifiers_and_depend_on_the_pepper():
    limiter, _, _ = make()
    key = limiter.email_key("  Ann@Example.org ")
    assert key == limiter.email_key("ann@example.org")
    assert "ann" not in key and "example" not in key
    other = Limiter(MemoryAttemptStore(), FakeClock(), b"q" * 32)
    assert other.email_key("ann@example.org") != limiter.email_key("ann@example.org")
    assert "203.0.113.9" not in limiter.ip_key("203.0.113.9")
    assert limiter.email_key("a@b.c") != limiter.ip_key("a@b.c")


# ------------------------------------------------------------ code requests


async def test_code_requests_three_per_email_and_address_per_ten_minutes():
    limiter, clock, _ = make()
    for _ in range(3):
        assert (await limiter.request_code("ann@example.org", "203.0.113.1")).allowed
    d = await limiter.request_code("ANN@example.org", "203.0.113.1")
    assert not d.allowed and 0 < d.retry_after <= 600 and not d.blocked_by_ip
    # another address is not affected by the first one's requests
    assert (await limiter.request_code("ann@example.org", "203.0.113.2")).allowed
    assert (await limiter.request_code("bob@example.org", "203.0.113.1")).allowed
    clock.advance(600)
    assert (await limiter.request_code("ann@example.org", "203.0.113.1")).allowed


async def test_code_requests_have_a_higher_ceiling_per_email_over_all_addresses():
    limiter, clock, _ = make()
    for n in range(12):
        assert (await limiter.request_code("ann@example.org", f"203.0.113.{n}")).allowed
    d = await limiter.request_code("ann@example.org", "203.0.113.99")
    assert not d.allowed and not d.blocked_by_ip
    clock.advance(600)
    assert (await limiter.request_code("ann@example.org", "203.0.113.99")).allowed


async def test_shared_address_is_not_one_global_bucket_for_every_email():
    limiter, _, _ = make()
    limiter.set_shared_clients(["172.30.77.1"])
    for n in range(40):  # far past the 10 an ordinary address gets
        assert (await limiter.request_code(f"u{n}@example.net", "172.30.77.1")).allowed
    # the genuine admin still gets a code after noise from other emails
    assert (await limiter.request_code("admin@example.org", "172.30.77.1")).allowed
    # a flood guard still caps the total work from the shared address
    for n in range(200):
        await limiter.request_code(f"v{n}@example.net", "172.30.77.1")
    d = await limiter.request_code("w@example.net", "172.30.77.1")
    assert not d.allowed and d.blocked_by_ip
    # an ordinary address keeps the strict per-address limit
    for n in range(10):
        assert (await limiter.request_code(f"x{n}@example.net", "198.51.100.1")).allowed
    assert (await limiter.request_code("x99@example.net", "198.51.100.1")).blocked_by_ip


async def test_signin_scope_counts_and_locks_do_not_touch_the_factor_lock():
    limiter, _, _ = make()
    pair = limiter.pair_subject("ann@example.org", "203.0.113.1")
    for _ in range(5):
        outcome = await limiter.record_failure(pair, "signin")
    assert outcome.newly_locked is False or outcome.locked
    assert (await limiter.lock_status(pair, "signin")).locked
    assert not (await limiter.lock_status("ann@example.org")).locked  # factor scope
    other = limiter.pair_subject("ann@example.org", "203.0.113.2")
    assert not (await limiter.lock_status(other, "signin")).locked


async def test_email_ceiling_is_an_alert_not_a_lock():
    limiter, _, _ = make()
    last = None
    for _ in range(31):
        last = await limiter.email_ceiling("ann@example.org")
    assert last.count == 31 and not (await limiter.lock_status("ann@example.org")).locked


async def test_code_requests_ten_per_ip_per_ten_minutes():
    limiter, clock, _ = make()
    for n in range(10):
        assert (await limiter.request_code(f"u{n}@example.org", "198.51.100.1")).allowed
    d = await limiter.request_code("u99@example.org", "198.51.100.1")
    assert not d.allowed
    assert (await limiter.request_code("u99@example.org", "198.51.100.2")).allowed
    clock.advance(600)
    assert (await limiter.request_code("u99@example.org", "198.51.100.1")).allowed


async def test_ipv6_rotation_inside_a_64_does_not_multiply_the_ip_limit():
    limiter, _, _ = make()
    for n in range(10):
        await limiter.request_code(f"u{n}@example.org", f"2001:db8:9:9::{n + 1}")
    d = await limiter.request_code("z@example.org", "2001:db8:9:9:ffff::1")
    assert not d.allowed


# --------------------------------------------------------------- challenge


async def test_challenge_allows_five_guesses_then_refuses():
    limiter, clock, _ = make()
    expires = clock.now() + timedelta(minutes=10)
    results = [await limiter.challenge_attempt("c1", expires) for _ in range(6)]
    assert [r.allowed for r in results] == [True] * 5 + [False]
    assert results[-1].retry_after > 0
    assert (await limiter.challenge_attempt("c2", expires)).allowed
    clock.advance(1200)  # no window boundary can reset a live challenge's tally
    assert not (await limiter.challenge_attempt("c1", expires)).allowed


# --------------------------------------------------- failures and lockout


async def fail_times(limiter, who, n):
    """The outcome that locked, else the last one."""
    out = None
    for _ in range(n):
        out = await limiter.record_failure(who)
        if out.newly_locked:
            return out
    return out


async def test_four_failures_do_not_lock_the_fifth_does():
    limiter, _, _ = make()
    out = await fail_times(limiter, "ann@example.org", 4)
    assert not out.locked
    assert not (await limiter.lock_status("ann@example.org")).locked
    out = await limiter.record_failure("ann@example.org")
    assert out.locked and out.newly_locked and out.level == 1
    assert out.retry_after == 900
    assert (await limiter.lock_status("ANN@example.org")).locked


async def test_failures_spread_over_more_than_five_minutes_do_not_lock():
    limiter, clock, _ = make()
    await fail_times(limiter, "ann@example.org", 4)
    clock.advance(300)
    out = await fail_times(limiter, "ann@example.org", 4)
    assert not out.locked


async def test_lockout_expires_and_escalates_15m_1h_4h_and_stays_at_4h():
    limiter, clock, _ = make()
    who = "ann@example.org"
    for expected in (900, 3600, 14400, 14400):
        out = await fail_times(limiter, who, 5)
        assert out.newly_locked and out.retry_after == expected
        clock.advance(expected - 1)
        assert (await limiter.lock_status(who)).locked
        clock.advance(2)
        assert not (await limiter.lock_status(who)).locked
        clock.advance(300)  # let the failure window roll


async def test_extra_failures_while_locked_do_not_escalate_or_renotify():
    limiter, _, _ = make()
    who = "ann@example.org"
    await fail_times(limiter, who, 5)
    out = await limiter.record_failure(who)
    assert out.locked and not out.newly_locked and out.retry_after > 0


async def test_success_resets_failures_and_escalation():
    limiter, clock, _ = make()
    who = "ann@example.org"
    await fail_times(limiter, who, 5)  # level 1
    clock.advance(901)
    await fail_times(limiter, who, 2)
    await limiter.record_success(who)
    out = await fail_times(limiter, who, 4)
    assert not out.locked  # counter restarted
    out = await limiter.record_failure(who)
    assert (
        out.locked and out.level == 1 and out.retry_after == 900
    )  # escalation restarted


async def test_lockouts_are_per_subject():
    limiter, _, _ = make()
    await fail_times(limiter, "ann@example.org", 5)
    assert not (await limiter.lock_status("bob@example.org")).locked


async def test_unlock_clears_everything():
    limiter, _, _ = make()
    who = "ann@example.org"
    await fail_times(limiter, who, 5)
    await limiter.unlock(who)
    assert not (await limiter.lock_status(who)).locked
    out = await limiter.record_failure(who)
    assert not out.locked


# --------------------------------------------------------- global breaker


async def trip(limiter, n=50):
    """n failures of identified admins from distinct addresses."""
    out = None
    for i in range(n):
        out = await limiter.record_global_failure(
            f"203.0.{i // 200}.{i % 200 + 1}", True
        )
    return out


async def test_global_breaker_trips_at_fifty_pauses_ten_minutes_and_notifies_once():
    limiter, clock, _ = make()
    outcomes = [
        await limiter.record_global_failure(f"203.0.113.{i + 1}", True)
        for i in range(49)
    ]
    assert not any(o.paused for o in outcomes)
    assert not (await limiter.sign_in_pause()).paused
    tripped = await limiter.record_global_failure("203.0.114.1", True)
    assert tripped.paused and tripped.newly_tripped and tripped.retry_after == 600
    again = await limiter.record_global_failure("203.0.114.2", True)
    assert again.paused and not again.newly_tripped
    assert (await limiter.sign_in_pause()).paused
    clock.advance(599)
    assert (await limiter.sign_in_pause()).paused
    clock.advance(2)
    assert not (await limiter.sign_in_pause()).paused  # lifts by itself


async def test_one_address_cannot_trip_the_breaker():
    limiter, _, _ = make()
    for _ in range(5000):
        out = await limiter.record_global_failure("198.51.100.7", True)
    assert not out.paused and not (await limiter.sign_in_pause()).paused
    # not even by rotating through its /64
    for n in range(5000):
        await limiter.record_global_failure(f"2001:db8:5:5::{n + 1}", True)
    assert not (await limiter.sign_in_pause()).paused


async def test_failures_of_non_admin_emails_never_count():
    limiter, _, _ = make()
    for i in range(5000):
        out = await limiter.record_global_failure(
            f"203.0.{i % 200}.{i % 250 + 1}", False
        )
    assert not out.paused and not (await limiter.sign_in_pause()).paused


async def test_the_pause_is_not_extended_by_more_failures_and_ends_on_time():
    limiter, clock, _ = make()
    await trip(limiter)
    for step in range(5):
        clock.advance(100)
        out = await limiter.record_global_failure(f"192.0.2.{step + 1}", True)
        assert out.paused and not out.newly_tripped
    clock.advance(101)  # 601 s after the trip
    assert not (await limiter.sign_in_pause()).paused


async def test_global_breaker_failures_must_fall_in_one_window():
    limiter, clock, _ = make()
    for i in range(40):
        await limiter.record_global_failure(f"203.0.113.{i + 1}", True)
    clock.advance(600)
    for i in range(40):
        out = await limiter.record_global_failure(f"203.0.114.{i + 1}", True)
    assert not out.paused


async def test_resume_sign_in_clears_the_pause():
    limiter, _, _ = make()
    await trip(limiter)
    assert (await limiter.sign_in_pause()).paused
    await limiter.resume_sign_in()
    assert not (await limiter.sign_in_pause()).paused


async def test_operator_hooks_reach_the_same_rows():
    limiter, clock, store = make()
    await trip(limiter)
    await fail_times(limiter, "ann@example.org", 5)
    await rl.operator_resume(store, clock, PEPPER)
    await rl.operator_unlock(store, clock, PEPPER, "Ann@Example.org")
    assert not (await limiter.sign_in_pause()).paused
    assert not (await limiter.lock_status("ann@example.org")).locked
    out = await fail_times(limiter, "ann@example.org", 4)
    assert not out.locked  # tallies are gone as well


# --------------------------------------------- slow guessing (rolling 24 h)


async def test_slow_guessing_under_the_short_rule_still_locks():
    limiter, clock, _ = make()
    who = "ann@example.org"
    out = None
    for round_ in range(4):  # 4 failures per 5-minute window: 16 in about 20 minutes
        out = await fail_times(limiter, who, 4)
        if out.locked:
            break
        clock.advance(300)
    assert out.locked and out.newly_locked and out.level == 1


async def test_four_guesses_every_five_minutes_around_the_clock_locks_within_a_day():
    limiter, clock, _ = make()
    who = "ann@example.org"
    locked_after = None
    for window in range(288):  # a day of 5-minute windows
        out = await fail_times(limiter, who, 4)
        if out.locked:
            locked_after = window
            break
        clock.advance(300)
    assert locked_after is not None and locked_after < 5


async def test_the_long_window_is_rolling_not_aligned_to_midnight():
    # start 10 minutes before a UTC midnight
    midnight = (int(T0) // 86400 + 1) * 86400
    limiter, clock, _ = make()
    clock.set(midnight - 600)
    who = "ann@example.org"
    await fail_times(limiter, who, 4)
    clock.advance(1200)  # now 10 minutes after midnight
    await fail_times(limiter, who, 4)
    clock.advance(1200)
    await fail_times(limiter, who, 4)
    clock.advance(1200)
    out = await fail_times(limiter, who, 3)
    assert out.locked  # 15 failures across midnight, in under 2 hours


async def test_failures_older_than_a_day_stop_counting():
    limiter, clock, _ = make()
    who = "ann@example.org"
    for _ in range(14 // 4):
        await fail_times(limiter, who, 4)
        clock.advance(300)
    await fail_times(limiter, who, 2)  # 14 so far
    clock.advance(86400 + 900)
    out = await fail_times(limiter, who, 4)
    assert not out.locked


async def test_the_long_tally_restarts_after_it_locks_and_escalates():
    limiter, clock, _ = make()
    who = "ann@example.org"

    async def burn():
        for _ in range(4):
            out = await fail_times(limiter, who, 4)
            if out.locked:
                return out
            clock.advance(300)
        return out

    first = await burn()
    assert first.level == 1
    clock.advance(901)
    second = await burn()
    assert second.locked and second.level == 2 and second.retry_after == 3600


async def test_success_does_not_wipe_the_rolling_tally_nor_an_active_lock():
    limiter, clock, _ = make()
    who = "ann@example.org"
    for _ in range(3):
        await fail_times(limiter, who, 4)
        await limiter.record_success(who)  # short counter reset each time
        clock.advance(300)
    out = await fail_times(limiter, who, 4)
    assert out.locked  # 16 failures in the day despite the successes
    await limiter.record_success(who)
    assert (await limiter.lock_status(who)).locked


def test_short_limiter_keys_are_refused_without_echoing_them():
    from backend.admin.security.keycheck import WeakKeyError

    with pytest.raises(WeakKeyError) as raised:
        Limiter(MemoryAttemptStore(), FakeClock(), b"short-pepper")
    assert "short-pepper" not in str(raised.value)


async def test_cleanup_removes_old_counters_only():
    limiter, clock, store = make()
    await limiter.request_code("ann@example.org", "203.0.113.1")
    clock.advance(3 * 86400)
    await limiter.request_code("bob@example.org", "203.0.113.2")
    removed = await limiter.cleanup()
    assert removed == 3  # address, (email, address) and email counters of the first request
    assert len(store.rows) == 3


async def test_memory_store_satisfies_the_protocol():
    assert isinstance(MemoryAttemptStore(), AttemptStore)


# ------------------------------------------------------------- PostgreSQL


@pytest.fixture
async def pg_store():
    url = os.environ.get("DATABASE_URL", "")
    name = url.rsplit("/", 1)[-1].split("?")[0]
    if not url or "test" not in name:
        pytest.skip("DATABASE_URL not set to a *_test database")
    from sqlalchemy import MetaData, text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(url, poolclass=NullPool)
    schema = f"attempts_{uuid.uuid4().hex[:10]}"
    try:
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"test database not reachable: {type(exc).__name__}")
    table = build_attempts_table(MetaData(), schema=schema)
    async with engine.begin() as conn:
        await conn.run_sync(table.metadata.create_all)
    try:
        yield SqlAttemptStore(engine, table)
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await engine.dispose()


async def test_sql_store_contract(pg_store):
    from datetime import datetime, timezone

    assert isinstance(pg_store, AttemptStore)
    w1 = datetime.fromtimestamp(T0, timezone.utc)
    w2 = datetime.fromtimestamp(T0 + 600, timezone.utc)
    assert await pg_store.count("k", w1) == 0
    assert [await pg_store.increment("k", w1) for _ in range(3)] == [1, 2, 3]
    assert await pg_store.increment("k", w2) == 1
    assert await pg_store.increment("other", w1) == 1
    assert await pg_store.count("k", w1) == 3
    assert await pg_store.latest_window("k") == w2
    assert await pg_store.latest_window("missing") is None
    assert await pg_store.cleanup(w2) == 2  # k@w1 and other@w1
    assert await pg_store.count("k", w1) == 0
    await pg_store.reset("k")
    assert await pg_store.latest_window("k") is None


async def test_sql_increments_are_atomic_under_concurrency(pg_store):
    import asyncio
    from datetime import datetime, timezone

    w = datetime.fromtimestamp(T0, timezone.utc)
    counts = await asyncio.gather(*[pg_store.increment("race", w) for _ in range(20)])
    assert sorted(counts) == list(range(1, 21))


async def test_limiter_runs_on_the_sql_store(pg_store):
    limiter, clock, _ = make(pg_store)
    for _ in range(4):
        d = await limiter.request_code("ann@example.org", "203.0.113.1")
    assert not d.allowed
    out = await fail_times(limiter, "ann@example.org", 5)
    assert out.locked and out.level == 1
    assert (await limiter.lock_status("ann@example.org")).locked
    clock.advance(901)
    assert not (await limiter.lock_status("ann@example.org")).locked
    await limiter.record_success("ann@example.org")
