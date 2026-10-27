"""Delivery end to end: a submission writes a delivery row and queues a job
that carries the delivery id only; the job decrypts the answers, builds the
body from the mapped variables only and sends it; failures retry on the
schedule and end visible; nothing secret or personal reaches logs, job
arguments or delivery records."""

import datetime as dt
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from common.clock import utcnow
from loguru import logger

from backend.app.container import container
from backend.app.schemas.registration import DeliveryStatus
from backend.app.services.registration import client
from backend.app.services.registration.retry import (
    MAX_ATTEMPTS,
    RETRY_WAITS,
    RegistrationRetry,
)
from backend.jobs import tasks
from tests.app.registration.helpers import (
    ANSWERS,
    configure,
    make_service,
    publish,
    submit,
)

pytestmark = pytest.mark.asyncio

SECRET = "Token s3cret-value"
PERSONAL = ["Ada Example", "ada@example.test", "Synthetic story.", "1990-01-02"]


@pytest.fixture()
def logs():
    lines = []
    handler = logger.add(lambda message: lines.append(str(message)), level="DEBUG")
    yield lines
    logger.remove(handler)


@pytest.fixture()
async def setup(workspace, registration_on, memory_jobs, tls):
    form = await publish(workspace)
    service = await make_service(workspace)
    await configure(
        workspace, form, service, ["name", "age", "colours", "people", "upload"]
    )
    return SimpleNamespace(
        workspace=workspace, form=form, service=service, jobs=memory_jobs, tls=tls
    )


async def delivery_of(setup, response):
    rows = await container.registration_delivery_repo().many()
    (row,) = [r for r in rows if r.response_id == response.response_id]
    return row


async def test_submission_queues_one_job_with_the_delivery_id_only(setup, logs):
    with patch.object(
        client, "post_json", side_effect=AssertionError("called on the request path")
    ):
        response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    assert delivery.status is DeliveryStatus.PENDING
    (job,) = setup.jobs.jobs.values()
    assert job["task_name"] == "register_submission" and job["queue_name"] == "default"
    assert job["args"] == {"delivery_id": str(delivery.id)}
    dumped = json.dumps(job, default=str)
    for text in PERSONAL + [SECRET]:
        assert text not in dumped
    assert setup.tls.requests == []


async def test_a_repeat_queue_call_is_a_no_op(setup):
    response = await submit(setup.workspace, setup.form)
    again = await container.registration_service().queue_for_submission(
        setup.workspace.id, setup.form.form_id, response.response_id
    )
    assert again is None
    assert len(setup.jobs.jobs) == 1


async def test_the_job_sends_only_the_mapped_variables(setup, logs):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    with patch.object(
        container.aws_service(), "read_object", MagicMock(return_value=None)
    ):
        outcome = await container.registration_service().run_delivery(str(delivery.id))
    assert outcome.status == "delivered"
    (request,) = setup.tls.requests
    sent = json.loads(request.body)
    assert list(sent) == ["values", "values_schema", "metadata", "metadata_schema"]
    assert list(sent["values"]) == ["name", "age", "colours", "people", "upload"]
    assert sent["values"]["name"] == "Ada Example" and sent["values"]["age"] == 36
    assert sent["values"]["colours"] == {"Red": True, "Green": False, "Blue": True}
    assert sent["values"]["people"][0] == {"pname": "Bo", "pyears": 3}
    assert sent["values"]["upload"] is None
    # data minimisation: what was not mapped is not in the body at all
    for text in ("Synthetic story.", "ada@example.test", "1990-01-02"):
        assert text.encode() not in request.body
    assert sent["metadata"]["public_reference"] == response.submission_uuid
    assert request.headers["authorization"] == SECRET
    assert request.headers["idempotency-key"] == str(delivery.id)
    assert request.target == "/api/intake"

    done = await container.registration_delivery_repo().get(delivery.id)
    assert (
        done.status is DeliveryStatus.DELIVERED
        and done.delivered_at
        and done.attempts == 1
    )
    assert done.last_http_status == 200 and done.last_error_code is None
    # the record holds ids and counters, never answers or addresses
    stored = json.dumps(done.model_dump(mode="json"))
    for text in PERSONAL + [SECRET, "case.example.org", "intake"]:
        assert text not in stored
    # nor do the logs
    for text in PERSONAL + [SECRET]:
        assert not any(text in line for line in logs), text
    # delivered once; a second run does nothing
    again = await container.registration_service().run_delivery(str(delivery.id))
    assert again.status == "skipped" and len(setup.tls.requests) == 1


