"""The queued ``run_action`` job: ids in, the run's data fetched from the backend
when it runs, retries with a growing wait, a time limit, and failures that name
ids and the kind of error and never a message (which can hold an answer)."""

import asyncio
import datetime as dt
from types import SimpleNamespace

import httpx
import pytest

import procrastinate_worker as worker
from utilities import run_context
from utilities.run_context import RunContextUnavailable, context_url, fetch_run_context

IDS = dict(
    workspace_id="w1", form_id="f1", action_id="a1", response_id="r1"
)
RUN_TOKEN = "t0k3n-of-this-run"
JOB = dict(**IDS, run_token=RUN_TOKEN)
CONTEXT = {
    "action": '{"id": "a1"}',
    "form": '{"form_id": "f1"}',
    "response": '{"answers": {"q": "THE-ANSWER"}}',
    "workspace": '{"id": "w1"}',
    "user_email": "responder@example.org",
}


def job(**kwargs):
    return asyncio.run(worker.run_action_job.func(**kwargs))


@pytest.fixture
def ran(monkeypatch):
    calls = []

    async def fake_run_action(**kwargs):
        calls.append(kwargs)
        return {"status": True, "log": "creator log THE-ANSWER"}

    monkeypatch.setattr(worker, "run_action", fake_run_action)
    return calls


def serve(monkeypatch, context):
    async def fetch(workspace_id, form_id, action_id, response_id, run_token):
        return context

    monkeypatch.setattr(worker, "fetch_run_context", fetch)


def test_a_run_is_fetched_by_ids_then_run(monkeypatch, ran):
    serve(monkeypatch, CONTEXT)
    assert job(**JOB) == "ok"
    assert ran == [
        dict(
            action=CONTEXT["action"],
            form=CONTEXT["form"],
            response=CONTEXT["response"],
            user_email="responder@example.org",
            workspace=CONTEXT["workspace"],
        )
    ]


def test_the_job_returns_no_run_data(monkeypatch, ran):
    """The worker logs a job's result: it must be a word, not the run's log."""
    serve(monkeypatch, CONTEXT)
    assert job(**JOB) == "ok"


def test_a_run_that_no_longer_applies_is_skipped_not_retried(monkeypatch, ran):
    serve(monkeypatch, None)
    assert job(**JOB) == "skipped"
    assert ran == []


def test_an_unreachable_backend_fails_the_attempt_so_it_is_retried(monkeypatch, ran):
    async def down(*args):
        raise RunContextUnavailable("the backend answered 503")

    monkeypatch.setattr(worker, "fetch_run_context", down)
    with pytest.raises(worker.ActionRunFailed) as failed:
        job(**JOB)
    assert "503" in str(failed.value) and ran == []


def test_a_failure_never_carries_the_message_of_the_code_that_failed(
    monkeypatch,
):
    serve(monkeypatch, CONTEXT)

    async def failing(**kwargs):
        raise RuntimeError("could not send THE-ANSWER to responder@example.org")

    monkeypatch.setattr(worker, "run_action", failing)
    with pytest.raises(worker.ActionRunFailed) as failed:
        job(**JOB)
    text = str(failed.value)
    assert "RuntimeError" in text and "a1" in text and "f1" in text
    assert "THE-ANSWER" not in text and "responder@example.org" not in text
    assert failed.value.__cause__ is None and failed.value.__suppress_context__


def test_a_run_is_cut_off_at_the_time_limit(monkeypatch):
    serve(monkeypatch, CONTEXT)
    monkeypatch.setattr(worker, "RUN_TIMEOUT_SECONDS", 0.05)

    async def stuck(**kwargs):
        await asyncio.sleep(5)

    monkeypatch.setattr(worker, "run_action", stuck)
    with pytest.raises(worker.ActionRunFailed) as failed:
        job(**JOB)
    assert "TimeoutError" in str(failed.value)


def test_a_job_queued_before_the_change_still_runs_once(monkeypatch, ran):
    async def never(*args):
        raise AssertionError("a legacy job has its data; no fetch")

    monkeypatch.setattr(worker, "fetch_run_context", never)
    assert (
        job(
            action='{"id": "a1"}',
            form="{}",
            response="{}",
            user_email="e@example.org",
            workspace="{}",
        )
        == "ok"
    )
    assert ran[0]["user_email"] == "e@example.org"


