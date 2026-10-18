"""The task runner: claim, verify, gate, lock, run, finish.

Rules, in order, for every run (``Runner.execute``):

1. claim: one transaction takes the oldest queued row (``FOR UPDATE SKIP LOCKED``),
   verifies the request signature, the task's name and version against the
   deployed registry and the parameters against the task's model. A row that
   fails is ended ``refused`` and never reaches ``task.run.started`` or any task
   code. Otherwise the row becomes ``running`` and ``task.run.started`` is
   audited in the same transaction.
2. gates: resume rules (same ``params_hash`` and version, a resumable task, an
   earlier run that did not succeed), the prior dry run for tasks that need one
   (succeeded, same ``params_hash``, finished under 24 h ago), then the task's
   ``precheck`` (a :class:`Refusal` ends the run ``refused``).
3. locks: ``task:<name>``, ``mutating:global`` for mutating tasks and the task's
   declared resources, all or nothing (``INSERT ... ON CONFLICT DO NOTHING``).
   A lock's lease is its run's ``heartbeat_at``: 60 s, renewed every 10 s,
   taken over only after the lease plus a 30 s grace (the old run becomes
   ``interrupted``).
4. run, with progress (at most every 2 s), cooperative cancel, checkpoints.
5. finish: state, result, lock release and ``task.run.finished`` in one
   transaction, fail closed (an audit failure rolls the state change back; the
   run then stays ``running`` until its lease lapses and it is taken over).

The runner never swallows an audit error and never records an exception
message.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from datetime import timedelta
from typing import Any, Mapping, Optional

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.security.clock import Clock, SystemClock
from backend.admin.services import audit
from backend.admin.tasks import signing
from backend.admin.tasks.registry import Registered, Registry
from backend.admin.tasks.runner.context import LeaseLost, RunContext, insert_event
from backend.admin.tasks.sanitiser import Event, EventRejected, exception_class_name
from backend.admin.tasks.spec import (
    MAX_RESULT_BYTES,
    Refusal,
    RunState,
    TaskError,
)

log = logging.getLogger("backend.admin.tasks")

LEASE_SECONDS = 60
HEARTBEAT_SECONDS = 10
GRACE_SECONDS = 30
POLL_SECONDS = 5
DRY_RUN_MAX_AGE = timedelta(hours=24)
MAX_REQUEST_AGE_CAP = timedelta(hours=24)
MAX_AGE_ENV = "ADMIN_TASKS_MAX_REQUEST_AGE_HOURS"


def max_request_age(env=None) -> timedelta:
    """How old a queued request may be before it is refused as ``expired``:
    ``ADMIN_TASKS_MAX_REQUEST_AGE_HOURS`` (whole hours), never above 24 h."""
    import os

    raw = (env if env is not None else os.environ).get(MAX_AGE_ENV, "")
    try:
        hours = int(raw) if raw.strip() else 24
    except ValueError:
        hours = 24
    return min(timedelta(hours=max(1, hours)), MAX_REQUEST_AGE_CAP)

_OUTCOME = {
    RunState.succeeded: "success",
    RunState.cancelled: "success",
    RunState.failed: "failure",
    RunState.interrupted: "failure",
    RunState.refused: "denied",
}


class _LockHeld(Exception):
    pass


def lock_names(meta) -> list[str]:
    names = {f"task:{meta.name}", *meta.resources}
    if meta.mutating:
        names.add("mutating:global")
    return sorted(names)


class Runner:
    def __init__(
        self,
        engine: AsyncEngine,
        registry: Registry,
        *,
        clock: Optional[Clock] = None,
        runner_id: Optional[str] = None,
        heartbeat_seconds: Optional[float] = HEARTBEAT_SECONDS,
        lease_seconds: float = LEASE_SECONDS,
        grace_seconds: float = GRACE_SECONDS,
        max_request_age_seconds: Optional[float] = None,
    ) -> None:
        self.engine = engine
        self.registry = registry
        self.clock = clock or SystemClock()
        self.runner_id = runner_id or f"runner-{secrets.token_hex(6)}"
        self.heartbeat_seconds = heartbeat_seconds
        self.lease_seconds = lease_seconds
        self.grace_seconds = grace_seconds
        cap = MAX_REQUEST_AGE_CAP.total_seconds()
        self.max_request_age = timedelta(
            seconds=min(
                cap,
                max_request_age_seconds
                if max_request_age_seconds is not None
                else max_request_age().total_seconds(),
            )
        )
        self.stopping = False
        self._keys: dict[int, bytes] = {}

    # -- small helpers -----------------------------------------------------------
    def _request_key(self, version: int) -> bytes:
        if version not in self._keys:
            self._keys[version] = signing.request_key(version)
        return self._keys[version]

    async def _audit(
        self, conn, action: str, row: Mapping[str, Any], outcome: str, **detail: Any
    ) -> None:
        body = {
            "run_id": str(row["id"]),
            "task": row["task"],
            "version": row["version"],
            "requested_by": row["requested_by"],
            "dry_run": bool(row["dry_run"]),
            "runner": self.runner_id,
            **detail,
        }
        await audit.write(
            conn,
            action,
            "task_run",
            str(row["id"]),
            None,
            None,
            outcome,
            actor_kind="system",
            detail=body,
            request_id=str(row["id"]),
        )

    def _admit(self, row: Mapping[str, Any]) -> Optional[str]:
        """A refusal code for a claimed row that must not run, else ``None``."""
        try:
            key = self._request_key(int(row["sig_version"]))
        except Exception:  # noqa: BLE001 - unknown signing key version
            return "bad_signature"
        if not signing.verify_request(row, key):
            return "bad_signature"
        # the signed timestamp is the request's age: an old request (a stopped
        # runner, a forgotten queue) is not run on a decision nobody remembers
        if self.clock.now() - row["requested_at"] > self.max_request_age:
            return "expired"
        registered = self.registry.get(row["task"])
        if registered is None:
            return "unknown_task"
        if registered.meta.version != row["version"]:
            return "version_mismatch"
        try:
            registered.meta.params.model_validate(row["params"])
        except ValidationError:
            return "bad_params"
        return None

    # -- claim -------------------------------------------------------------------
    async def claim(self) -> Optional[tuple[Mapping[str, Any], Registered]]:
        """Claim the oldest queued run. ``None`` when there is none. A row that
        fails verification is finished here and ``claim`` looks at the next."""
        while True:
            async with self.engine.connect() as conn:
                async with conn.begin():
                    row = (
                        (
                            await conn.execute(
                                text(
                                    "SELECT * FROM tasks.runs WHERE state = 'queued' "
                                    "ORDER BY created_at, id LIMIT 1 FOR UPDATE SKIP LOCKED"
                                )
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if row is None:
                        return None
                    row = dict(row)
                    now = self.clock.now()
                    if row["cancel_requested_at"] is not None:
                        await self._end_unclaimed(conn, row, RunState.cancelled, None, now)
                        continue
                    refusal = self._admit(row)
                    if refusal is not None:
                        await self._end_unclaimed(conn, row, RunState.refused, refusal, now)
                        continue
                    await conn.execute(
                        text(
                            "UPDATE tasks.runs SET state = 'running', runner_id = :rid, "
                            "started_at = :now, heartbeat_at = :now WHERE id = :id"
                        ),
                        {"rid": self.runner_id, "now": now, "id": row["id"]},
                    )
                    await self._audit(conn, "task.run.started", row, "success")
                    await self._announce_apply(conn, row)
                    return row, self.registry.get(row["task"])

    async def _announce_apply(self, conn, row: Mapping[str, Any]) -> None:
        """A re-encryption rewrites every stored response and credential: when an
        APPLY run of it starts, every admin is told, in the transaction that
        records the start (the database function checks that audit row is there).
        Dry runs tell no one."""
        if row["task"] != "keyset.reencrypt" or row["dry_run"]:
            return
        params = row["params"]
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except ValueError:
                return
        primary = params.get("primary_id") if isinstance(params, dict) else None
        if not isinstance(primary, int) or isinstance(primary, bool):
            return  # the parameters will not validate: the run is refused anyway
        await conn.execute(
            text("SELECT settings.task_notify_reencrypt(:run, :primary)"),
            {"run": str(row["id"]), "primary": primary},
        )

    async def _end_unclaimed(
        self, conn, row: Mapping[str, Any], state: RunState, code: Optional[str], now
    ) -> None:
        await conn.execute(
            text(
                "UPDATE tasks.runs SET state = :s, finished_at = :now, refusal_code = :c "
                "WHERE id = :id AND state = 'queued'"
            ),
            {"s": state.value, "now": now, "c": code, "id": row["id"]},
        )
        await self._audit(
            conn,
            "task.run.finished",
            row,
            _OUTCOME[state],
            state=state.value,
            reason=code,
        )

    # -- gates -------------------------------------------------------------------
    async def _gate(self, row: Mapping[str, Any], meta) -> Optional[str]:
        async with self.engine.connect() as conn:
            if row["resumes_run_id"] is not None:
                if not meta.resumable:
                    return "not_resumable"
                prior = (
                    (
                        await conn.execute(
                            text(
                                "SELECT task, version, params_hash, state FROM tasks.runs "
                                "WHERE id = :id"
                            ),
                            {"id": row["resumes_run_id"]},
                        )
                    )
                    .mappings()
                    .first()
                )
                if (
                    prior is None
                    or prior["task"] != row["task"]
                    or prior["version"] != row["version"]
                    or prior["params_hash"] != row["params_hash"]
                    or prior["state"]
                    not in (
                        RunState.failed.value,
                        RunState.cancelled.value,
                        RunState.interrupted.value,
                    )
                ):
                    return "resume_mismatch"
                if not meta.idempotent:
                    again = (
                        await conn.execute(
                            text(
                                "SELECT 1 FROM tasks.runs WHERE resumes_run_id = :id "
                                "AND state = 'succeeded' AND id <> :me LIMIT 1"
                            ),
                            {"id": row["resumes_run_id"], "me": row["id"]},
                        )
                    ).first()
                    if again is not None:
                        return "already_resumed"
            if meta.requires_prior_dry_run and not row["dry_run"]:
                since = self.clock.now() - DRY_RUN_MAX_AGE
                found = (
                    await conn.execute(
                        text(
                            "SELECT 1 FROM tasks.runs WHERE task = :t AND version = :v "
                            "AND params_hash = :h AND dry_run AND state = 'succeeded' "
                            "AND finished_at > :since AND finished_at < :requested_at LIMIT 1"
                        ),
                        {
                            "t": row["task"],
                            "v": row["version"],
                            "h": row["params_hash"],
                            "since": since,
                            "requested_at": row["requested_at"],
                        },
                    )
                ).first()
                if found is None:
                    return "dry_run_required"
        return None

    async def _fingerprint_ok(self, row: Mapping[str, Any], ctx: RunContext) -> bool:
        """Keyset-fingerprint hook: when the task installed ``ctx.fingerprint``, a
        resume must see the fingerprint the earlier run checkpointed."""
        if ctx.fingerprint is None or row["resumes_run_id"] is None:
            return True
        current = await ctx.fingerprint()
        async with self.engine.connect() as conn:
            cursor = (
                await conn.execute(
                    text(
                        "SELECT cursor FROM tasks.checkpoints WHERE run_id = :id "
                        "ORDER BY id DESC LIMIT 1"
                    ),
                    {"id": row["resumes_run_id"]},
                )
            ).scalar()
        stored = cursor.get("_fp") if cursor else None
        return stored is None or stored == current

    async def _acquire(self, row: Mapping[str, Any], meta) -> bool:
        """All of the task's locks or none (``False``)."""
        try:
            async with self.engine.begin() as conn:
                # still ours? (a takeover would have ended the run)
                owned = (
                    await conn.execute(
                        text(
                            "SELECT 1 FROM tasks.runs WHERE id = :id AND state = 'running' "
                            "AND runner_id = :rid FOR UPDATE"
                        ),
                        {"id": row["id"], "rid": self.runner_id},
                    )
                ).first()
                if owned is None:
                    raise LeaseLost()
                await conn.execute(
                    text(
                        "DELETE FROM tasks.locks l USING tasks.runs r "
                        "WHERE l.run_id = r.id AND r.state <> 'running'"
                    )
                )
                for name in lock_names(meta):
                    got = (
                        await conn.execute(
                            text(
                                "INSERT INTO tasks.locks (name, run_id, runner_id, acquired_at) "
                                "VALUES (:n, :id, :rid, :now) ON CONFLICT DO NOTHING "
                                "RETURNING name"
                            ),
                            {
                                "n": name,
                                "id": row["id"],
                                "rid": self.runner_id,
                                "now": self.clock.now(),
                            },
                        )
                    ).first()
                    if got is None:
                        raise _LockHeld()
        except _LockHeld:
            return False
        return True

    # -- finishing -----------------------------------------------------------------
    async def _finish(
        self,
        ctx: RunContext,
        row: Mapping[str, Any],
        state: RunState,
        *,
        result: Optional[dict] = None,
        code: Optional[str] = None,
        error_class: Optional[str] = None,
    ) -> None:
        now = self.clock.now()
        async with self.engine.connect() as conn:
            async with conn.begin():
                updated = await conn.execute(
                    text(
                        "UPDATE tasks.runs SET state = :s, finished_at = :now, "
                        "result = CAST(:r AS jsonb), refusal_code = :c, "
                        "progress = coalesce(CAST(:p AS jsonb), progress) "
                        "WHERE id = :id AND state = 'running' AND runner_id = :rid"
                    ),
                    {
                        "s": state.value,
                        "now": now,
                        "r": json.dumps(result) if result is not None else None,
                        "c": code,
                        "p": json.dumps(ctx._latest_progress) if ctx._latest_progress else None,
                        "id": row["id"],
                        "rid": self.runner_id,
                    },
                )
                if updated.rowcount != 1:
                    raise LeaseLost()
                await conn.execute(
                    text("DELETE FROM tasks.locks WHERE run_id = :id"), {"id": row["id"]}
                )
                if state in (RunState.failed, RunState.cancelled, RunState.interrupted):
                    marker = ctx.sink.build_system(
                        "cancelled" if state is RunState.cancelled else "failed",
                        error_class=error_class,
                    )
                    if marker is not None:
                        await insert_event(conn, row["id"], marker)
                await self._audit(
                    conn,
                    "task.run.finished",
                    row,
                    _OUTCOME[state],
                    state=state.value,
                    reason=code,
                    error_class=error_class,
                    events=ctx.sink.seq,
                    truncated=ctx.sink.truncated,
                )

    # -- running -------------------------------------------------------------------
    async def execute(self, row: Mapping[str, Any], registered: Registered) -> RunState:
        """Run a claimed row to a terminal state (returned). A run that lost its
        lease is left to whoever took it over."""
        meta, impl = registered.meta, registered.impl
        ctx = RunContext(
            engine=self.engine,
            clock=self.clock,
            meta=meta,
            row=row,
            runner_id=self.runner_id,
            stopping=lambda: self.stopping,
        )
        beat: Optional[asyncio.Task] = None
        try:
            # the lease is renewed from the moment of the claim, so a slow
            # precheck or gate cannot let another runner take the run over
            if self.heartbeat_seconds:
                beat = asyncio.create_task(self._heartbeat(ctx, row))
            params = meta.params.model_validate(row["params"])
            refusal = await self._gate(row, meta)
            if refusal is None:
                try:
                    await impl.precheck(ctx, params)
                except Refusal as r:
                    refusal = r.code
            if refusal is None and not await self._fingerprint_ok(row, ctx):
                refusal = "resume_mismatch"
            if refusal is None and not await self._acquire(row, meta):
                refusal = "lock_held"
            if refusal is not None:
                await self._finish(ctx, row, RunState.refused, code=refusal)
                return RunState.refused

            try:
                outcome = await impl.run(ctx, params)
                result = meta.result.model_validate(outcome).model_dump(mode="json")
                if len(json.dumps(result)) > MAX_RESULT_BYTES:
                    raise EventRejected("result over 8 KB")
                state = RunState.succeeded
                if ctx.shutdown_seen:
                    state = RunState.interrupted
                elif ctx.cancel_seen:
                    state = RunState.cancelled
                await self._finish(ctx, row, state, result=result)
                return state
            except LeaseLost:
                raise
            except Refusal as r:
                await self._finish(ctx, row, RunState.refused, code=r.code)
                return RunState.refused
            except TaskError as e:
                await self._finish(
                    ctx, row, RunState.failed, code=e.code, error_class=type(e).__name__
                )
                return RunState.failed
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - recorded by class name only
                log.warning("task run failed run=%s class=%s", row["id"], type(e).__name__)
                await self._finish(
                    ctx,
                    row,
                    RunState.failed,
                    code="unexpected",
                    error_class=exception_class_name(e),
                )
                return RunState.failed
        except LeaseLost:
            log.warning("task run lost its lease run=%s", row["id"])
            return RunState.interrupted
        finally:
            if beat is not None:
                beat.cancel()
                try:
                    await beat
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

    async def _heartbeat(self, ctx: RunContext, row: Mapping[str, Any]) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            try:
                if not await self.beat(row["id"]):
                    ctx.lost = True
                    return
            except Exception as e:  # noqa: BLE001 - a database blip must not kill the run
                log.warning("heartbeat failed run=%s class=%s", row["id"], type(e).__name__)

    async def beat(self, run_id) -> bool:
        """Renew the lease of ``run_id``; ``False`` if the run is no longer ours."""
        async with self.engine.begin() as conn:
            result = await conn.execute(
                text(
                    "UPDATE tasks.runs SET heartbeat_at = :now "
                    "WHERE id = :id AND state = 'running' AND runner_id = :rid"
                ),
                {"now": self.clock.now(), "id": run_id, "rid": self.runner_id},
            )
        return result.rowcount == 1

    # -- takeover ------------------------------------------------------------------
    async def takeover_stale(self) -> int:
        """Mark runs whose lease and grace have lapsed ``interrupted`` and free
        their locks. Returns how many were taken over."""
        now = self.clock.now()
        cutoff = now - timedelta(seconds=self.lease_seconds + self.grace_seconds)
        async with self.engine.connect() as conn:
            stale = (
                await conn.execute(
                    text(
                        "SELECT id FROM tasks.runs WHERE state = 'running' "
                        "AND heartbeat_at < :cutoff ORDER BY id"
                    ),
                    {"cutoff": cutoff},
                )
            ).scalars().all()
        taken = 0
        for run_id in stale:
            async with self.engine.connect() as conn:
                async with conn.begin():
                    row = (
                        (
                            await conn.execute(
                                text(
                                    "UPDATE tasks.runs SET state = 'interrupted', "
                                    "finished_at = :now WHERE id = :id AND state = 'running' "
                                    "AND heartbeat_at < :cutoff RETURNING *"
                                ),
                                {"now": now, "id": run_id, "cutoff": cutoff},
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if row is None:
                        continue
                    await conn.execute(
                        text("DELETE FROM tasks.locks WHERE run_id = :id"), {"id": run_id}
                    )
                    seq = (
                        await conn.execute(
                            text(
                                "SELECT coalesce(max(seq), 0) + 1 FROM tasks.run_events "
                                "WHERE run_id = :id"
                            ),
                            {"id": run_id},
                        )
                    ).scalar_one()
                    await insert_event(conn, run_id, Event(seq, "interrupted", None, None))
                    await self._audit(
                        conn,
                        "task.run.finished",
                        row,
                        "failure",
                        state="interrupted",
                        reason="lease_expired",
                        taken_over_by=self.runner_id,
                        previous_runner=row["runner_id"],
                    )
                    taken += 1
        return taken

    # -- loop ----------------------------------------------------------------------
    async def run_once(self) -> bool:
        """Claim and run one queued run. ``False`` when nothing was queued."""
        claimed = await self.claim()
        if claimed is None:
            return False
        row, registered = claimed
        await self.execute(row, registered)
        return True

    async def serve(self, stop: asyncio.Event, poll_seconds: float = POLL_SECONDS) -> None:
        """Poll until ``stop`` is set: takeover, then drain the queue, then wait."""
        while not stop.is_set():
            try:
                await self.takeover_stale()
                while not stop.is_set() and await self.run_once():
                    pass
            except Exception as e:  # noqa: BLE001 - keep serving; class name only
                log.error("runner cycle failed class=%s", type(e).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                pass