async def test_files_are_read_inside_the_job_and_sent_as_base64(setup):
    form = await publish(setup.workspace)
    service = await make_service(setup.workspace, name="Second")
    await configure(setup.workspace, form, service, ["upload"])
    answers = {
        **ANSWERS,
        "upload": {
            "type": "file",
            "file_metadata": {"id": "file-1", "name": "note.txt"},
        },
    }
    response = await submit(setup.workspace, form, answers)
    delivery = await delivery_of(setup, response)
    seen = []

    def read(key, max_bytes):
        seen.append(key)
        return b"synthetic bytes" if key.endswith("/file-1") else None

    with patch.object(container.aws_service(), "read_object", side_effect=read):
        await container.registration_service().run_delivery(str(delivery.id))
    sent = json.loads(setup.tls.requests[-1].body)
    assert sent["values"]["upload"] == {
        "file_name": "note.txt",
        "content": "c3ludGhldGljIGJ5dGVz",
    }
    assert (
        seen[0]
        == f"private/{setup.workspace.id}/{form.form_id}/{response.response_id}/file-1"
    )


async def test_a_missing_file_fails_permanently_without_a_send(setup):
    answers = {
        **ANSWERS,
        "upload": {"type": "file", "file_metadata": {"id": "gone", "name": "x.txt"}},
    }
    response = await submit(setup.workspace, setup.form, answers)
    delivery = await delivery_of(setup, response)
    with patch.object(
        container.aws_service(), "read_object", MagicMock(return_value=None)
    ):
        outcome = await container.registration_service().run_delivery(str(delivery.id))
    row = await container.registration_delivery_repo().get(delivery.id)
    assert outcome.status == "failed" and row.last_error_code == "file_missing"
    assert setup.tls.requests == []


async def test_transient_failures_retry_on_the_schedule_then_end_visible(setup, logs):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.tls.script.answers = [(503, {}, b"down")]
    service = container.registration_service()
    repo = container.registration_delivery_repo()
    for attempt in range(MAX_ATTEMPTS - 1):
        outcome = await service.run_delivery(str(delivery.id), job_attempt=attempt)
        assert (outcome.status, outcome.retry) == ("retrying", True)
        row = await repo.get(delivery.id)
        assert row.status is DeliveryStatus.RETRYING and row.attempts == attempt + 1
        wait = (row.next_attempt_at - row.last_attempt_at).total_seconds()
        assert abs(wait - RETRY_WAITS[attempt]) < 5
        assert row.last_error_code == "http_5xx" and row.last_http_status == 503
    last = await service.run_delivery(str(delivery.id), job_attempt=MAX_ATTEMPTS - 1)
    row = await repo.get(delivery.id)
    assert (last.status, last.retry) == ("failed", False)
    assert row.status is DeliveryStatus.FAILED and row.attempts == MAX_ATTEMPTS
    assert row.next_attempt_at is None
    assert len(setup.tls.requests) == MAX_ATTEMPTS
    # nothing more happens to a failed delivery on its own
    assert (await service.run_delivery(str(delivery.id))).status == "skipped"
    for text in PERSONAL + [SECRET, "down"]:
        assert not any(text in line for line in logs), text


@pytest.mark.parametrize("status", [400, 401, 404, 422])
async def test_a_permanent_4xx_is_not_retried(setup, status):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.tls.script.answers = [(status, {}, b"no")]
    outcome = await container.registration_service().run_delivery(str(delivery.id))
    row = await container.registration_delivery_repo().get(delivery.id)
    assert (outcome.status, outcome.retry) == ("failed", False)
    assert row.last_error_code == "http_4xx" and row.attempts == 1
    assert len(setup.tls.requests) == 1


async def test_a_redirect_is_a_permanent_failure(setup):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.tls.script.answers = [
        (302, {"Location": "https://elsewhere.example.org/"}, b"")
    ]
    outcome = await container.registration_service().run_delivery(str(delivery.id))
    row = await container.registration_delivery_repo().get(delivery.id)
    assert outcome.status == "failed" and row.last_error_code == "redirect_refused"
    assert len(setup.tls.requests) == 1


async def test_a_name_that_turned_private_fails_at_send_time(setup, monkeypatch):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)

    async def rebound(host, port=443):
        return ["169.254.169.254"]

    monkeypatch.setattr(client, "resolve", rebound)
    outcome = await container.registration_service().run_delivery(str(delivery.id))
    row = await container.registration_delivery_repo().get(delivery.id)
    assert outcome.status == "failed" and row.last_error_code == "not_allowed"
    assert setup.tls.requests == []


async def test_the_job_body_retries_by_raising_and_gives_up_by_returning(setup):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.tls.script.answers = [(429, {"Retry-After": "7200"}, b"")]
    context = SimpleNamespace(job=SimpleNamespace(attempts=0))
    with pytest.raises(RegistrationRetry) as raised:
        await tasks.register_submission(context, str(delivery.id))
    assert raised.value.retry_after == 3600  # capped at an hour
    strategy = tasks.RegistrationRetryStrategy()
    job = lambda attempts: SimpleNamespace(attempts=attempts)  # noqa: E731
    decision = strategy.get_retry_decision(exception=raised.value, job=job(0))
    soon = decision.retry_at - dt.datetime.now(dt.timezone.utc)
    assert 3500 < soon.total_seconds() <= 3600  # the longer Retry-After wins over 60 s
    plain = strategy.get_retry_decision(exception=RegistrationRetry(), job=job(1))
    assert (
        290 < (plain.retry_at - dt.datetime.now(dt.timezone.utc)).total_seconds() <= 300
    )
    assert (
        strategy.get_retry_decision(
            exception=RegistrationRetry(), job=job(MAX_ATTEMPTS - 1)
        )
        is None
    )


