"""``python -m backend.jobs.schema`` scrubs the action jobs that 4.1.x queued with
a whole run in them (the decrypted response, the responder's address, the
action's secrets), in any status: finished ones are deleted, waiting or running
ones are rewritten to ids and a run token, so the run still happens. Idempotent,
counts only in the log. Real database, as in test_executor_role.py."""

from __future__ import annotations

import json

import pytest
from loguru import logger

from backend.app.services.action_run_token import VALID, check_run_token
from backend.jobs.legacy import run, scrub_legacy_action_jobs
from common.db.flags import JobsBackend
from tests.app.jobs.test_executor_role import db  # noqa: F401 - fixture
from tests.app.jobs.test_executor_role import pytestmark  # noqa: F401

ANSWER = "THE-ANSWER-42"
SECRET = "an-action-secret"


def legacy_args(n: int) -> dict:
    return {
        "action": json.dumps({"id": f"a{n}", "secrets": [{"value": SECRET}]}),
        "form": json.dumps({"form_id": f"f{n}"}),
        "response": json.dumps(
            {"response_id": f"r{n}", "answers": {"q": ANSWER}}
        ),
        "user_email": "responder@example.org",
        "workspace": json.dumps({"id": f"w{n}", "secrets": {f"a{n}": SECRET}}),
    }


async def _insert(db, status, args, task="run_action", queue="actions"):
    conn = await db.connect("app")
    try:
        row = await (
            await conn.execute(
                "INSERT INTO jobs.procrastinate_jobs (queue_name, task_name, args, status)"
                " VALUES (%s, %s, %s::jsonb, %s::jobs.procrastinate_job_status)"
                " RETURNING id",
                (queue, task, json.dumps(args), status),
            )
        ).fetchone()
        return row[0]
    finally:
        await conn.close()


async def _rows(db):
    conn = await db.connect("app")
    try:
        return await (
            await conn.execute(
                "SELECT id, status::text, args FROM jobs.procrastinate_jobs ORDER BY id"
            )
        ).fetchall()
    finally:
        await conn.close()


async def _scrub(db):
    app = db.queue_app("app")
    async with app.open_async():
        return await scrub_legacy_action_jobs(app)


async def test_rows_in_every_status_lose_the_response_data(db):
    ids = {}
    for n, status in enumerate(
        ["succeeded", "failed", "cancelled", "aborted", "todo", "doing"]
    ):
        ids[status] = await _insert(db, status, legacy_args(n))

    counts = await _scrub(db)

    assert counts == {"deleted": 4, "rewritten": 2, "left": 0}
    rows = {row[0]: row for row in await _rows(db)}
    assert set(rows) == {ids["todo"], ids["doing"]}  # the over ones are gone
    for status, n in (("todo", 4), ("doing", 5)):
        _, row_status, args = rows[ids[status]]
        assert row_status == status
        assert set(args) == {
            "action_id", "form_id", "response_id", "workspace_id", "run_token"
        }
        assert (args["action_id"], args["form_id"], args["response_id"]) == (
            f"a{n}", f"f{n}", f"r{n}"
        )
        assert args["workspace_id"] == f"w{n}"
        assert check_run_token(
            args["run_token"], f"w{n}", f"f{n}", f"a{n}", f"r{n}"
        ) == VALID
    everything = json.dumps([list(map(str, r)) for r in await _rows(db)])
    for content in (ANSWER, SECRET, "responder@example.org"):
        assert content not in everything


async def test_it_is_idempotent_and_leaves_current_jobs_and_other_queues_alone(db):
    current = {
        "action_id": "a",
        "form_id": "f",
        "response_id": "r",
        "workspace_id": "w",
        "run_token": "9.x",
    }
    keep_current = await _insert(db, "todo", current)
    other = await _insert(
        db, "todo", {"response": "kept"}, task="delete_user", queue="default"
    )
    await _insert(db, "todo", legacy_args(1))

    first = await _scrub(db)
    after_first = await _rows(db)
    second = await _scrub(db)

    assert first == {"deleted": 0, "rewritten": 1, "left": 0}
    assert second == {"deleted": 0, "rewritten": 0, "left": 0}
    assert await _rows(db) == after_first
    by_id = {row[0]: row for row in after_first}
    assert by_id[keep_current][2] == current
    assert by_id[other][2] == {"response": "kept"}


