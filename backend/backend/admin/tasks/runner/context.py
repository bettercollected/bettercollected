"""The runner's implementation of :class:`~backend.admin.tasks.spec.TaskContext`."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable, Mapping, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.security.clock import Clock
from backend.admin.services import audit
from backend.admin.tasks.sanitiser import (
    Event,
    EventRejected,
    EventSink,
)
from backend.admin.tasks.spec import TaskMeta

PROGRESS_INTERVAL = 2.0
MAX_CURSOR_BYTES = 2048


class LeaseLost(Exception):
    """The run was taken over (or finished by someone else): stop touching it."""


async def insert_event(conn, run_id: Any, event: Event) -> None:
    await conn.execute(
        text(
            "INSERT INTO tasks.run_events (run_id, seq, code, counts, ids, error_class) "
            "VALUES (:run, :seq, :code, CAST(:counts AS jsonb), CAST(:ids AS jsonb), :err)"
        ),
        {
            "run": run_id,
            "seq": event.seq,
            "code": event.code,
            "counts": json.dumps(event.counts) if event.counts is not None else None,
            "ids": json.dumps(event.ids) if event.ids is not None else None,
            "err": event.error_class,
        },
    )


class RunContext:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        clock: Clock,
        meta: TaskMeta,
        row: Mapping[str, Any],
        runner_id: str,
        stopping: Callable[[], bool],
    ) -> None:
        self._engine = engine
        self._clock = clock
        self._runner_id = runner_id
        self._stopping = stopping
        self.meta = meta
        self.run_id = str(row["id"])
        self._run_uuid = row["id"]
        self.task = row["task"]
        self.dry_run = bool(row["dry_run"])
        self.params_hash = row["params_hash"]
        self.requested_by = row["requested_by"]
        self._resume_uuid = row.get("resumes_run_id")
        self.resumes_run_id: Optional[str] = (
            str(self._resume_uuid) if self._resume_uuid else None
        )
        self.sink = EventSink(meta.events)
        self.fingerprint: Optional[Callable[[], Awaitable[Optional[str]]]] = None
        self._fp_value: Optional[str] = None
        self.lost = False
        self.cancel_seen = False  # an admin asked for cancel
        self.shutdown_seen = False  # the runner is stopping
        self._last_progress_at: Optional[float] = None
        self._latest_progress: Optional[dict] = None

    # -- liveness ---------------------------------------------------------------
    def _alive(self) -> None:
        if self.lost:
            raise LeaseLost()

    async def cancelled(self) -> bool:
        if self.lost:
            return True
        if self._stopping():
            self.shutdown_seen = True
            return True
        async with self._engine.connect() as conn:
            requested = (
                await conn.execute(
                    text("SELECT cancel_requested_at FROM tasks.runs WHERE id = :id"),
                    {"id": self._run_uuid},
                )
            ).scalar()
        if requested is not None:
            self.cancel_seen = True
            return True
        return False

    # -- reporting ----------------------------------------------------------------
    async def progress(self, done: int, total: Optional[int] = None) -> None:
        self._alive()
        if (
            isinstance(done, bool)
            or not isinstance(done, int)
            or (total is not None and (isinstance(total, bool) or not isinstance(total, int)))
        ):
            raise EventRejected("progress is integers")
        self._latest_progress = {"done": done, "total": total}
        now = self._clock.time()
        if self._last_progress_at is not None and now - self._last_progress_at < PROGRESS_INTERVAL:
            return
        self._last_progress_at = now
        await self.flush_progress()

    async def flush_progress(self) -> None:
        if self._latest_progress is None:
            return
        async with self._engine.begin() as conn:
            result = await conn.execute(
                text(
                    "UPDATE tasks.runs SET progress = CAST(:p AS jsonb), heartbeat_at = :now "
                    "WHERE id = :id AND state = 'running' AND runner_id = :rid"
                ),
                {
                    "p": json.dumps(self._latest_progress),
                    "now": self._clock.now(),
                    "id": self._run_uuid,
                    "rid": self._runner_id,
                },
            )
            if result.rowcount != 1:
                self.lost = True
                raise LeaseLost()

    async def emit(
        self,
        code: Any,
        counts: Optional[Mapping[str, int]] = None,
        ids: Optional[Sequence[str]] = None,
    ) -> None:
        self._alive()
        event = self.sink.build(code, counts, ids)
        if event is None:
            return
        async with self._engine.begin() as conn:
            await insert_event(conn, self._run_uuid, event)

    async def checkpoint(self, cursor: Mapping[str, Any]) -> None:
        self._alive()
        body = dict(cursor)
        if self.fingerprint is not None:
            if self._fp_value is None:
                self._fp_value = await self.fingerprint()
            if self._fp_value is not None:
                body["_fp"] = self._fp_value
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(raw.encode()) > MAX_CURSOR_BYTES:
            raise EventRejected("checkpoint cursor over 2 KB")
        async with self._engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO tasks.checkpoints (run_id, cursor) "
                    "VALUES (:id, CAST(:c AS jsonb))"
                ),
                {"id": self._run_uuid, "c": raw},
            )

    async def load_checkpoint(self) -> Optional[dict]:
        """Own latest cursor, else the resumed run's. ``_fp`` is not exposed."""
        async with self._engine.connect() as conn:
            for run in (self._run_uuid, self._resume_uuid):
                if run is None:
                    continue
                cursor = (
                    await conn.execute(
                        text(
                            "SELECT cursor FROM tasks.checkpoints WHERE run_id = :id "
                            "ORDER BY id DESC LIMIT 1"
                        ),
                        {"id": run},
                    )
                ).scalar()
                if cursor is not None:
                    return {k: v for k, v in cursor.items() if k != "_fp"}
        return None

    def read_setting(self, name: str) -> Any:
        raise NotImplementedError("the settings store is not available yet")

    async def audit(
        self,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        before: Any = None,
        after: Any = None,
        outcome: str = "success",
        detail: Any = None,
    ) -> None:
        self._alive()
        if not action.startswith("task."):
            raise EventRejected("task audit actions start with 'task.'")
        merged = {
            "run_id": self.run_id,
            "task": self.task,
            "requested_by": self.requested_by,
        }
        if isinstance(detail, Mapping):
            merged.update({k: v for k, v in detail.items() if k not in merged})
        async with self._engine.begin() as conn:
            await audit.write(
                conn,
                action,
                target_type,
                target_id,
                before,
                after,
                outcome,
                actor_kind="system",
                detail=merged,
                request_id=self.run_id,
            )
