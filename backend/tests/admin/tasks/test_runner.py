"""The runner end to end on real Postgres: claim, verify, gate, lock, run, finish."""

from __future__ import annotations

import asyncio
import enum
import json

from datetime import timedelta

import pytest
from sqlalchemy import text

from backend.admin.services import audit
from backend.admin.tasks.impl import selftest_slow as slow_impl
from backend.admin.tasks.registry import Registry
from backend.admin.tasks.spec import Params, Result, TaskMeta
from tests.admin.conftest import needs_postgres

pytestmark = needs_postgres

SLOW = {"items": 20, "batch_size": 5}


class Gate:
    """Hold a slow run between batches until the test lets it go."""

    def __init__(self, at_batch: int = 0):
        self.at_batch = at_batch
        self.reached = asyncio.Event()
        self.release = asyncio.Event()

    async def before_batch(self, ctx, index):
        if index == self.at_batch:
            self.reached.set()
            await self.release.wait()


def install(gate: Gate):
    slow_impl.HOOKS.before_batch = gate.before_batch


async def start(world, runner, run_id=None):
    """Claim and execute in the background; returns the asyncio task."""
    claimed = await runner.claim()
    assert claimed is not None
    row, registered = claimed
    return row, asyncio.create_task(runner.execute(row, registered))


# -- happy path, audit, idempotency ---------------------------------------------------
async def test_selftest_runs_and_is_audited_as_system(world):
    run_id = await world.enqueue("selftest", {"rounds": 3}, requested_by="ops@example.org")
    assert await world.drain() == 1
    run = await world.run(run_id)
    assert run["state"] == "succeeded"
    assert run["result"] == {"ok": True, "checked": 3}
    assert run["progress"] == {"done": 3, "total": 3}
    assert run["runner_id"].startswith("runner-") and run["finished_at"] and run["started_at"]
    assert [e["code"] for e in await world.events(run_id)] == ["checked"] * 3
    assert await world.locks() == []

    started = await world.audit_rows("task.run.started")
    finished = await world.audit_rows("task.run.finished")
    assert len(started) == 1 and len(finished) == 1
    for row in (started[0], finished[0]):
        assert row["actor_kind"] == "system" and row["actor_email"] is None
        assert row["target_type"] == "task_run" and row["target_id"] == str(run_id)
        assert row["detail"]["requested_by"] == "ops@example.org"
        assert row["detail"]["task"] == "selftest"
    assert finished[0]["outcome"] == "success" and finished[0]["detail"]["state"] == "succeeded"
    async with world.owner.connect() as conn:
        assert (await audit.verify_chain(conn, None, None)).ok


async def test_idempotency_harness(world):
    """Run twice: the read-only task gives the same result, the mutating one's
    second run is a no-op."""
    for _ in range(2):
        await world.enqueue("selftest", {"rounds": 2})
    await world.drain()
    first, second = [
        r["result"]
        for r in [await world.run(i) for i in await _ids(world, "selftest")]
    ]
    assert first == second

    a = await world.enqueue("selftest_slow", SLOW)
    b = await world.enqueue("selftest_slow", SLOW)
    await world.drain()
    assert (await world.run(a))["result"] == {"changed": 20, "unchanged": 0, "batches": 4}
    assert (await world.run(b))["result"] == {"changed": 0, "unchanged": 20, "batches": 4}


async def _ids(world, task):
    async with world.owner.connect() as conn:
        rows = await conn.execute(
            text("SELECT id FROM tasks.runs WHERE task = :t ORDER BY created_at, id"), {"t": task}
        )
        return list(rows.scalars())


async def test_runs_are_taken_oldest_first_one_at_a_time(world):
    ids = [await world.enqueue("selftest", {"rounds": i}) for i in range(3)]
    runner = world.runner()
    for expected in ids:
        claimed = await runner.claim()
        assert claimed[0]["id"] == expected
        await runner.execute(*claimed)
    assert await runner.claim() is None


