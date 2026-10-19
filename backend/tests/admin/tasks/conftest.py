"""Fixtures for the task runner's database tests.

``world`` wires a migrated throw-away database the way production does: the
admin role enqueues signed requests, the runner role (``bc_tasks``) runs them,
the owner role is used only to inspect. A ``FakeClock`` drives leases.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import pytest
import pytest_asyncio
from sqlalchemy import text

from backend.admin.security.clock import FakeClock
from backend.admin.tasks import signing
from backend.admin.tasks.impl import build_registry
from backend.admin.tasks.impl import selftest_slow as slow_impl
from backend.admin.tasks.runner.runner import Runner

AT = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset_selftest_state():
    slow_impl.WORLD.clear()
    slow_impl.HOOKS.__dict__.clear()
    yield
    slow_impl.WORLD.clear()
    slow_impl.HOOKS.__dict__.clear()


@dataclass
class World:
    admin: Any  # bc_admin engine
    tasks: Any  # bc_tasks engine
    owner: Any  # migration role, for inspection
    clock: FakeClock
    registry: Any

    def runner(self, **kw) -> Runner:
        kw.setdefault("heartbeat_seconds", None)
        kw.setdefault("finish_retry_delays", (0, 0))
        return Runner(self.tasks, self.registry, clock=self.clock, **kw)

    async def enqueue(
        self,
        task: str = "selftest",
        params: Optional[dict] = None,
        *,
        version: int = 1,
        dry_run: bool = False,
        resumes: Optional[uuid.UUID] = None,
        requested_by: str = "ops@example.org",
        tamper: Optional[dict] = None,
        sign_params: Optional[dict] = None,
        requested_at: Optional[datetime] = None,
    ) -> uuid.UUID:
        """Insert a signed request as the admin role. ``tamper`` overrides stored
        columns after signing; ``sign_params`` signs different params than stored."""
        params = params or {}
        request = signing.RunRequest.create(
            task=task,
            version=version,
            params=sign_params if sign_params is not None else params,
            dry_run=dry_run,
            requested_by=requested_by,
            requested_at=requested_at or AT,
            resumes_run_id=resumes,
        )
        values = {
            "id": request.id,
            "task": request.task,
            "version": request.version,
            "params": json.dumps(params),
            "params_hash": request.params_hash,
            "dry_run": request.dry_run,
            "requested_by": request.requested_by,
            "requested_at": request.requested_at,
            "nonce": request.nonce,
            "resumes": resumes,
            "sig": request.request_sig,
            "sigv": request.sig_version,
        }
        for key, value in (tamper or {}).items():
            values[key] = value
        async with self.admin.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO tasks.runs (id, task, version, params, params_hash, dry_run, "
                    "requested_by, requested_at, nonce, resumes_run_id, request_sig, sig_version) "
                    "VALUES (:id, :task, :version, CAST(:params AS jsonb), :params_hash, "
                    ":dry_run, :requested_by, :requested_at, :nonce, :resumes, :sig, :sigv)"
                ),
                values,
            )
        return request.id

    async def cancel(self, run_id) -> None:
        async with self.admin.begin() as conn:
            await conn.execute(
                text("UPDATE tasks.runs SET cancel_requested_at = now() WHERE id = :id"),
                {"id": run_id},
            )

    async def run(self, run_id) -> dict:
        async with self.owner.connect() as conn:
            row = (
                await conn.execute(text("SELECT * FROM tasks.runs WHERE id = :id"), {"id": run_id})
            ).mappings().one()
        return dict(row)

    async def events(self, run_id) -> list[dict]:
        async with self.owner.connect() as conn:
            rows = await conn.execute(
                text("SELECT seq, code, counts, ids, error_class FROM tasks.run_events "
                     "WHERE run_id = :id ORDER BY seq"),
                {"id": run_id},
            )
            return [dict(r) for r in rows.mappings()]

    async def locks(self) -> list[str]:
        async with self.owner.connect() as conn:
            return list((await conn.execute(text("SELECT name FROM tasks.locks ORDER BY 1"))).scalars())

    async def audit_rows(self, action: Optional[str] = None) -> list[dict]:
        sql = "SELECT * FROM admin.audit_log"
        params: dict = {}
        if action:
            sql += " WHERE action = :a"
            params["a"] = action
        async with self.owner.connect() as conn:
            rows = await conn.execute(text(sql + " ORDER BY seq"), params)
            return [dict(r) for r in rows.mappings()]

    async def drain(self, runner: Optional[Runner] = None) -> int:
        runner = runner or self.runner()
        n = 0
        while await runner.run_once():
            n += 1
        return n


@pytest_asyncio.fixture(loop_scope="session")
async def world(server, migrated, runtime_engine, tasks_engine, owner_engine, monkeypatch):
    monkeypatch.setenv("ADMIN_TASKS_SELFTEST", "1")
    return World(
        admin=runtime_engine,
        tasks=tasks_engine,
        owner=owner_engine,
        clock=FakeClock(AT.timestamp() + 60),
        registry=build_registry(),
    )