async def test_a_waiting_job_whose_ids_cannot_be_read_is_deleted_not_run(db):
    broken = await _insert(
        db, "todo", {**legacy_args(1), "response": "not json THE-ANSWER-42"}
    )
    counts = await _scrub(db)
    assert counts == {"deleted": 1, "rewritten": 0, "left": 0}
    assert broken not in [row[0] for row in await _rows(db)]


async def test_without_a_token_key_a_waiting_job_is_left_and_counted(db, monkeypatch):
    def no_key(*args, **kwargs):
        raise RuntimeError("no identity key here")

    monkeypatch.setattr("backend.jobs.legacy.run_token", no_key)
    await _insert(db, "succeeded", legacy_args(1))
    waiting = await _insert(db, "todo", legacy_args(2))

    counts = await _scrub(db)

    assert counts == {"deleted": 1, "rewritten": 0, "left": 1}
    assert [row[0] for row in await _rows(db)] == [waiting]


async def test_it_works_in_batches(db, monkeypatch):
    monkeypatch.setattr("backend.jobs.legacy.BATCH", 3)
    for n in range(8):
        await _insert(db, "succeeded" if n % 2 else "todo", legacy_args(n))
    assert await _scrub(db) == {"deleted": 4, "rewritten": 4, "left": 0}


async def test_the_log_holds_counts_only(db):
    await _insert(db, "succeeded", legacy_args(1))
    await _insert(db, "todo", legacy_args(2))
    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    try:
        app = db.queue_app("app")
        async with app.open_async():
            await run(app)
    finally:
        logger.remove(sink)
    text = "".join(lines)
    assert "1 deleted, 1 rewritten" in text
    for content in (ANSWER, SECRET, "responder@example.org", "r1", "a2", "w2"):
        assert content not in text


# -- at the backend's startup, with DB_AUTO_MIGRATE on ------------------------------
# A stack that upgrades by swapping images never runs ``python -m
# backend.jobs.schema``; the backend's startup scrubs instead.


class _Flags:
    def __init__(self, backend):
        self.backend = backend

    def jobs_backend(self, job):
        return self.backend


class _Engine:
    def __init__(self, url):
        from sqlalchemy.engine import make_url

        self.url = make_url(url)


async def _startup_scrub(db, env, backend=JobsBackend.POSTGRES):
    from backend.db.startup import scrub_legacy_action_jobs

    await scrub_legacy_action_jobs(_Flags(backend), _Engine(db.url("app")), env=env)


async def test_the_backend_start_scrubs_when_it_migrates(db):
    await _insert(db, "succeeded", legacy_args(1))
    waiting = await _insert(db, "todo", legacy_args(2))

    await _startup_scrub(db, {"DB_AUTO_MIGRATE": "true"})

    rows = await _rows(db)
    assert [row[0] for row in rows] == [waiting]
    assert "response" not in rows[0][2] and "run_token" in rows[0][2]


@pytest.mark.parametrize(
    "env, backend",
    [({}, JobsBackend.POSTGRES), ({"DB_AUTO_MIGRATE": "true"}, JobsBackend.TEMPORAL)],
    ids=["no-auto-migrate", "no-postgres-jobs"],
)
async def test_the_backend_start_leaves_the_queue_alone_otherwise(db, env, backend):
    await _insert(db, "succeeded", legacy_args(1))
    before = await _rows(db)
    await _startup_scrub(db, env, backend)
    assert await _rows(db) == before


async def test_a_failed_scrub_at_startup_is_logged_and_the_start_goes_on(
    db, monkeypatch
):
    async def broken(url):
        raise RuntimeError(f"cannot reach {url}")

    monkeypatch.setattr("backend.db.startup.scrub_at", broken)
    lines = []
    sink = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    try:
        await _startup_scrub(db, {"DB_AUTO_MIGRATE": "true"})
    finally:
        logger.remove(sink)
    text = "".join(lines)
    assert "scrub at startup failed (RuntimeError)" in text
    assert "cannot reach" not in text  # no URL, no credentials in the log