async def test_two_runners_never_claim_the_same_run(world):
    for _ in range(3):
        await world.enqueue("selftest", {})
    claims = await asyncio.gather(*(world.runner().claim() for _ in range(6)))
    got = [c[0]["id"] for c in claims if c]
    assert len(got) == 3 and len(set(got)) == 3


# -- verification ---------------------------------------------------------------------
async def test_a_bad_signature_is_refused_and_never_executes(world):
    forged = await world.enqueue("selftest_slow", SLOW, tamper={"sig": b"\x00" * 32})
    assert await world.drain() == 0  # claim() ended it itself
    run = await world.run(forged)
    assert run["state"] == "refused" and run["refusal_code"] == "bad_signature"
    assert run["started_at"] is None and run["runner_id"] is None
    assert slow_impl.WORLD == set()
    assert await world.events(forged) == []
    assert await world.audit_rows("task.run.started") == []
    (finished,) = await world.audit_rows("task.run.finished")
    assert finished["outcome"] == "denied" and finished["detail"]["reason"] == "bad_signature"


@pytest.mark.parametrize(
    "tamper",
    [
        {"task": "selftest"},  # signed for selftest_slow
        {"requested_by": "intruder@example.org"},
        {"dry_run": True},
        {"nonce": "different"},
        {"version": 1, "params_hash": "1" * 64},
    ],
)
async def test_any_tampered_column_is_refused(world, tamper):
    run_id = await world.enqueue("selftest_slow", SLOW, tamper=tamper)
    await world.drain()
    run = await world.run(run_id)
    assert run["state"] == "refused" and run["refusal_code"] == "bad_signature"
    assert slow_impl.WORLD == set()


async def test_params_edited_after_signing_are_refused(world):
    run_id = await world.enqueue(
        "selftest_slow", {"items": 1000}, sign_params={"items": 1}
    )
    await world.drain()
    assert (await world.run(run_id))["refusal_code"] == "bad_signature"
    assert slow_impl.WORLD == set()


async def test_a_resume_pointer_grafted_after_signing_is_refused(world):
    victim = await world.enqueue("selftest_slow", SLOW)
    await world.drain()
    forged = await world.enqueue("selftest_slow", SLOW, tamper={"resumes": victim})
    await world.drain()
    assert (await world.run(forged))["refusal_code"] == "bad_signature"


async def test_version_mismatch_unknown_task_and_bad_params_are_refused(world):
    newer = await world.enqueue("selftest", {}, version=2)
    unknown = await world.enqueue("no_such_task", {})
    extra = await world.enqueue("selftest", {"surprise": 1})
    await world.drain()
    assert (await world.run(newer))["refusal_code"] == "version_mismatch"
    assert (await world.run(unknown))["refusal_code"] == "unknown_task"
    assert (await world.run(extra))["refusal_code"] == "bad_params"
    assert await world.audit_rows("task.run.started") == []


async def test_a_precheck_refusal_ends_refused_with_its_code(world):
    run_id = await world.enqueue("selftest_slow", {**SLOW, "decline": True})
    await world.drain()
    run = await world.run(run_id)
    assert run["state"] == "refused" and run["refusal_code"] == "declined"
    assert slow_impl.WORLD == set() and await world.locks() == []
    started = await world.audit_rows("task.run.started")
    finished = await world.audit_rows("task.run.finished")
    assert len(started) == 1 and finished[0]["outcome"] == "denied"


