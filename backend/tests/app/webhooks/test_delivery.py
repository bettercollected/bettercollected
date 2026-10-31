"""Delivery end to end: a submission writes one log row per enabled webhook and
queues one job each (log id only) on the ``webhooks`` queue; the job decrypts
the answers, reduces them to the mapped questions and sends a signed body; a
failure retries with exponential backoff and jitter and ends visible; nothing
secret or personal reaches logs, job arguments or log rows."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from common.clock import utcnow
from loguru import logger

from backend.app.container import container
from backend.app.schemas.webhook import LogStatus
from backend.app.services.registration import client
from backend.app.services.webhooks import payload, retry, sender
from backend.app.services.webhooks.service import MAX_ATTEMPTS
from backend.config import settings
from backend.jobs import tasks
from tests.app.registration.helpers import ANSWERS, publish, submit
from tests.app.registration.tls_server import PUBLIC_ADDRESS
from tests.app.webhooks.helpers import URL, logs_of, make_webhook

pytestmark = pytest.mark.asyncio

PERSONAL = ["Ada Example", "ada@example.test", "Synthetic story.", "1990-01-02"]


@pytest.fixture()
def lines():
    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    yield seen
    logger.remove(handler)


@pytest.fixture()
async def setup(workspace, webhooks_on, memory_jobs, tls):
    form = await publish(workspace)
    hook = await make_webhook(workspace, form, ["name", "age", "colours", "people"])
    return SimpleNamespace(
        workspace=workspace, form=form, hook=hook, jobs=memory_jobs, tls=tls
    )


async def log_of(setup, response):
    (row,) = [r for r in await logs_of(setup.form) if r.response_id == response.response_id]
    return row


async def run(log, attempt=0):
    return await container.webhook_service().run_delivery(str(log.id), job_attempt=attempt)


async def test_submission_queues_one_job_per_enabled_webhook_with_the_log_id_only(setup, lines):
    second = await make_webhook(setup.workspace, setup.form, ["name"])
    await make_webhook(setup.workspace, setup.form, ["name"], enabled=False)
    response = await submit(setup.workspace, setup.form)
    rows = [r for r in await logs_of(setup.form) if r.response_id == response.response_id]
    assert sorted(r.action_id for r in rows) == sorted([setup.hook.id, second.id])
    assert all(r.status is LogStatus.PENDING and r.attempts == 0 for r in rows)
    jobs = list(setup.jobs.jobs.values())
    assert len(jobs) == 2
    for job in jobs:
        assert job["task_name"] == "deliver_webhook" and job["queue_name"] == "webhooks"
        assert list(job["args"]) == ["log_id"]
        dumped = json.dumps(job, default=str)
        for text in PERSONAL + ["case.example.org", "whsec_"]:
            assert text not in dumped
    assert {j["args"]["log_id"] for j in jobs} == {str(r.id) for r in rows}
    assert setup.tls.requests == []  # nothing external on the request path


async def test_a_repeat_queue_call_is_a_no_op(setup):
    response = await submit(setup.workspace, setup.form)
    again = await container.webhook_service().queue_for_submission(
        setup.workspace.id, setup.form.form_id, response.response_id
    )
    assert again == []
    assert len(setup.jobs.jobs) == 1


async def test_the_job_sends_only_the_mapped_questions_signed(setup, lines):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    outcome = await run(log)
    assert outcome.status == "delivered"
    (request,) = setup.tls.requests
    sent = json.loads(request.body)
    assert list(sent) == ["event", "delivery_id", "form_id", "response_id", "submitted_at", "data"]
    assert sent["event"] == "submission" and sent["delivery_id"] == str(log.id)
    assert sent["form_id"] == setup.form.form_id and sent["response_id"] == response.response_id
    assert list(sent["data"]) == ["name", "age", "colours", "people"]
    assert sent["data"]["name"] == "Ada Example" and sent["data"]["age"] == 36
    assert sent["data"]["colours"] == ["Red", "Blue"]
    assert sent["data"]["people"][0] == {"pname": "Bo", "pyears": 3}
    # data minimisation: what was not mapped is not in the body at all
    for text in ("Synthetic story.", "ada@example.test", "1990-01-02"):
        assert text.encode() not in request.body
    assert "values_schema" not in sent
    h = request.headers
    assert request.method == "POST" and request.target == "/hooks/intake"
    assert h["content-type"] == "application/json"
    assert h["x-bettercollected-event"] == "submission"
    assert h["x-bettercollected-delivery"] == str(log.id)
    assert h["user-agent"] == "bettercollected-webhooks/1"
    timestamp = int(h["x-bettercollected-timestamp"])
    assert abs(timestamp - utcnow().timestamp()) < 30
    secret = setup.hook.secret
    assert payload.verify(secret, timestamp, request.body, h["x-bettercollected-signature"])
    assert "cookie" not in h and "authorization" not in h

    done = await container.action_log_repo().get(log.id)
    assert done.status is LogStatus.DELIVERED and done.attempts == 1
    assert done.last_http_status == 200 and done.last_error_code is None
    assert done.finished_at and done.first_attempt_at and done.last_duration_ms is not None
    # the row holds ids, the host it was queued for and counters, never answers,
    # addresses or secrets
    assert done.host == "case.example.org"
    stored = json.dumps(done.model_dump(mode="json"))
    for text in PERSONAL + [secret, "https://", "intake"]:
        assert text not in stored
    for text in PERSONAL + [secret, "case.example.org"]:
        assert not any(text in line for line in lines), text
    # delivered once: a second run does nothing
    assert (await run(log)).status == "skipped" and len(setup.tls.requests) == 1


async def test_the_reply_of_the_destination_is_never_kept(setup, lines):
    marker = b"DESTINATION-SECRET-TEXT"
    setup.tls.script.answers = [(200, {}, marker * 1000)]
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    assert (await run(log)).status == "delivered"
    done = await container.action_log_repo().get(log.id)
    assert marker.decode() not in json.dumps(done.model_dump(mode="json"))
    assert not any(marker.decode() in line for line in lines)


async def test_the_reply_is_read_up_to_a_few_kb_only(setup):
    seen = {}
    real = client._request_once

    async def spy(*args, **kwargs):
        seen["max_reply"] = args[7]
        return await real(*args, **kwargs)

    setup.tls.script.answers = [(200, {}, b"x" * 200_000)]
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    import unittest.mock as mock

    with mock.patch.object(client, "_request_once", spy):
        assert (await run(log)).status == "delivered"
    assert seen["max_reply"] == sender.MAX_REPLY_BYTES == 4096


async def test_transient_failures_retry_with_backoff_then_end_visible(setup, lines):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(503, {}, b"down")]
    repo = container.action_log_repo()
    for attempt in range(MAX_ATTEMPTS - 1):
        outcome = await run(log, attempt)
        assert (outcome.status, outcome.retry) == ("retrying", True)
        row = await repo.get(log.id)
        assert row.status is LogStatus.RETRYING and row.attempts == attempt + 1
        wait = (row.next_attempt_at - row.last_attempt_at).total_seconds()
        base = min(retry.CAP_SECONDS, retry.BASE_SECONDS * retry.FACTOR**attempt)
        assert base * 0.74 <= wait <= base * 1.26 + 2, (attempt, wait)
        assert row.last_error_code == "http_5xx" and row.last_http_status == 503
    last = await run(log, MAX_ATTEMPTS - 1)
    row = await repo.get(log.id)
    assert (last.status, last.retry) == ("failed", False)
    assert row.status is LogStatus.FAILED and row.attempts == MAX_ATTEMPTS
    assert row.next_attempt_at is None and row.finished_at
    assert len(setup.tls.requests) == MAX_ATTEMPTS
    # every attempt carries the same delivery id and body: a receiver can drop a repeat
    assert {r.headers["x-bettercollected-delivery"] for r in setup.tls.requests} == {str(log.id)}
    assert len({r.body for r in setup.tls.requests}) == 1
    # a fresh timestamp and signature on each attempt
    assert len({r.headers["x-bettercollected-signature"] for r in setup.tls.requests}) >= 1


async def test_a_retry_after_longer_than_the_backoff_wins(setup):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(429, {"Retry-After": "900"}, b"slow down")]
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert outcome.retry and outcome.retry_after == 900
    assert row.last_error_code == "http_4xx" and row.last_http_status == 429
    assert (row.next_attempt_at - row.last_attempt_at).total_seconds() >= 899


@pytest.mark.parametrize("status", [400, 401, 403, 404, 410, 422])
async def test_a_client_error_fails_at_once(setup, status):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(status, {}, b"no")]
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert (outcome.status, outcome.retry) == ("failed", False)
    assert row.status is LogStatus.FAILED and row.last_http_status == status
    assert row.last_error_code == "http_4xx" and len(setup.tls.requests) == 1


@pytest.mark.parametrize("status", [301, 302, 307, 308])
async def test_a_redirect_is_never_followed(setup, status):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(status, {"Location": "https://169.254.169.254/"}, b"")]
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert outcome.status == "failed"
    assert row.last_error_code == "redirect_refused" and row.last_http_status == status
    assert len(setup.tls.requests) == 1 and setup.tls.dialled == [(PUBLIC_ADDRESS, 443)]


async def test_a_slow_destination_times_out(setup, monkeypatch):
    monkeypatch.setattr(sender, "TOTAL_TIMEOUT_S", 0.3)
    monkeypatch.setitem(sender.TIMEOUTS, "read", 0.2)
    setup.tls.script.delay = 2.0
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert (outcome.status, outcome.retry) == ("retrying", True)
    assert row.last_error_code == "timeout" and row.last_duration_ms is not None


async def test_the_connection_is_pinned_to_the_address_that_was_checked(setup):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    await run(log)
    assert setup.tls.dialled == [(PUBLIC_ADDRESS, 443)]


async def test_dns_rebinding_public_when_saved_private_when_called(
    workspace, webhooks_on, memory_jobs, tls, monkeypatch
):
    """The name resolves to a public address when the webhook is saved and to a
    private one when it is called: refused at the call, permanently, with no
    connection made."""
    form = await publish(workspace)
    state = {"answer": [PUBLIC_ADDRESS]}

    async def resolve(host, port=443):
        return state["answer"]

    monkeypatch.setattr(client, "resolve", resolve)
    hook = await make_webhook(workspace, form)  # passes the save-time check
    state["answer"] = ["10.0.0.5"]
    response = await submit(workspace, form)
    (log,) = [r for r in await logs_of(form) if r.response_id == response.response_id]
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert (outcome.status, outcome.retry) == ("failed", False)
    assert row.last_error_code == "not_allowed" and row.attempts == 1
    assert tls.requests == [] and tls.dialled == []
    # a name that answers both at the call is refused too
    for answer in (["10.0.0.5", PUBLIC_ADDRESS], ["169.254.169.254"], ["::1"], ["::ffff:10.0.0.5"]):
        state["answer"] = answer
        fresh = await submit(workspace, form)
        (again,) = [r for r in await logs_of(form) if r.response_id == fresh.response_id]
        assert (await run(again)).status == "failed"
        assert (await container.action_log_repo().get(again.id)).last_error_code == "not_allowed"
    assert tls.requests == [] and tls.dialled == [] and hook


async def test_an_erased_response_is_never_sent(setup):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    # the response vanishes without the service's hook (a cascade, an import
    # cleanup): the job still never sends it and drops the row
    await container.form_response_service()._form_response_repo.delete_response(
        response_id=response.response_id
    )
    outcome = await run(log)
    assert outcome.status == "gone" and setup.tls.requests == []
    assert await container.action_log_repo().get(log.id) is None


async def test_erasing_a_response_through_the_service_removes_the_row_so_nothing_is_sent(setup):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    await container.form_response_service().delete_response(response_id=response.response_id)
    assert await container.action_log_repo().get(log.id) is None
    assert (await run(log)).status == "skipped" and setup.tls.requests == []


async def test_a_webhook_switched_off_meanwhile_cancels_the_delivery(setup):
    from backend.app.services.webhooks.service import WebhookUpdateDto
    from tests.app.controllers.data import testUser

    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    await container.webhook_service().update_webhook(
        setup.workspace.id, setup.form.form_id, setup.hook.id, WebhookUpdateDto(enabled=False), testUser
    )
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert outcome.status == "cancelled" and row.status is LogStatus.CANCELLED
    assert row.last_error_code == "disabled" and setup.tls.requests == []


async def test_a_deleted_webhook_cancels_the_delivery(setup):
    from tests.app.controllers.data import testUser

    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    await container.webhook_service().delete_webhook(
        setup.workspace.id, setup.form.form_id, setup.hook.id, testUser
    )
    assert (await run(log)).status == "cancelled" and setup.tls.requests == []


async def test_the_switch_off_queues_nothing_and_sends_nothing(setup, monkeypatch):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    monkeypatch.setattr(settings.webhooks, "ENABLED", False)
    before = len(setup.jobs.jobs)
    second = await submit(setup.workspace, setup.form)
    assert len(setup.jobs.jobs) == before
    assert [r for r in await logs_of(setup.form) if r.response_id == second.response_id] == []
    # a run that was queued before the switch went off sends nothing
    assert (await run(log)).status == "skipped" and setup.tls.requests == []
    assert (await container.webhook_service().redefer_pending()) == {"queued": 0, "rescued": 0}


async def test_a_retrying_delivery_is_parked_while_the_switch_is_off(setup, monkeypatch):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(503, {}, b"")]
    await run(log)
    monkeypatch.setattr(settings.webhooks, "ENABLED", False)
    assert (await run(log, 1)).status == "skipped"
    assert (await container.action_log_repo().get(log.id)).status is LogStatus.PENDING


async def test_the_sweep_queues_a_lost_job_again_and_rescues_a_dead_worker(setup):
    import datetime as dt

    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    repo = container.action_log_repo()
    service = container.webhook_service()
    setup.jobs.jobs.clear()  # the queue lost it
    # too young: left alone
    assert (await service.redefer_pending())["queued"] == 0
    real_clock = service._clock
    try:
        service._clock = lambda: utcnow() + dt.timedelta(minutes=10)
        assert (await service.redefer_pending())["queued"] == 1
        assert [j["args"]["log_id"] for j in setup.jobs.jobs.values()] == [str(log.id)]
        # a run whose worker died mid-attempt goes back to pending and is queued
        row = await repo.get(log.id)
        row.status = LogStatus.IN_PROGRESS
        await repo.upsert(row)
        setup.jobs.jobs.clear()
        service._clock = lambda: utcnow() + dt.timedelta(hours=2)
        counts = await service.redefer_pending()
        assert counts["rescued"] == 1 and len(setup.jobs.jobs) == 1
        assert (await repo.get(log.id)).status is LogStatus.PENDING
        # a retry whose job vanished long ago
        row = await repo.get(log.id)
        row.status = LogStatus.RETRYING
        await repo.upsert(row)
        service._clock = lambda: utcnow() + dt.timedelta(days=2)
        setup.jobs.jobs.clear()
        assert (await service.redefer_pending())["rescued"] == 1
    finally:
        service._clock = real_clock


# ---------------------------------------------------------------- the job


async def test_the_job_raises_for_a_retry_and_returns_the_status_otherwise(setup):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(503, {}, b"")]
    ctx = SimpleNamespace(job=SimpleNamespace(attempts=0))
    with pytest.raises(retry.WebhookRetry):
        await tasks.deliver_webhook(ctx, str(log.id))
    setup.tls.script.answers = [(200, {}, b"")]
    ctx = SimpleNamespace(job=SimpleNamespace(attempts=1))
    assert await tasks.deliver_webhook(ctx, str(log.id)) == "delivered"


async def test_the_task_is_on_its_own_queue_never_the_executors():
    from backend.jobs.app import ACTIONS_QUEUE, DEFAULT_QUEUE, WEBHOOKS_QUEUE

    for name in ("deliver_webhook", "webhooks_redefer", "purge_action_logs"):
        assert tasks.app.tasks[name].queue == WEBHOOKS_QUEUE
    assert WEBHOOKS_QUEUE not in (ACTIONS_QUEUE, DEFAULT_QUEUE)
    assert "run_action" not in tasks.app.tasks  # the executor's body is not here


async def test_the_worker_listens_to_default_and_webhooks_but_not_actions(monkeypatch):
    import inspect

    from backend.jobs import worker

    source = inspect.getsource(worker.main)
    assert "WEBHOOKS_QUEUE" in source and "ACTIONS_QUEUE" not in source


@pytest.mark.parametrize("attempts", range(MAX_ATTEMPTS + 1))
async def test_the_retry_strategy_stops_after_the_last_attempt(attempts):
    strategy = retry.WebhookRetryStrategy(rand=lambda: 0.5)
    job = SimpleNamespace(attempts=attempts)
    decision = strategy.get_retry_decision(exception=retry.WebhookRetry(), job=job)
    if attempts + 1 >= MAX_ATTEMPTS:
        assert decision is None
    else:
        waited = (decision.retry_at - utcnow()).total_seconds()
        assert waited == pytest.approx(retry.backoff_seconds(attempts, lambda: 0.5), abs=3)


async def test_the_retry_strategy_honours_a_longer_retry_after():
    strategy = retry.WebhookRetryStrategy(rand=lambda: 0.5)
    decision = strategy.get_retry_decision(
        exception=retry.WebhookRetry(retry_after=3000), job=SimpleNamespace(attempts=0)
    )
    assert (decision.retry_at - utcnow()).total_seconds() == pytest.approx(3000, abs=3)


async def test_backoff_grows_exponentially_with_jitter_inside_bounds_and_a_cap():
    for attempt in range(10):
        base = min(retry.CAP_SECONDS, retry.BASE_SECONDS * retry.FACTOR**attempt)
        low = retry.backoff_seconds(attempt, lambda: 0.0)
        high = retry.backoff_seconds(attempt, lambda: 1.0)
        mid = retry.backoff_seconds(attempt, lambda: 0.5)
        assert low == pytest.approx(base * 0.75, abs=1) and high == pytest.approx(base * 1.25, abs=1)
        assert mid == pytest.approx(base, abs=1)
    assert [retry.backoff_seconds(i, lambda: 0.5) for i in range(5)] == [30, 120, 480, 1920, 7680]
    assert retry.backoff_seconds(9, lambda: 1.0) <= retry.CAP_SECONDS * 1.25
    # jitter really varies
    assert len({retry.backoff_seconds(3) for _ in range(30)}) > 1


# ------------------------------------- a delivery goes to the host it was queued for


async def _change_url(setup, url):
    from backend.app.services.webhooks.service import WebhookUpdateDto
    from tests.app.controllers.data import testUser

    await container.webhook_service().update_webhook(
        setup.workspace.id, setup.form.form_id, setup.hook.id, WebhookUpdateDto(url=url), testUser
    )


async def test_a_url_change_between_queueing_and_running_cancels_the_delivery(setup, lines):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    assert log.host == "case.example.org"
    await _change_url(setup, "https://elsewhere.example.net/hook")
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert outcome.status == "cancelled"
    assert row.status is LogStatus.CANCELLED and row.last_error_code == "destination_changed"
    assert row.finished_at and row.attempts == 1
    # nothing was sent, to the old host or the new one
    assert setup.tls.requests == [] and setup.tls.dialled == []
    assert not any("elsewhere.example.net" in line for line in lines)


async def test_a_url_change_between_attempts_cancels_the_retry(setup):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(503, {}, b"down")]
    assert (await run(log, 0)).status == "retrying"
    assert len(setup.tls.requests) == 1
    await _change_url(setup, "https://elsewhere.example.net/hook")
    outcome = await run(log, 1)
    row = await container.action_log_repo().get(log.id)
    assert outcome.status == "cancelled" and not outcome.retry
    assert row.status is LogStatus.CANCELLED and row.last_error_code == "destination_changed"
    assert len(setup.tls.requests) == 1  # the second attempt sent nothing


async def test_a_change_of_path_or_token_on_the_same_host_still_delivers(setup):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    await _change_url(setup, "https://case.example.org/v2/hooks?key=new")
    assert (await run(log)).status == "delivered"
    assert setup.tls.requests[0].target == "/v2/hooks?key=new"


async def test_a_test_event_is_bound_to_its_host_too(setup):
    from tests.app.controllers.data import testUser

    queued = await container.webhook_service().send_test(
        setup.workspace.id, setup.form.form_id, setup.hook.id, testUser
    )
    assert queued.host == "case.example.org"
    await _change_url(setup, "https://elsewhere.example.net/hook")
    assert (await container.webhook_service().run_delivery(queued.id)).status == "cancelled"
    assert setup.tls.requests == []


# --------------------------------------------------------- the attempt cap


async def test_fresh_jobs_never_give_a_delivery_more_than_the_attempt_cap(setup):
    """The sweep (or the switch coming back on) queues a new job, whose own
    attempt count starts at 0: the row's count is what limits the delivery."""
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(503, {}, b"down")]
    repo = container.action_log_repo()
    for _ in range(MAX_ATTEMPTS - 1):
        outcome = await run(log, 0)  # a brand new job each time
        assert (outcome.status, outcome.retry) == ("retrying", True)
        row = await repo.get(log.id)
        row.status = LogStatus.PENDING  # as the sweep puts a lost one back
        await repo.upsert(row)
    last = await run(log, 0)
    row = await repo.get(log.id)
    assert (last.status, last.retry) == ("failed", False)
    assert row.status is LogStatus.FAILED and row.attempts == MAX_ATTEMPTS
    assert len(setup.tls.requests) == MAX_ATTEMPTS
    assert (await run(log, 0)).status == "skipped" and len(setup.tls.requests) == MAX_ATTEMPTS


