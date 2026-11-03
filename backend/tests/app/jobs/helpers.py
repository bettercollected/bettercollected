"""Running the job worker inside a test."""

from unittest.mock import patch

from backend.jobs.app import app


async def run_worker() -> None:
    """Run the app's worker once over the in-memory queue, until no job is due.

    The app's periodic tasks are left out. The worker's periodic deferrer reads
    the wall clock: a cron tick that falls between two runs of a test makes it
    defer a new job into the in-memory connector, which then cannot notify the
    listener of the earlier run (the connector was never opened, so it has no
    loop to notify on). The deferrer fails, the worker stops at once and the
    job under test is left ``todo``. Without periodic tasks the deferrer has
    nothing to defer and a run does exactly what the test queued.
    """
    with patch.object(app.periodic_registry, "periodic_tasks", {}):
        await app.run_worker_async(wait=False, install_signal_handlers=False)