# -- locks, leases, takeover ----------------------------------------------------------
async def test_a_second_mutating_run_is_refused_while_one_holds_the_locks(world):
    gate = Gate()
    install(gate)
    first = await world.enqueue("selftest_slow", SLOW)
    runner_a = world.runner(runner_id="runner-a")
    _, task_a = await start(world, runner_a)
    await asyncio.wait_for(gate.reached.wait(), 60)
    assert await world.locks() == ["mutating:global", "selftest_resource", "task:selftest_slow"]

    same_task = await world.enqueue("selftest_slow", SLOW)
    other_mutating = await world.enqueue("selftest_guarded", SLOW, dry_run=True)
    read_only = await world.enqueue("selftest", {})
    runner_b = world.runner(runner_id="runner-b")
    await world.drain(runner_b)
    assert (await world.run(same_task))["refusal_code"] == "lock_held"
    # a dry run of a mutating task still takes the global lock
    assert (await world.run(other_mutating))["refusal_code"] == "lock_held"
    # read-only tasks are not serialised behind it
    assert (await world.run(read_only))["state"] == "succeeded"
    assert (await world.run(first))["state"] == "running"

    gate.release.set()
    assert await task_a == "succeeded"
    assert await world.locks() == []


async def test_lease_heartbeat_and_takeover_with_a_fake_clock(world):
    gate = Gate()
    install(gate)
    run_id = await world.enqueue("selftest_slow", SLOW)
    old = world.runner(runner_id="runner-old")
    row, task = await start(world, old)
    await asyncio.wait_for(gate.reached.wait(), 60)

    taker = world.runner(runner_id="runner-new")
    world.clock.advance(89)  # lease 60 + grace 30: not yet
    assert await taker.takeover_stale() == 0
    assert await old.beat(run_id) is True  # renewed at t+89
    world.clock.advance(89)
    assert await taker.takeover_stale() == 0
    world.clock.advance(2)  # 91 s since the last beat
    assert await taker.takeover_stale() == 1
    assert await taker.takeover_stale() == 0  # once

    run = await world.run(run_id)
    assert run["state"] == "interrupted" and run["finished_at"] is not None
    assert await world.locks() == []
    assert [e["code"] for e in await world.events(run_id)][-1] == "interrupted"
    (finished,) = await world.audit_rows("task.run.finished")
    assert finished["outcome"] == "failure"
    assert finished["detail"]["reason"] == "lease_expired"
    assert finished["detail"]["taken_over_by"] == "runner-new"
    assert await old.beat(run_id) is False  # the old runner learns it lost the run

    # the old runner finishing late must not overwrite the takeover
    gate.release.set()
    assert await task == "interrupted"
    assert (await world.run(run_id))["state"] == "interrupted"
    assert (await world.run(run_id))["result"] is None

    # and the locks are free again
    again = await world.enqueue("selftest_slow", SLOW)
    await world.drain(taker)
    assert (await world.run(again))["state"] == "succeeded"


async def test_heartbeat_task_renews_the_lease_and_detects_loss(world):
    gate = Gate()
    install(gate)
    run_id = await world.enqueue("selftest_slow", SLOW)
    runner = world.runner(runner_id="runner-hb", heartbeat_seconds=0.05)
    row, task = await start(world, runner)
    await asyncio.wait_for(gate.reached.wait(), 60)
    before = (await world.run(run_id))["heartbeat_at"]
    world.clock.advance(5)
    for _ in range(200):  # generous: the database may be busy
        await asyncio.sleep(0.1)
        if (await world.run(run_id))["heartbeat_at"] > before:
            break
    assert (await world.run(run_id))["heartbeat_at"] > before
    world.clock.advance(200)
    for _ in range(200):  # the heartbeat keeps the lease fresh at the new time
        await asyncio.sleep(0.1)
        if await world.runner().takeover_stale() == 0 and (
            (await world.run(run_id))["heartbeat_at"] >= world.clock.now() - timedelta(seconds=1)
        ):
            break
    assert await world.runner().takeover_stale() == 0
    gate.release.set()
    assert await task == "succeeded"


async def test_orphan_locks_of_finished_runs_are_cleaned(world):
    run_id = await world.enqueue("selftest_slow", SLOW)
    await world.drain()
    async with world.tasks.begin() as conn:
        await conn.execute(
            text("INSERT INTO tasks.locks (name, run_id, runner_id) VALUES ('task:selftest_slow', :id, 'dead')"),
            {"id": run_id},
        )
    again = await world.enqueue("selftest_slow", SLOW)
    await world.drain()
    assert (await world.run(again))["state"] == "succeeded"