async def test_the_backoff_follows_the_rows_count_not_the_jobs(setup):
    response = await submit(setup.workspace, setup.form)
    log = await log_of(setup, response)
    setup.tls.script.answers = [(503, {}, b"down")]
    repo = container.action_log_repo()
    waits = []
    for _ in range(3):
        await run(log, 0)
        row = await repo.get(log.id)
        waits.append((row.next_attempt_at - row.last_attempt_at).total_seconds())
        row.status = LogStatus.PENDING
        await repo.upsert(row)
    assert waits[0] < waits[1] < waits[2]


async def test_the_log_rows_of_a_response_are_deleted_within_its_workspace_and_form_only(setup):
    response = await submit(setup.workspace, setup.form)
    repo = container.action_log_repo()
    (log,) = [r for r in await logs_of(setup.form) if r.response_id == response.response_id]
    # the same response id under another workspace or form is not touched
    for index, other in enumerate(({"workspace_id": "6a2f00000000000000000001"}, {"form_id": "6a2f00000000000000000002"})):
        twin = log.model_copy(deep=True)
        twin.id = None
        twin.ensure_id()
        twin.action_id = f"other-hook-{index}"
        for key, value in other.items():
            setattr(twin, key, value)
        await repo.upsert(twin)
    before = len(await repo.many())
    assert await repo.delete_by_response_id(setup.workspace.id, setup.form.form_id, response.response_id) == 1
    assert len(await repo.many()) == before - 1
