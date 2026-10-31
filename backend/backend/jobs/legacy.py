"""Scrub the action jobs that earlier releases queued with a whole run in them.

4.1.x wrote the run's action, form, **decrypted response**, the responder's
address and the workspace (with the action's stored secrets) into the job's
arguments, and kept the row. This removes that data from the ``actions`` queue,
in any status:

* a job that is over (succeeded, failed, cancelled, aborted): deleted, with its
  events;
* a job that has not finished (``todo``, ``doing``): its arguments are replaced
  by what a job carries now (ids and a run token), so the run still happens and
  reads its data when it runs. If its ids cannot be read, or the token cannot be
  made (no identity key in this process), the job is deleted and counted, or left
  and counted: never run with data in it.

Idempotent (a second run finds nothing), in small batches, safe to run on every
deploy (``python -m backend.jobs.schema`` does). It logs and returns counts only,
never an id, argument or value.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger
from procrastinate import App

from backend.app.services.action_run_token import run_token
from backend.jobs.app import ACTIONS_QUEUE

BATCH = 200
#: argument names of a whole-run job; the current shape has none of them
LEGACY_KEYS = ("action", "form", "response", "workspace", "user_email")
FINISHED = ("succeeded", "failed", "cancelled", "aborted")

_SELECT = f"""
SELECT id, status, args FROM jobs.procrastinate_jobs
 WHERE queue_name = %(queue)s AND task_name = 'run_action'
   AND ({" OR ".join(f"args ? '{key}'" for key in LEGACY_KEYS)})
 ORDER BY id LIMIT %(limit)s
"""


def _ids_of(args: dict[str, Any]) -> Optional[dict[str, str]]:
    """The four ids a whole-run job names, or None when they cannot be read."""
    try:
        action = json.loads(args["action"])
        form = json.loads(args["form"])
        response = json.loads(args["response"])
        workspace = json.loads(args["workspace"])
        ids = {
            "action_id": action["id"],
            "form_id": form["form_id"],
            "response_id": response["response_id"],
            "workspace_id": workspace["id"],
        }
    except (KeyError, TypeError, ValueError):
        return None
    if not all(isinstance(value, str) and value for value in ids.values()):
        return None
    return ids


def _scrubbed_args(args: dict[str, Any]) -> Optional[dict[str, str]]:
    ids = _ids_of(args)
    if ids is None:
        return None
    try:
        token = run_token(
            ids["workspace_id"], ids["form_id"], ids["action_id"], ids["response_id"]
        )
    except Exception:  # noqa: BLE001 - no identity key here: leave the job, count it
        return None
    return {**ids, "run_token": token}


async def scrub_legacy_action_jobs(jobs_app: App) -> dict[str, int]:
    """Counts: ``deleted`` (over, or unreadable), ``rewritten`` (waiting or
    running, now ids only), ``left`` (needed a token this process could not
    make). The app must be open."""
    connector = jobs_app.connector
    counts = {"deleted": 0, "rewritten": 0, "left": 0}
    skip: set[int] = set()
    while True:
        rows = [
            row
            for row in await connector.execute_query_all_async(
                _SELECT, queue=ACTIONS_QUEUE, limit=BATCH + len(skip)
            )
            if row["id"] not in skip
        ][:BATCH]
        if not rows:
            return counts
        delete: list[int] = []
        for row in rows:
            args = row["args"] if isinstance(row["args"], dict) else json.loads(row["args"])
            if row["status"] in FINISHED:
                delete.append(row["id"])
                continue
            new_args = _scrubbed_args(args)
            if new_args is not None:
                await connector.execute_query_async(
                    "UPDATE jobs.procrastinate_jobs SET args = %(args)s::jsonb"
                    " WHERE id = %(id)s",
                    args=json.dumps(new_args),
                    id=row["id"],
                )
                counts["rewritten"] += 1
            elif _ids_of(args) is None:
                delete.append(row["id"])  # never run, and it holds data
            else:
                skip.add(row["id"])
                counts["left"] += 1
        if delete:
            await connector.execute_query_async(
                "DELETE FROM jobs.procrastinate_jobs WHERE id = ANY(%(ids)s)",
                ids=delete,
            )
            counts["deleted"] += len(delete)


async def run(jobs_app: App) -> dict[str, int]:
    counts = await scrub_legacy_action_jobs(jobs_app)
    logger.info(
        "legacy action jobs scrubbed: {} deleted, {} rewritten to ids only, {} left",
        counts["deleted"],
        counts["rewritten"],
        counts["left"],
    )
    if counts["left"]:
        logger.warning(
            "{} waiting action jobs still carry response data: run this again "
            "where the respondent identity key is configured",
            counts["left"],
        )
    return counts