# -- cancel -----------------------------------------------------------------------------
async def test_cancel_while_queued(world):
    run_id = await world.enqueue("selftest_slow", SLOW)
    await world.cancel(run_id)
    await world.drain()
    run = await world.run(run_id)
    assert run["state"] == "cancelled" and run["started_at"] is None
    assert slow_impl.WORLD == set()


async def test_cooperative_cancel_between_batches(world):
    gate = Gate(at_batch=2)
    install(gate)
    run_id = await world.enqueue("selftest_slow", SLOW)
    row, task = await start(world, world.runner())
    await asyncio.wait_for(gate.reached.wait(), 60)
    await world.cancel(run_id)
    gate.release.set()
    assert await task == "cancelled"
    run = await world.run(run_id)
    assert run["state"] == "cancelled"
    # the cancel arrives during batch 2 and is seen before batch 3
    assert run["result"] == {"changed": 15, "unchanged": 0, "batches": 3}
    assert slow_impl.WORLD == set(range(15))
    assert await world.locks() == []
    assert [e["code"] for e in await world.events(run_id)][-1] == "cancelled"
    (finished,) = await world.audit_rows("task.run.finished")
    assert finished["outcome"] == "success" and finished["detail"]["state"] == "cancelled"


async def test_shutdown_interrupts_a_run_so_it_can_be_resumed(world):
    gate = Gate(at_batch=1)
    install(gate)
    run_id = await world.enqueue("selftest_slow", SLOW)
    runner = world.runner()
    row, task = await start(world, runner)
    await asyncio.wait_for(gate.reached.wait(), 60)
    runner.stopping = True
    gate.release.set()
    assert await task == "interrupted"
    assert (await world.run(run_id))["state"] == "interrupted"


# -- resume -------------------------------------------------------------------------------
async def test_resume_continues_from_the_checkpoint(world):
    gate = Gate(at_batch=2)
    install(gate)
    first = await world.enqueue("selftest_slow", SLOW)
    row, task = await start(world, world.runner())
    await asyncio.wait_for(gate.reached.wait(), 60)
    await world.cancel(first)
    gate.release.set()
    assert await task == "cancelled"

    second = await world.enqueue("selftest_slow", SLOW, resumes=first)
    await world.drain()
    run = await world.run(second)
    assert run["state"] == "succeeded", run
    assert run["result"] == {"changed": 5, "unchanged": 0, "batches": 1}
    assert slow_impl.WORLD == set(range(20))


async def test_resume_rules(world):
    done = await world.enqueue("selftest_slow", SLOW)
    await world.drain()

    gate = Gate(at_batch=1)
    install(gate)
    base = await world.enqueue("selftest_slow", {"items": 15, "batch_size": 5})
    row, task = await start(world, world.runner())
    await asyncio.wait_for(gate.reached.wait(), 60)
    await world.cancel(base)
    gate.release.set()
    await task
    slow_impl.HOOKS.__dict__.clear()

    different_params = await world.enqueue(
        "selftest_slow", {"items": 16, "batch_size": 5}, resumes=base
    )
    after_success = await world.enqueue("selftest_slow", SLOW, resumes=done)
    not_resumable = await world.enqueue("selftest_guarded", SLOW, dry_run=True, resumes=base)
    other_task = await world.enqueue("selftest", {}, resumes=base)
    await world.drain()
    assert (await world.run(different_params))["refusal_code"] == "resume_mismatch"
    assert (await world.run(after_success))["refusal_code"] == "resume_mismatch"
    assert (await world.run(not_resumable))["refusal_code"] == "not_resumable"
    assert (await world.run(other_task))["refusal_code"] == "not_resumable"

    ok = await world.enqueue("selftest_slow", {"items": 15, "batch_size": 5}, resumes=base)
    await world.drain()
    assert (await world.run(ok))["state"] == "succeeded"


