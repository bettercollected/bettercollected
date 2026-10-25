"""What the portal's task pages read and write.

Reads: the catalog (metadata only), runs, their events and checkpoint presence,
shaped for display (every string that came from the database is re-checked
against the shape the runner promises, so a row written by anything else cannot
put prose on a page). Writes, each in ONE transaction with its audit row:

* ``request_run``: a signed ``tasks.runs`` row (state ``queued``) and
  ``task.run.requested``;
* ``request_cancel``: ``cancel_requested_at`` (the only column the admin role may
  update) and ``task.run.cancel_requested``;
* ``request_resume``: a new signed row with ``resumes_run_id``.

This module imports the catalog, the signing helpers and the spec only, never a
task implementation or the runner (an import test enforces it).
"""

from __future__ import annotations

import enum
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.repositories import settings as outbox
from backend.admin.security.clock import Clock
from backend.admin.services import audit, taskform
from backend.admin.tasks import catalog, signing
from backend.admin.tasks.spec import (
    CODE_RE,
    COUNTER_RE,
    ID_RE,
    TERMINAL_STATES,
    RunState,
    TaskMeta,
)

DRY_RUN_MAX_AGE = timedelta(hours=24)  # the runner's own bound (``runner.DRY_RUN_MAX_AGE``)
MAX_PARAMS_BYTES = 8000  # the table's CHECK is 8192
RUNS_PER_PAGE = 25
EVENTS_PER_PAGE = 50
EVENTS_LAST = 20
RESUMABLE_STATES = frozenset({"failed", "interrupted", "cancelled"})
ACTIVE_STATES = frozenset({"queued", "running"})
_CLASS_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,79}$")
_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")


class Refusal(str, enum.Enum):
    """Why the portal declined to start, cancel or resume. Fixed codes; the pages
    map each to one fixed sentence."""

    unknown_task = "unknown_task"
    bad_params = "bad_params"
    stored_params = "stored_params"
    params_too_large = "params_too_large"
    dry_run_required = "dry_run_required"
    unknown_run = "unknown_run"
    not_active = "not_active"
    not_resumable = "not_resumable"
    not_eligible = "not_eligible"
    resume_active = "resume_active"
    already_resumed = "already_resumed"
    version_changed = "version_changed"
    read_only = "read_only"


@dataclass(frozen=True)
class Started:
    run_id: Optional[uuid.UUID] = None
    refusal: Optional[Refusal] = None
    already: bool = False

    @property
    def ok(self) -> bool:
        return self.refusal is None


@dataclass(frozen=True)
class TaskRow:
    meta: TaskMeta
    last_state: Optional[str] = None
    last_run_id: Optional[str] = None
    last_dry_run: bool = False
    last_at: Optional[datetime] = None


@dataclass(frozen=True)
class EventView:
    seq: int
    at: datetime
    code: str
    counts: list
    ids: list
    error_class: Optional[str]


@dataclass(frozen=True)
class RunView:
    id: str
    task: str
    title: str
    version: int
    state: str
    dry_run: bool
    requested_by: str
    requested_at: datetime
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    cancel_requested_at: Optional[datetime]
    resumes_run_id: Optional[str]
    refusal_code: Optional[str]
    done: Optional[int]
    total: Optional[int]
    params_hash: str = ""

    @property
    def terminal(self) -> bool:
        return self.state in {s.value for s in TERMINAL_STATES}

    @property
    def active(self) -> bool:
        return self.state in ACTIVE_STATES

    @property
    def percent(self) -> Optional[int]:
        if self.done is None or not self.total:
            return None
        return max(0, min(100, int(self.done * 100 / self.total)))


@dataclass(frozen=True)
class RunDetail:
    run: RunView
    meta: Optional[TaskMeta]
    params: list  # (label, value) rows
    result: Optional[list]  # (path, value) rows, None when there is none
    result_note: Optional[str]  # "no_result" | "mismatch" | None
    events: list
    event_count: int
    next_after: Optional[int]
    checkpoints: int
    can_cancel: bool
    can_resume: bool
    resume_blocked: Optional[str]  # fixed code when a resume would be refused