def test_retries_grow_in_wait_and_stop_after_three_attempts():
    strategy = worker.run_action_job.retry_strategy
    assert strategy.max_attempts == worker.MAX_RUNS - 1  # retries, not runs
    waits = []
    for attempts in (0, 1):
        decision = strategy.get_retry_decision(
            exception=Exception(), job=SimpleNamespace(attempts=attempts)
        )
        delay = decision.retry_at - dt.datetime.now(dt.timezone.utc)
        waits.append(round(delay.total_seconds()))
    assert waits == [5, 25]
    assert (
        strategy.get_retry_decision(
            exception=Exception(), job=SimpleNamespace(attempts=2)
        )
        is None
    )


def test_the_task_is_on_the_actions_queue_only():
    assert worker.run_action_job.name == "run_action"
    assert worker.run_action_job.queue == worker.ACTIONS_QUEUE == "actions"


# fetch_run_context -----------------------------------------------------------------


def with_backend(monkeypatch, handler):
    real = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(run_context.httpx, "AsyncClient", client)


def test_context_is_asked_in_network_with_the_job_key_and_returned(monkeypatch):
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["method"] = request.method
        seen["key"] = request.headers.get("api-key")
        seen["token"] = request.headers.get("run-token")
        return httpx.Response(200, json=CONTEXT)

    monkeypatch.setattr(run_context.settings, "api_key", "job-key")
    with_backend(monkeypatch, handler)
    got = asyncio.run(fetch_run_context(**IDS, run_token=RUN_TOKEN))
    assert got == CONTEXT
    assert seen["method"] == "POST" and seen["key"] == "job-key"
    assert seen["token"] == RUN_TOKEN
    assert seen["url"].endswith(
        "/temporal/workspaces/w1/forms/f1/actions/a1/runs/r1/context"
    )


def test_410_means_the_run_no_longer_applies(monkeypatch):
    with_backend(monkeypatch, lambda request: httpx.Response(410, json={}))
    assert asyncio.run(fetch_run_context(**IDS, run_token=RUN_TOKEN)) is None


@pytest.mark.parametrize("status", [401, 403, 404, 500, 503])
def test_any_other_answer_is_unavailable_and_says_only_the_status(
    monkeypatch, status
):
    with_backend(
        monkeypatch, lambda request: httpx.Response(status, text="THE-ANSWER body")
    )
    with pytest.raises(RunContextUnavailable) as failed:
        asyncio.run(fetch_run_context(**IDS, run_token=RUN_TOKEN))
    assert str(status) in str(failed.value) and "THE-ANSWER" not in str(failed.value)


def test_a_network_error_is_unavailable(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("refused for http://backend/secret-path")

    with_backend(monkeypatch, handler)
    with pytest.raises(RunContextUnavailable) as failed:
        asyncio.run(fetch_run_context(**IDS, run_token=RUN_TOKEN))
    assert str(failed.value) == "ConnectError"


@pytest.mark.parametrize(
    "body",
    [
        ["not", "a", "dict"],
        {**CONTEXT, "response": None},
        {k: v for k, v in CONTEXT.items() if k != "workspace"},
    ],
)
def test_an_incomplete_answer_is_unavailable(monkeypatch, body):
    with_backend(monkeypatch, lambda request: httpx.Response(200, json=body))
    with pytest.raises(RunContextUnavailable):
        asyncio.run(fetch_run_context(**IDS, run_token=RUN_TOKEN))


@pytest.mark.parametrize("token", [None, ""])
def test_a_job_without_a_run_token_is_not_asked_for(monkeypatch, token):
    asked = []
    with_backend(monkeypatch, lambda request: asked.append(request) or httpx.Response(200))
    with pytest.raises(RunContextUnavailable):
        asyncio.run(fetch_run_context(**IDS, run_token=token))
    assert asked == []


def test_ids_are_one_path_segment_each():
    url = context_url("w/../x", "f?a=b", "a#1", "r 1")
    assert "/../" not in url and "?" not in url and "#" not in url
    with pytest.raises(RunContextUnavailable):
        context_url("w1", "", "a1", "r1")