async def test_resume_needs_the_same_keyset_fingerprint(world):
    gate = Gate(at_batch=1)
    install(gate)
    base = await world.enqueue("selftest_slow", SLOW)
    runner = world.runner()
    claimed = await runner.claim()
    row, registered = claimed
    impl = registered.impl
    original = impl.precheck

    async def with_fingerprint(ctx, params):
        async def fp():
            return "keyset-A"

        ctx.fingerprint = fp
        await original(ctx, params)

    impl.precheck = with_fingerprint
    try:
        task = asyncio.create_task(runner.execute(row, registered))
        await asyncio.wait_for(gate.reached.wait(), 60)
        await world.cancel(base)
        gate.release.set()
        await task
        slow_impl.HOOKS.__dict__.clear()

        async def changed(ctx, params):
            async def fp():
                return "keyset-B"

            ctx.fingerprint = fp

        impl.precheck = changed
        bad = await world.enqueue("selftest_slow", SLOW, resumes=base)
        await world.drain()
        assert (await world.run(bad))["refusal_code"] == "resume_mismatch"

        impl.precheck = with_fingerprint
        good = await world.enqueue("selftest_slow", SLOW, resumes=base)
        await world.drain()
        assert (await world.run(good))["state"] == "succeeded"
    finally:
        del impl.precheck


# -- dry run requirement ---------------------------------------------------------------------
async def _later(world, seconds=1):
    """A request time after everything that has finished so far."""
    world.clock.advance(seconds)
    return world.clock.now()


async def test_requires_prior_dry_run(world):
    params = {"items": 5, "batch_size": 5}
    real = await world.enqueue("selftest_guarded", params)
    await world.drain()
    assert (await world.run(real))["refusal_code"] == "dry_run_required"

    dry = await world.enqueue("selftest_guarded", params, dry_run=True, requested_at=await _later(world))
    await world.drain()
    assert (await world.run(dry))["state"] == "succeeded"
    assert slow_impl.WORLD == set()  # a dry run changes nothing

    other_params = await world.enqueue(
        "selftest_guarded", {"items": 6, "batch_size": 5}, requested_at=await _later(world)
    )
    await world.drain()
    assert (await world.run(other_params))["refusal_code"] == "dry_run_required"

    allowed = await world.enqueue("selftest_guarded", params, requested_at=await _later(world))
    await world.drain()
    assert (await world.run(allowed))["state"] == "succeeded"
    assert slow_impl.WORLD == set(range(5))

    world.clock.advance(24 * 3600 + 1)
    stale = await world.enqueue("selftest_guarded", params, requested_at=await _later(world))
    await world.drain()
    assert (await world.run(stale))["refusal_code"] == "dry_run_required"


async def test_a_dry_run_queued_back_to_back_with_the_apply_does_not_count(world):
    """The apply must be requested after the dry run finished, so someone could
    have seen its result. Both queued together (or double-submitted): refused."""
    params = {"items": 5, "batch_size": 5}
    t0 = world.clock.now()
    dry = await world.enqueue("selftest_guarded", params, dry_run=True, requested_at=t0)
    apply_ = await world.enqueue(
        "selftest_guarded", params, requested_at=t0 + timedelta(seconds=1)
    )
    world.clock.advance(5)  # the runner gets to them a few seconds later
    await world.drain()
    assert (await world.run(dry))["state"] == "succeeded"
    assert (await world.run(apply_))["refusal_code"] == "dry_run_required"
    assert slow_impl.WORLD == set()


async def test_a_dry_run_finished_before_the_request_counts_even_if_run_later(world):
    params = {"items": 5, "batch_size": 5}
    dry = await world.enqueue("selftest_guarded", params, dry_run=True)
    await world.drain()
    assert (await world.run(dry))["state"] == "succeeded"
    apply_ = await world.enqueue("selftest_guarded", params, requested_at=await _later(world, 30))
    world.clock.advance(2 * 3600)  # the runner was stopped for a while
    await world.drain()
    assert (await world.run(apply_))["state"] == "succeeded"
    assert slow_impl.WORLD == set(range(5))


