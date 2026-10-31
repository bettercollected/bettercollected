"""No job argument reaches a log line. procrastinate prints a job's
``call_string`` (every argument) when it starts, ends or fails for good, and the
arguments in the record's ``job`` extra."""

import logging

import pytest
from procrastinate import App
from procrastinate.testing import InMemoryConnector

import backend.jobs.app  # noqa: F401 - installs the log safety on import

MARKER = "THE-ANSWER-42-in-a-job-argument"


@pytest.mark.parametrize("fail", [False, True])
async def test_a_job_that_runs_or_fails_for_good_logs_no_argument(caplog, fail):
    app = App(connector=InMemoryConnector())

    @app.task(name="leaky", queue="actions")
    async def leaky(**kwargs):
        if fail:
            raise RuntimeError("failed")

    async with app.open_async():
        await app.configure_task(name="leaky", queue="actions").defer_async(
            response=MARKER, run_token="9.secret-token", answers={"q": MARKER}
        )
        with caplog.at_level(logging.DEBUG):
            await app.run_worker_async(wait=False, install_signal_handlers=False)

    assert caplog.records, "the worker logged nothing: the test proves nothing"
    for record in caplog.records:
        everything = " ".join(
            [record.getMessage(), str(record.__dict__), record.exc_text or ""]
        )
        assert MARKER not in everything, record.getMessage()
        assert "secret-token" not in everything, record.getMessage()
    # the call is still recognisable: task name and job id
    assert any("leaky[" in record.getMessage() for record in caplog.records)
