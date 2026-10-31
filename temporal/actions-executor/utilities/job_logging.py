"""Keep a job's arguments out of the executor's logs (a copy of
``backend/backend/jobs/log_safety.py``, which explains why; the executor has its
own environment). procrastinate logs a job's ``call_string``, with every
argument, at start, at the end and at ERROR for a job that fails for good."""

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
    def filter(self, record: logging.LogRecord) -> bool:
        job = getattr(record, "job", None)
        if isinstance(job, dict) and "task_kwargs" in job:
            record.job = {k: v for k, v in job.items() if k != "task_kwargs"}
        return True


def scrub_job_logging() -> None:
    if getattr(jobs.Job, _MARK, False):
        return
    jobs.Job.call_string = property(_call_string)
    jobs.Job.log_context = _log_context
    setattr(jobs.Job, _MARK, True)
    for name in LOGGERS:
        logging.getLogger(name).addFilter(DropJobArguments())