async def test_a_stale_request_is_refused_as_expired(world):
    old = await world.enqueue("selftest", {})
    world.clock.advance(24 * 3600 + 1)
    fresh = await world.enqueue("selftest", {}, requested_at=world.clock.now())
    await world.drain()
    assert (await world.run(old))["refusal_code"] == "expired"
    assert (await world.run(old))["started_at"] is None
    assert (await world.run(fresh))["state"] == "succeeded"
    assert await world.audit_rows("task.run.started") != []
    assert len(await world.audit_rows("task.run.started")) == 1


async def test_the_maximum_request_age_is_configurable_but_capped(world, monkeypatch):
    from backend.admin.tasks.runner.runner import max_request_age

    assert world.runner(max_request_age_seconds=10 * 3600).max_request_age == timedelta(hours=10)
    assert world.runner(max_request_age_seconds=1000 * 3600).max_request_age == timedelta(hours=24)
    assert max_request_age({}) == timedelta(hours=24)
    assert max_request_age({"ADMIN_TASKS_MAX_REQUEST_AGE_HOURS": "6"}) == timedelta(hours=6)
    assert max_request_age({"ADMIN_TASKS_MAX_REQUEST_AGE_HOURS": "999"}) == timedelta(hours=24)
    assert max_request_age({"ADMIN_TASKS_MAX_REQUEST_AGE_HOURS": "junk"}) == timedelta(hours=24)
    run_id = await world.enqueue("selftest", {})
    world.clock.advance(11 * 3600)
    await world.drain(world.runner(max_request_age_seconds=10 * 3600))
    assert (await world.run(run_id))["refusal_code"] == "expired"


async def test_a_failed_or_refused_dry_run_does_not_count(world):
    params = {"items": 5, "batch_size": 5, "fail_at": 2}
    dry = await world.enqueue("selftest_guarded", params, dry_run=True)
    await world.drain()
    assert (await world.run(dry))["state"] == "failed"
    real = await world.enqueue("selftest_guarded", params, requested_at=await _later(world))
    await world.drain()
    assert (await world.run(real))["refusal_code"] == "dry_run_required"


async def test_a_dry_run_cannot_write_through_the_task_connection(world):
    params = {"items": 5, "batch_size": 5, "write_probe": True}
    dry = await world.enqueue("selftest_slow", params, dry_run=True)
    await world.drain()
    run = await world.run(dry)
    assert run["state"] == "failed"
    assert (await world.events(dry))[-1]["error_class"] != "TaskError"
    assert await world.locks() == []
    real = await world.enqueue("selftest_slow", params, requested_at=await _later(world))
    await world.drain()
    assert (await world.run(real))["state"] == "succeeded"  # a real run may write


async def test_a_run_is_resumed_from_a_checkpoint_only_once(world):
    import dataclasses

    gate = Gate(at_batch=1)
    install(gate)
    base = await world.enqueue("selftest_slow", SLOW)
    row, task = await start(world, world.runner())
    await asyncio.wait_for(gate.reached.wait(), 60)
    await world.cancel(base)
    gate.release.set()
    await task
    slow_impl.HOOKS.__dict__.clear()

    first = await world.enqueue("selftest_slow", SLOW, resumes=base)
    await world.drain()
    assert (await world.run(first))["state"] == "succeeded"
    second = await world.enqueue("selftest_slow", SLOW, resumes=base)
    await world.drain()
    assert (await world.run(second))["refusal_code"] == "already_resumed"

    # a task that says it can be replayed from the same checkpoint may
    registry = Registry()
    registry.register(dataclasses.replace(slow_impl.META, idempotent=True), slow_impl.SelfTestSlow())
    runner = world.runner()
    runner.registry = registry
    third = await world.enqueue("selftest_slow", SLOW, resumes=base)
    await world.drain(runner)
    assert (await world.run(third))["state"] == "succeeded"


