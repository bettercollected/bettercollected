"""Keep a job's arguments out of the logs.

procrastinate prints ``Job run_action[7](action_id='…', run_token='…')`` (the
job's ``call_string``, with every argument) at start, at the end and, for a job
that fails for good, at ERROR with the traceback, and puts the arguments in the
record's ``job`` extra too. What the arguments hold varies by job (sealed
values, ids, run tokens, and for jobs queued by 4.1.x a whole response), and a
log line outlives the queue's retention. So the call string is cut to the task
name and the job id, the ``task_kwargs`` are dropped from the log context, and
a filter on procrastinate's loggers removes them from any record that still
carries them.

Applied when ``backend.jobs.app`` is imported, so every process that uses the
queue (the API, the jobs worker, the executor's copy in
``temporal/actions-executor/utilities/job_logging.py``) has it.
"""

from __future__ import annotations

import logging

from procrastinate import jobs

LOGGERS = ("procrastinate", "procrastinate.worker", "procrastinate.periodic")
_MARK = "_bc_job_args_scrubbed"


def _call_string(self) -> str:
    return f"{self.task_name}[{self.id}]"


def _log_context(self) -> dict:
    context = self.asdict()
    if context.get("scheduled_at"):
        context["scheduled_at"] = context["scheduled_at"].isoformat()
    context.pop("task_kwargs", None)
    context["call_string"] = self.call_string
    return context


class DropJobArguments(logging.Filter):
    """Removes ``task_kwargs`` from a record's ``job`` extra (belt and braces:
    ``log_context`` no longer adds them)."""

    def filter(self, record: logging.LogRecord) -> bool:
        job = getattr(record, "job", None)
        if isinstance(job, dict) and "task_kwargs" in job:
            record.job = {k: v for k, v in job.items() if k != "task_kwargs"}
        return True


def scrub_job_logging() -> None:
    """Idempotent."""
    if getattr(jobs.Job, _MARK, False):
        return
    jobs.Job.call_string = property(_call_string)
    jobs.Job.log_context = _log_context
    setattr(jobs.Job, _MARK, True)
    for name in LOGGERS:
        logging.getLogger(name).addFilter(DropJobArguments())