@dataclass(frozen=True)
class DryRunSummary:
    """The latest finished dry run of a task with exactly the parameters an apply
    is about to use: who asked for it, when it finished and its result counters
    (the same rows the run page shows, through the task's own result schema)."""

    run: RunView
    result: Optional[list]  # (path, value) rows, None when there is none to show
    result_note: Optional[str]  # "no_result" | "mismatch" | None
    older_than_a_day: bool


@dataclass(frozen=True)
class RunsPage:
    runs: list
    page: int
    has_more: bool


def _safe_int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _progress(raw: Any) -> tuple[Optional[int], Optional[int]]:
    if not isinstance(raw, Mapping):
        return None, None
    return _safe_int(raw.get("done")), _safe_int(raw.get("total"))


def _refusal_code(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and CODE_RE.match(value) else None


def event_view(row: Mapping[str, Any]) -> EventView:
    counts = row["counts"] if isinstance(row["counts"], Mapping) else {}
    ids = row["ids"] if isinstance(row["ids"], list) else []
    cls = row["error_class"]
    return EventView(
        seq=int(row["seq"]),
        at=row["at"],
        code=row["code"] if isinstance(row["code"], str) and CODE_RE.match(row["code"]) else "-",
        counts=[
            (k, v) for k, v in counts.items()
            if isinstance(k, str) and COUNTER_RE.match(k) and _safe_int(v) is not None
        ][:16],
        ids=[i for i in ids if isinstance(i, str) and ID_RE.match(i)][:20],
        error_class=cls if isinstance(cls, str) and _CLASS_NAME.match(cls) else None,
    )


def flatten_result(model: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """``(path, value)`` rows of a validated ``Result`` (ints, bools, ids, enums)."""
    rows: list[tuple[str, Any]] = []
    for name, value in model.model_dump(mode="json").items():
        path = f"{prefix}{name}"
        if isinstance(value, dict):
            rows.extend(_flatten_dict(value, path + "."))
        else:
            rows.append((path, value))
    return rows


def _flatten_dict(data: Mapping, prefix: str) -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for name, value in data.items():
        if isinstance(value, dict):
            rows.extend(_flatten_dict(value, f"{prefix}{name}."))
        else:
            rows.append((f"{prefix}{name}", value))
    return rows


class TaskPageService:
    def __init__(self, engine: AsyncEngine, clock: Clock, env: Optional[Mapping[str, str]] = None):
        self._engine = engine
        self._clock = clock
        self._env = env  # None: the process environment, read at call time

    # -- catalog ---------------------------------------------------------------------
    def metas(self) -> list[TaskMeta]:
        return catalog.all_meta(self._env) if self._env is not None else catalog.all_meta()

    def meta(self, name: str) -> Optional[TaskMeta]:
        return next((m for m in self.metas() if m.name == name), None)

    # -- reads -----------------------------------------------------------------------
    async def task_rows(self) -> list[TaskRow]:
        async with self._engine.connect() as conn:
            latest = {
                r["task"]: r
                for r in (
                    await conn.execute(
                        text(
                            "SELECT DISTINCT ON (task) task, id, state, dry_run, created_at "
                            "FROM tasks.runs ORDER BY task, created_at DESC, id"
                        )
                    )
                ).mappings()
            }
        rows = []
        for meta in self.metas():
            last = latest.get(meta.name)
            rows.append(
                TaskRow(
                    meta,
                    last["state"] if last else None,
                    str(last["id"]) if last else None,
                    bool(last["dry_run"]) if last else False,
                    last["created_at"] if last else None,
                )
            )
        return rows

    def _view(self, row: Mapping[str, Any]) -> RunView:
        meta = self.meta(row["task"])
        done, total = _progress(row["progress"])
        return RunView(
            id=str(row["id"]),
            task=row["task"],
            title=meta.title if meta and meta.title else "",
            version=int(row["version"]),
            state=row["state"],
            dry_run=bool(row["dry_run"]),
            requested_by=row["requested_by"],
            requested_at=row["requested_at"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            cancel_requested_at=row["cancel_requested_at"],
            resumes_run_id=str(row["resumes_run_id"]) if row["resumes_run_id"] else None,
            refusal_code=_refusal_code(row["refusal_code"]),
            done=done,
            total=total,
            params_hash=row["params_hash"],
        )

    async def runs_page(
        self, page: int = 1, task: Optional[str] = None, state: Optional[str] = None
    ) -> RunsPage:
        page = max(1, min(page, 1000))
        async with self._engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT * FROM tasks.runs WHERE (CAST(:t AS text) IS NULL OR task = :t) "
                        "AND (CAST(:s AS text) IS NULL OR state = :s) "
                        "ORDER BY created_at DESC, id LIMIT :n OFFSET :o"
                    ),
                    {"t": task, "s": state, "n": RUNS_PER_PAGE + 1, "o": (page - 1) * RUNS_PER_PAGE},
                )
            ).mappings().all()
        return RunsPage([self._view(r) for r in rows[:RUNS_PER_PAGE]], page, len(rows) > RUNS_PER_PAGE)

    async def _run_row(self, conn, run_id: uuid.UUID) -> Optional[Mapping[str, Any]]:
        return (
            await conn.execute(text("SELECT * FROM tasks.runs WHERE id = :id"), {"id": run_id})
        ).mappings().first()

    @staticmethod
    def parse_id(value: str) -> Optional[uuid.UUID]:
        if not isinstance(value, str) or not _UUID.match(value):
            return None
        try:
            return uuid.UUID(value)
        except ValueError:
            return None

    async def run_progress(self, run_id: uuid.UUID, after: int = 0) -> Optional[dict]:
        """The polling payload: state, progress and the events after ``after``."""
        async with self._engine.connect() as conn:
            row = await self._run_row(conn, run_id)
            if row is None:
                return None
            events = (
                await conn.execute(
                    text(
                        "SELECT seq, at, code, counts, ids, error_class FROM tasks.run_events "
                        "WHERE run_id = :id AND seq > :after ORDER BY seq LIMIT :n"
                    ),
                    {"id": run_id, "after": max(0, after), "n": EVENTS_PER_PAGE},
                )
            ).mappings().all()
        view = self._view(row)
        return {
            "id": view.id,
            "state": view.state,
            "terminal": view.terminal,
            "done": view.done,
            "total": view.total,
            "percent": view.percent,
            "cancel_requested": view.cancel_requested_at is not None,
            "refusal_code": view.refusal_code,
            "events": [
                {
                    "seq": e.seq, "at": e.at.isoformat(), "code": e.code,
                    "counts": dict(e.counts), "ids": e.ids, "error_class": e.error_class,
                }
                for e in map(event_view, events)
            ],
        }

    async def run_detail(self, run_id: uuid.UUID, after: int = 0) -> Optional[RunDetail]:
        async with self._engine.connect() as conn:
            row = await self._run_row(conn, run_id)
            if row is None:
                return None
            events = (
                await conn.execute(
                    text(
                        "SELECT seq, at, code, counts, ids, error_class FROM tasks.run_events "
                        "WHERE run_id = :id AND seq > :after ORDER BY seq LIMIT :n"
                    ),
                    {"id": run_id, "after": max(0, after), "n": EVENTS_PER_PAGE + 1},
                )
            ).mappings().all()
            total_events = (
                await conn.execute(
                    text("SELECT count(*) FROM tasks.run_events WHERE run_id = :id"), {"id": run_id}
                )
            ).scalar_one()
            checkpoints = (
                await conn.execute(
                    text("SELECT count(*) FROM tasks.checkpoints WHERE run_id = :id"), {"id": run_id}
                )
            ).scalar_one()
        view = self._view(row)
        meta = self.meta(view.task)
        shown = [event_view(e) for e in events[:EVENTS_PER_PAGE]]
        params_rows: list = []
        result_rows: Optional[list] = None
        note: Optional[str] = None
        if meta is not None and meta.version == view.version:
            fields = taskform.fields_for(meta)
            valid = taskform.validate_stored(meta, row["params"])
            if valid is not None:
                params_rows = taskform.summary(fields, valid)
            if row["result"] is None:
                note = "no_result"
            else:
                try:
                    result_rows = flatten_result(meta.result.model_validate(row["result"]))
                except Exception:  # noqa: BLE001 - any mismatch: show nothing from it
                    note = "mismatch"
        elif row["result"] is not None:
            note = "mismatch"
        else:
            note = "no_result"
        blocked = await self._resume_blocked(view, meta, row) if view.state in RESUMABLE_STATES else None
        return RunDetail(
            run=view,
            meta=meta,
            params=params_rows,
            result=result_rows,
            result_note=note,
            events=shown,
            event_count=int(total_events),
            next_after=shown[-1].seq if len(events) > EVENTS_PER_PAGE and shown else None,
            checkpoints=int(checkpoints),
            can_cancel=view.active and view.cancel_requested_at is None,
            can_resume=view.state in RESUMABLE_STATES and blocked is None,
            resume_blocked=blocked,
        )

    async def _resume_blocked(self, view: RunView, meta: Optional[TaskMeta], row) -> Optional[str]:
        if meta is None:
            return Refusal.unknown_task.value
        try:
            run_id = uuid.UUID(view.id)
            async with self._engine.connect() as conn:
                return await self._resume_check(conn, meta, row, run_id)
        except Exception:  # noqa: BLE001 - a read problem only hides the button
            return Refusal.read_only.value

    async def _resume_check(self, conn, meta: TaskMeta, row, run_id) -> Optional[str]:
        if not meta.resumable:
            return Refusal.not_resumable.value
        if row["state"] not in RESUMABLE_STATES:
            return Refusal.not_eligible.value
        if meta.version != row["version"]:
            return Refusal.version_changed.value
        if taskform.validate_stored(meta, row["params"]) is None:
            return Refusal.stored_params.value
        active = (
            await conn.execute(
                text(
                    "SELECT 1 FROM tasks.runs WHERE resumes_run_id = :id "
                    "AND state IN ('queued','running') LIMIT 1"
                ),
                {"id": run_id},
            )
        ).first()
        if active is not None:
            return Refusal.resume_active.value
        if not meta.idempotent:
            done = (
                await conn.execute(
                    text(
                        "SELECT 1 FROM tasks.runs WHERE resumes_run_id = :id "
                        "AND state = 'succeeded' LIMIT 1"
                    ),
                    {"id": run_id},
                )
            ).first()
            if done is not None:
                return Refusal.already_resumed.value
        return None

    async def last_dry_run(self, meta: TaskMeta) -> Optional[RunView]:
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT * FROM tasks.runs WHERE task = :t AND version = :v AND dry_run "
                        "AND state = 'succeeded' ORDER BY finished_at DESC NULLS LAST LIMIT 1"
                    ),
                    {"t": meta.name, "v": meta.version},
                )
            ).mappings().first()
        return self._view(row) if row else None

    async def dry_run_for(self, meta: TaskMeta, params: Mapping[str, Any]) -> Optional[DryRunSummary]:
        """The latest succeeded dry run of this task and version with exactly
        these (canonical, validated) parameters, or None."""
        async with self._engine.connect() as conn:
            found = (
                await conn.execute(
                    text(
                        "SELECT id FROM tasks.runs WHERE task = :t AND version = :v "
                        "AND params_hash = :h AND dry_run AND state = 'succeeded' "
                        "ORDER BY finished_at DESC NULLS LAST, id LIMIT 1"
                    ),
                    {"t": meta.name, "v": meta.version, "h": signing.params_hash(dict(params))},
                )
            ).scalar_one_or_none()
        detail = await self.run_detail(found) if found is not None else None
        if detail is None:
            return None
        finished = detail.run.finished_at
        old = finished is None or self._clock.now() - finished > DRY_RUN_MAX_AGE
        return DryRunSummary(detail.run, detail.result, detail.result_note, old)

    async def _dry_run_ok(self, conn, meta: TaskMeta, params_hash: str) -> bool:
        """The condition the runner checks: a succeeded dry run of this task and
        version with the same params hash that finished before now and less than
        24 h ago. (The runner re-checks against the signed request time.)"""
        now = self._clock.now()
        found = (
            await conn.execute(
                text(
                    "SELECT 1 FROM tasks.runs WHERE task = :t AND version = :v "
                    "AND params_hash = :h AND dry_run AND state = 'succeeded' "
                    "AND finished_at > :since AND finished_at < :now LIMIT 1"
                ),
                {"t": meta.name, "v": meta.version, "h": params_hash,
                 "since": now - DRY_RUN_MAX_AGE, "now": now},
            )
        ).first()
        return found is not None

    async def prior_dry_run_exists(self, meta: TaskMeta, params: Mapping[str, Any]) -> bool:
        async with self._engine.connect() as conn:
            return await self._dry_run_ok(conn, meta, signing.params_hash(dict(params)))

    # -- writes ----------------------------------------------------------------------
    @staticmethod
    def _actor(session, ip, ua, rid) -> dict:
        return dict(
            actor_kind="admin", actor_email=session.email, session_id=session.id,
            ip=ip, ua=ua, request_id=rid,
        )

    @staticmethod
    async def _notify(conn, task: str, run_id, state: str, session, entry, dry_run: bool) -> None:
        """The mail to every admin (``tasks.run``), in the same transaction as the
        audit row. Dry runs and read-only runs are not mailed."""
        if dry_run:
            return
        await outbox.enqueue_notification(
            conn, "tasks.run",
            {"task": task, "run_id": str(run_id), "state": state, "actor": session.email},
            entry.seq, dedupe_key=f"tasks.run:{run_id}:{state}",
        )

    async def _insert(self, conn, request: signing.RunRequest) -> None:
        import json

        await conn.execute(
            text(
                "INSERT INTO tasks.runs (id, task, version, params, params_hash, dry_run, "
                "requested_by, requested_at, nonce, resumes_run_id, request_sig, sig_version) "
                "VALUES (:id, :task, :version, CAST(:params AS jsonb), :params_hash, :dry_run, "
                ":requested_by, :requested_at, :nonce, :resumes, :sig, :sigv)"
            ),
            {
                "id": request.id, "task": request.task, "version": request.version,
                "params": json.dumps(request.params), "params_hash": request.params_hash,
                "dry_run": request.dry_run, "requested_by": request.requested_by,
                "requested_at": request.requested_at, "nonce": request.nonce,
                "resumes": request.resumes_run_id, "sig": request.request_sig,
                "sigv": request.sig_version,
            },
        )

    async def request_run(
        self, session, meta: TaskMeta, params: Mapping[str, Any], dry_run: bool,
        ip: Optional[str], ua: Optional[str], rid: Optional[str],
    ) -> Started:
        """Queue a signed run and audit the request, atomically. ``params`` are the
        canonical (validated) params. A real run of a task that needs a prior dry
        run is refused unless a suitable one exists (checked inside the same
        transaction as the insert)."""
        canonical = dict(params)
        if len(signing.canonical_params(canonical)) > MAX_PARAMS_BYTES:
            return Started(refusal=Refusal.params_too_large)
        async with self._engine.connect() as conn:
            async with conn.begin():
                if (
                    meta.requires_prior_dry_run
                    and not dry_run
                    and not await self._dry_run_ok(conn, meta, signing.params_hash(canonical))
                ):
                    return Started(refusal=Refusal.dry_run_required)
                request = signing.RunRequest.create(
                    task=meta.name, version=meta.version, params=canonical, dry_run=dry_run,
                    requested_by=session.email, requested_at=self._clock.now(),
                )
                await self._insert(conn, request)
                entry = await audit.write(
                    conn, "task.run.requested", "task_run", str(request.id), None,
                    {"task": meta.name, "version": meta.version, "dry_run": dry_run,
                     "params": canonical},
                    "success",
                    detail={"run_id": str(request.id), "task": meta.name,
                            "version": meta.version, "dry_run": dry_run,
                            "requested_by": session.email,
                            "params_digest": request.params_hash[:16]},
                    **self._actor(session, ip, ua, rid),
                )
                await self._notify(conn, meta.name, request.id, "queued", session, entry, dry_run)
        return Started(run_id=request.id)

    async def request_cancel(
        self, session, run_id: uuid.UUID, ip: Optional[str], ua: Optional[str], rid: Optional[str]
    ) -> Started:
        async with self._engine.connect() as conn:
            async with conn.begin():
                row = await self._run_row(conn, run_id)
                if row is None:
                    return Started(refusal=Refusal.unknown_run)
                if row["state"] not in ACTIVE_STATES:
                    return Started(refusal=Refusal.not_active)
                if row["cancel_requested_at"] is not None:
                    return Started(run_id=run_id, already=True)
                updated = await conn.execute(
                    text(
                        "UPDATE tasks.runs SET cancel_requested_at = :now "
                        "WHERE id = :id AND cancel_requested_at IS NULL "
                        "AND state IN ('queued','running')"
                    ),
                    {"now": self._clock.now(), "id": run_id},
                )
                if updated.rowcount != 1:
                    return Started(run_id=run_id, already=True)
                entry = await audit.write(
                    conn, "task.run.cancel_requested", "task_run", str(run_id), None, None,
                    "success",
                    detail={"run_id": str(run_id), "task": row["task"],
                            "version": row["version"], "state": row["state"],
                            "dry_run": bool(row["dry_run"]), "requested_by": session.email},
                    **self._actor(session, ip, ua, rid),
                )
                await self._notify(
                    conn, row["task"], run_id, "cancel_requested", session, entry, bool(row["dry_run"])
                )
        return Started(run_id=run_id)

    async def resume_target(self, run_id: uuid.UUID) -> Optional[tuple[str, str]]:
        """``(task, params_hash)`` of a run (for the step-up binding)."""
        async with self._engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT task, params_hash FROM tasks.runs WHERE id = :id"), {"id": run_id}
                )
            ).first()
        return (row[0], row[1]) if row else None

    async def check_resume(self, run_id: uuid.UUID) -> Optional[str]:
        """A fixed refusal code when resuming ``run_id`` would be refused, else None."""
        async with self._engine.connect() as conn:
            row = await self._run_row(conn, run_id)
            if row is None:
                return Refusal.unknown_run.value
            meta = self.meta(row["task"])
            if meta is None:
                return Refusal.unknown_task.value
            return await self._resume_check(conn, meta, row, run_id)

    async def request_resume(
        self, session, run_id: uuid.UUID, ip: Optional[str], ua: Optional[str], rid: Optional[str]
    ) -> Started:
        async with self._engine.connect() as conn:
            async with conn.begin():
                row = await self._run_row(conn, run_id)
                if row is None:
                    return Started(refusal=Refusal.unknown_run)
                meta = self.meta(row["task"])
                if meta is None:
                    return Started(refusal=Refusal.unknown_task)
                blocked = await self._resume_check(conn, meta, row, run_id)
                if blocked is not None:
                    return Started(refusal=Refusal(blocked))
                params = taskform.validate_stored(meta, row["params"])
                dry_run = bool(row["dry_run"])
                canonical = signing.params_hash(params)
                if (
                    meta.requires_prior_dry_run
                    and not dry_run
                    and not await self._dry_run_ok(conn, meta, canonical)
                ):
                    return Started(refusal=Refusal.dry_run_required)
                request = signing.RunRequest.create(
                    task=meta.name, version=meta.version, params=params, dry_run=dry_run,
                    requested_by=session.email, requested_at=self._clock.now(),
                    resumes_run_id=run_id,
                )
                await self._insert(conn, request)
                entry = await audit.write(
                    conn, "task.run.requested", "task_run", str(request.id), None,
                    {"task": meta.name, "version": meta.version, "dry_run": dry_run,
                     "params": params},
                    "success",
                    detail={"run_id": str(request.id), "task": meta.name,
                            "version": meta.version, "dry_run": dry_run,
                            "requested_by": session.email, "resumes_run_id": str(run_id),
                            "params_digest": request.params_hash[:16]},
                    **self._actor(session, ip, ua, rid),
                )
                await self._notify(conn, meta.name, request.id, "queued", session, entry, dry_run)
        return Started(run_id=request.id)