async def test_the_lease_is_renewed_from_the_claim_not_from_the_start_of_run(world):
    release = asyncio.Event()
    reached = asyncio.Event()
    run_id = await world.enqueue("selftest_slow", SLOW)
    runner = world.runner(runner_id="runner-slow-precheck", heartbeat_seconds=0.05)
    row, registered = await runner.claim()
    impl = registered.impl

    async def slow_precheck(ctx, params):
        reached.set()
        await release.wait()

    impl.precheck = slow_precheck
    try:
        task = asyncio.create_task(runner.execute(row, registered))
        await asyncio.wait_for(reached.wait(), 60)
        before = (await world.run(run_id))["heartbeat_at"]
        world.clock.advance(200)  # far past lease + grace
        for _ in range(200):
            await asyncio.sleep(0.1)
            if (await world.run(run_id))["heartbeat_at"] > before:
                break
        assert await world.runner().takeover_stale() == 0
        release.set()
        assert await task == "succeeded"
    finally:
        del impl.precheck


async def test_a_claimed_run_that_was_taken_over_never_takes_locks(world):
    run_id = await world.enqueue("selftest_slow", SLOW)
    runner = world.runner(runner_id="runner-late")
    claimed = await runner.claim()
    world.clock.advance(91)
    assert await world.runner(runner_id="runner-taker").takeover_stale() == 1
    assert await runner.execute(*claimed) == "interrupted"
    assert await world.locks() == []
    assert slow_impl.WORLD == set()
    assert (await world.run(run_id))["state"] == "interrupted"


# -- failure handling and caps -----------------------------------------------------------------
async def test_failures_record_class_and_task_code_only(world):
    run_id = await world.enqueue("selftest_slow", {**SLOW, "fail_at": 7})
    await world.drain()
    run = await world.run(run_id)
    assert run["state"] == "failed" and run["refusal_code"] == "planted_failure"
    last = (await world.events(run_id))[-1]
    assert last["code"] == "failed" and last["error_class"] == "TaskError"
    (finished,) = await world.audit_rows("task.run.finished")
    assert finished["outcome"] == "failure"
    assert await world.locks() == []


class LeakEvents(str, enum.Enum):
    step = "step"


class LeakParams(Params):
    n: int = 1


class LeakResult(Result):
    n: int


LEAK_META = TaskMeta(
    name="leaky", version=1, params=LeakParams, result=LeakResult, events=LeakEvents, mutating=False
)
SECRET = "hunter2-deadbeefdeadbeefdeadbeefdeadbeefcafebabe"


class Leaky:
    META = LEAK_META

    async def precheck(self, ctx, params):
        return None

    async def run(self, ctx, params):
        raise RuntimeError(f"password={SECRET} user=alice@example.org")


async def test_exception_messages_never_reach_the_database(world):
    registry = Registry()
    registry.register(LEAK_META, Leaky())
    runner = world.runner()
    runner.registry = registry
    run_id = await world.enqueue("leaky", {})
    await world.drain(runner)
    run = await world.run(run_id)
    assert run["state"] == "failed" and run["refusal_code"] == "unexpected"
    assert (await world.events(run_id))[-1]["error_class"] == "RuntimeError"
    async with world.owner.connect() as conn:
        dump = json.dumps(
            [
                [dict(r) for r in (await conn.execute(text(f"SELECT * FROM {t}"))).mappings()]
                for t in ("tasks.runs", "tasks.run_events", "admin.audit_log")
            ],
            default=str,
        )
    assert "hunter2" not in dump and "deadbeef" not in dump and "alice" not in dump