async def test_a_ciphertext_copied_to_another_service_is_unreadable(setup):
    other = await make_service(setup.workspace, name="Other")
    repo = container.registration_service_repo()
    first = await repo.get(setup.workspace.id, setup.service.id)
    second = await repo.get(setup.workspace.id, other.id)
    second.secret_sealed = first.secret_sealed  # moved by someone with database access
    await repo.save(second)
    form = await publish(setup.workspace)
    await configure(setup.workspace, form, other, ["name"])
    response = await submit(setup.workspace, form)
    rows = [
        r
        for r in await container.registration_delivery_repo().many()
        if r.response_id == response.response_id
    ]
    outcome = await container.registration_service().run_delivery(str(rows[0].id))
    row = await container.registration_delivery_repo().get(rows[0].id)
    assert outcome.status == "failed" and row.last_error_code == "secret_unreadable"
    assert setup.tls.requests == []


async def test_a_disabled_registration_cancels_pending_deliveries(setup):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    await configure(setup.workspace, setup.form, setup.service, ["name"], enabled=False)
    outcome = await container.registration_service().run_delivery(str(delivery.id))
    row = await container.registration_delivery_repo().get(delivery.id)
    assert outcome.status == "cancelled" and row.last_error_code == "disabled"
    assert setup.tls.requests == []


async def test_a_deleted_response_takes_its_delivery_with_it(setup):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    with patch.object(container.aws_service(), "delete_folder_from_s3", MagicMock()):
        await container.form_response_service().delete_form_response(
            setup.form.form_id, response.response_id, setup.workspace.id
        )
    assert await container.registration_delivery_repo().get(delivery.id) is None


async def test_a_job_for_a_vanished_response_drops_the_row(setup):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    await container.form_response_repo().delete_response(
        response_id=response.response_id
    )
    outcome = await container.registration_service().run_delivery(str(delivery.id))
    assert outcome.status == "gone"
    assert await container.registration_delivery_repo().get(delivery.id) is None
    assert setup.tls.requests == []


async def test_the_sweeps_requeue_lost_jobs_and_delete_orphans(setup):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    setup.jobs.jobs.clear()  # the queue lost it
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)
    service = container.registration_service()
    service._clock = lambda: later
    try:
        counts = await service.redefer_pending()
        assert counts["queued"] == 1 and len(setup.jobs.jobs) == 1
        # an orphan: a response that no longer exists
        await container.form_response_repo().delete_response(
            response_id=response.response_id
        )
        assert (await service.sweep_orphans())["deliveries"] == 1
        assert await container.registration_delivery_repo().get(delivery.id) is None
    finally:
        service._clock = utcnow


async def test_switch_off_enqueues_nothing_and_the_jobs_do_nothing(setup, monkeypatch):
    first = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, first)
    setup.jobs.jobs.clear()
    from backend.config import settings

    monkeypatch.setattr(settings.registration, "REGISTRATION", "off")
    second = await submit(setup.workspace, setup.form)
    assert setup.jobs.jobs == {}
    assert [
        r.response_id for r in await container.registration_delivery_repo().many()
    ] == [first.response_id]
    service = container.registration_service()
    assert (await service.run_delivery(str(delivery.id))).status == "skipped"
    assert await service.redefer_pending() == {"queued": 0, "rescued": 0}
    assert await service.sweep_orphans() == {"deliveries": 0, "registrations": 0}
    assert await service.destination_for(setup.workspace.id, setup.form.form_id) is None
    assert setup.tls.requests == []
    # the configuration and the existing delivery are untouched
    assert (
        await container.registration_delivery_repo().get(delivery.id)
    ).status is DeliveryStatus.PENDING
    assert second.response_id


async def test_answers_that_do_not_decrypt_fail_permanently_never_an_empty_body(setup):
    response = await submit(setup.workspace, setup.form)
    delivery = await delivery_of(setup, response)
    repo = container.form_response_repo()
    stored = await repo.get_response(response.response_id)
    stored.answers = "v1:not-a-real-ciphertext"
    await repo.upsert(stored)
    outcome = await container.registration_service().run_delivery(str(delivery.id))
    row = await container.registration_delivery_repo().get(delivery.id)
    assert outcome.status == "failed" and row.last_error_code == "answers_unreadable"
    assert setup.tls.requests == []
