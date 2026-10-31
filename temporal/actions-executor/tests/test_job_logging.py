"""The executor's logs hold no job argument: procrastinate prints a job's
``call_string`` (every argument) at start, at the end and at ERROR when a job
fails for good."""

import asyncio
import logging

import pytest
from procrastinate import App
from procrastinate.testing import InMemoryConnector

import procrastinate_worker  # noqa: F401 - installs the log safety on import

MARKER = "THE-ANSWER-42-in-a-job-argument"


@pytest.mark.parametrize("fail", [False, True])
def test_a_job_that_runs_or_fails_for_good_logs_no_argument(caplog, fail):
    app = App(connector=InMemoryConnector())

    @app.task(name="leaky", queue="actions")
    async def leaky(**kwargs):
        if fail:
            raise RuntimeError("failed")

    async def go():
        async with app.open_async():
            await app.configure_task(name="leaky", queue="actions").defer_async(
                response=MARKER, run_token="9.secret-token"
            )
            with caplog.at_level(logging.DEBUG):
                await app.run_worker_async(wait=False, install_signal_handlers=False)

    asyncio.run(go())

    assert caplog.records
    for record in caplog.records:
        everything = " ".join(
            [record.getMessage(), str(record.__dict__), record.exc_text or ""]
        )
        assert MARKER not in everything and "secret-token" not in everything
    assert any("leaky[" in record.getMessage() for record in caplog.records)