async def test_event_cap_ends_with_a_truncated_marker(world, monkeypatch):
    from backend.admin.tasks import sanitiser
    from backend.admin.tasks.runner import context

    assert sanitiser.MAX_EVENTS_PER_RUN == 5000 and sanitiser.MAX_BYTES_PER_RUN == 1024 * 1024
    # a small cap keeps the database round trips few; the default is unit-tested
    monkeypatch.setattr(
        context, "EventSink", lambda events: sanitiser.EventSink(events, max_events=25)
    )
    run_id = await world.enqueue(
        "selftest_slow", {"items": 5, "batch_size": 5, "emit_events": 60}
    )
    await world.drain()
    run = await world.run(run_id)
    assert run["state"] == "succeeded"
    events = await world.events(run_id)
    assert len(events) == 25
    assert events[-1]["code"] == "truncated"
    assert [e["seq"] for e in events] == list(range(1, 26))
    (finished,) = await world.audit_rows("task.run.finished")
    assert finished["detail"]["truncated"] is True


async def test_an_undeclared_event_code_fails_the_run(world):
    class Rogue(slow_impl.SelfTestSlow):
        async def run(self, ctx, params):
            await ctx.emit("not_declared")

    registry = Registry()
    registry.register(slow_impl.META, Rogue())
    runner = world.runner()
    runner.registry = registry
    run_id = await world.enqueue("selftest_slow", SLOW)
    await world.drain(runner)
    run = await world.run(run_id)
    assert run["state"] == "failed" and run["refusal_code"] == "unexpected"
    assert (await world.events(run_id))[-1]["error_class"] == "EventRejected"


# -- fail closed -------------------------------------------------------------------------------
async def test_a_failed_audit_write_rolls_the_claim_back(world, monkeypatch):
    run_id = await world.enqueue("selftest", {})

    async def boom(*a, **k):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(audit, "write", boom)
    with pytest.raises(RuntimeError):
        await world.runner().claim()
    assert (await world.run(run_id))["state"] == "queued"


async def test_a_failed_audit_write_keeps_the_run_running_until_takeover(world, monkeypatch):
    run_id = await world.enqueue("selftest", {})
    runner = world.runner()
    claimed = await runner.claim()

    async def boom(*a, **k):
        raise RuntimeError("audit unavailable")

    original = audit.write
    monkeypatch.setattr(audit, "write", boom)
    with pytest.raises(RuntimeError):
        await runner.execute(*claimed)
    assert (await world.run(run_id))["state"] == "running"  # the finish rolled back
    monkeypatch.setattr(audit, "write", original)
    world.clock.advance(91)
    assert await world.runner().takeover_stale() == 1
    assert (await world.run(run_id))["state"] == "interrupted"


async def test_progress_writes_are_throttled_to_two_seconds(world, monkeypatch):
    from backend.admin.tasks.runner.context import RunContext

    flushes = []
    real = RunContext.flush_progress

    async def counting(self):
        flushes.append(self._latest_progress)
        await real(self)

    monkeypatch.setattr(RunContext, "flush_progress", counting)

    class Chatty(slow_impl.SelfTestSlow):
        async def run(self, ctx, params):
            for i in range(10):
                await ctx.progress(i, 10)
            world.clock.advance(2.5)
            await ctx.progress(10, 10)
            return slow_impl.SlowResult(changed=0, unchanged=0, batches=0)

    registry = Registry()
    registry.register(slow_impl.META, Chatty())
    runner = world.runner()
    runner.registry = registry
    run_id = await world.enqueue("selftest_slow", SLOW)
    await world.drain(runner)
    assert len(flushes) == 2
    assert (await world.run(run_id))["progress"] == {"done": 10, "total": 10}


async def test_serve_polls_and_stops(world):
    run_id = await world.enqueue("selftest", {})
    runner = world.runner()
    stop = asyncio.Event()
    task = asyncio.create_task(runner.serve(stop, poll_seconds=0.05))
    for _ in range(100):
        await asyncio.sleep(0.05)
        if (await world.run(run_id))["state"] == "succeeded":
            break
    stop.set()
    await asyncio.wait_for(task, 5)
    assert (await world.run(run_id))["state"] == "succeeded"
