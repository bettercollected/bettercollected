"""Counters of what went wrong in this process, for the operator's status view.

A submission whose action run could not be queued is stored and is not run
(there is no later re-queueing): the error log carries the event name
``action_run_not_queued`` with ids, and this count (since the process started)
is shown by ``GET /persistence/status``. Per process, not durable: the log line
is the record.
"""

_counts = {"action_runs_not_queued": 0}


def action_run_not_queued() -> None:
    _counts["action_runs_not_queued"] += 1


def snapshot() -> dict:
    return dict(_counts)
