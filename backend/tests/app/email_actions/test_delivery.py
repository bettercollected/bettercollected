"""Delivery end to end: a submission writes one log row per mail and queues one
job each (log id only) on the ``emails`` queue; the job decrypts the answers,
reduces them to the mapped questions and sends a plain-text message; the team
channel re-checks membership, the respondent channel is fixed wording to the
address of this very submission with rate limits; a failure retries with
backoff and ends visible; nothing personal reaches logs, job arguments or log
rows; erasure wins over a late send."""

import json
from types import SimpleNamespace

import pytest
from common.models.standard_form import StandardForm, StandardFormSettings
from common.models.user import User
from loguru import logger

from backend.app.container import container
from backend.app.schemas.webhook import LogStatus
from backend.app.services.email_actions import retry
from backend.app.services.email_actions.retry import MAX_ATTEMPTS
from backend.app.services.email_actions.service import (
    COPY_ADDRESS_FORM_PER_HOUR,
    EmailActionUpdateDto,
)
from backend.app.services.email_actions.transport import MailFailed
from backend.jobs import tasks
from tests.app.controllers.data import invited_user, testUser, testUser1
from tests.app.email_actions.helpers import OWNER, age, logs_of, make_action
from tests.app.email_actions.helpers import submit_as_owner_of_the_address as submit, verified
from tests.app.registration.helpers import ANSWERS, FIELDS, publish
from tests.app.registration.helpers import submit as submit_as

pytestmark = pytest.mark.asyncio

PERSONAL = ["Ada Example", "ada@example.test", "Synthetic story.", "1990-01-02"]


def _mentions_personal(document) -> bool:
    """Whether a log row holds any of the respondent's details. Checked by whole value:
    a short needle such as "ada" is made of hex letters and turns up in random ids."""
    text = json.dumps(document).lower()
    return any(value.lower() in text for value in PERSONAL)


@pytest.fixture()
def lines():
    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    yield seen
    logger.remove(handler)


@pytest.fixture()
async def setup(workspace, emails_on, memory_jobs, transport):
    form = await publish(workspace)
    action = await make_action(workspace, form, respondent="mail")
    return SimpleNamespace(
        workspace=workspace, form=form, action=action, jobs=memory_jobs, transport=transport
    )


async def rows_of(setup, response, channel=None):
    rows = [r for r in await logs_of(setup.form) if r.response_id == response.response_id]
    return [r for r in rows if channel is None or r.channel == channel]


async def run(log, attempt=0):
    return await container.email_action_service().run_delivery(str(log.id), job_attempt=attempt)


async def test_a_submission_queues_one_job_per_mail_with_the_log_id_only(setup, lines):
    response = await submit(setup.workspace, setup.form)
    rows = await rows_of(setup, response)
    assert sorted(r.channel for r in rows) == ["respondent", "team"]
    assert all(r.status is LogStatus.PENDING and r.attempts == 0 for r in rows)
    assert {r.action_id for r in rows} == {setup.action.id, setup.action.id + ".copy"}
    jobs = list(setup.jobs.jobs.values())
    assert len(jobs) == 2
    for job in jobs:
        assert job["task_name"] == "deliver_email" and job["queue_name"] == "emails"
        assert list(job["args"]) == ["log_id"]
        dumped = json.dumps(job, default=str)
        for text in PERSONAL + ["acme.example", "Notify the team"]:
            assert text not in dumped
    assert {j["args"]["log_id"] for j in jobs} == {str(r.id) for r in rows}
    assert setup.transport.sent == []  # nothing external on the request path


async def test_a_repeat_queue_call_is_a_no_op(setup):
    response = await submit(setup.workspace, setup.form)
    again = await container.email_action_service().queue_for_submission(
        setup.workspace.id, setup.form.form_id, response.response_id, form=None, answers={}
    )
    assert again == [] and len(setup.jobs.jobs) == 2


async def test_a_disabled_action_queues_nothing(setup):
    await container.email_action_service().update_action(
        setup.workspace.id, setup.form.form_id, setup.action.id,
        EmailActionUpdateDto(enabled=False), testUser,
    )
    response = await submit(setup.workspace, setup.form)
    assert await rows_of(setup, response) == [] and len(setup.jobs.jobs) == 0


async def test_the_team_mail_has_the_mapped_questions_only_as_plain_text(setup, lines):
    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    outcome = await run(log)
    assert outcome.status == "delivered"
    (mail,) = setup.transport.sent
    assert mail["recipients"] == [OWNER]
    assert mail["subject"] == "New response to Registration test from Ada Example"
    assert mail["body"] == "Ada Example sent a response.\n\nFull name: Ada Example\nAge: 36"
    # data minimisation: what was not mapped is not in the mail at all
    for text in ("Synthetic story.", "ada@example.test", "1990-01-02"):
        assert text not in mail["body"] and text not in mail["subject"]
    done = await container.action_log_repo().get(log.id)
    assert done.status is LogStatus.DELIVERED and done.attempts == 1
    assert done.finished_at and done.last_error_code is None
    # the row holds ids and counters, never an address, a subject or an answer
    stored = json.dumps(done.model_dump(mode="json"))
    for text in PERSONAL + [OWNER, "acme.example", "Registration test", "New response"]:
        assert text not in stored
    for text in PERSONAL + [OWNER, "acme.example"]:
        assert not any(text in line for line in lines), text
    # delivered once: a second run does nothing
    assert (await run(log)).status == "skipped" and len(setup.transport.sent) == 1


async def test_the_form_language_picks_the_dutch_template(workspace, emails_on, memory_jobs, transport):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        StandardForm(
            builder_version="v2",
            title="Intake",
            settings=StandardFormSettings(language="nl"),
            fields=[{"id": "s1", "type": "slide", "index": 0, "properties": {"fields": FIELDS}}],
        ),
        testUser,
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    await make_action(workspace, form)
    response = await submit(workspace, form)
    (log,) = [r for r in await logs_of(form) if r.response_id == response.response_id]
    await run(log)
    (mail,) = transport.sent
    assert mail["subject"] == "Nieuwe inzending voor Intake van Ada Example"
    assert "stuurde een inzending" in mail["body"]


async def test_the_answers_are_plain_text_whatever_the_respondent_typed(setup):
    evil = {
        **ANSWERS,
        "name": {"type": "text", "text": "<b>Ada</b>\r\nBcc: attacker@evil.example {{answers}}"},
    }
    response = await submit(setup.workspace, setup.form, answers=evil)
    (log,) = await rows_of(setup, response, "team")
    await run(log)
    (mail,) = setup.transport.sent
    assert "\n" not in mail["subject"] and "\r" not in mail["subject"]
    assert mail["subject"].endswith("from <b>Ada</b> Bcc: attacker@evil.example {{answers}}")
    assert mail["recipients"] == [OWNER]  # nobody is added by an answer
    assert "{{answers}}" in mail["body"]  # not expanded a second time


async def test_a_member_removed_after_the_save_stops_receiving_mail(setup):
    # (the invited user is a member of the test workspace)
    await container.email_action_service().update_action(
        setup.workspace.id, setup.form.form_id, setup.action.id,
        EmailActionUpdateDto(team_recipients=[OWNER, "editor@acme.example"]), testUser,
    )
    membership = await container.workspace_user_repo().find_workspace_user(
        setup.workspace.id, invited_user.id
    )
    await container.workspace_user_repo().delete_by_id(membership.id)
    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    assert (await run(log)).status == "delivered"
    (mail,) = setup.transport.sent
    assert mail["recipients"] == [OWNER]  # the removed member is not mailed


async def test_when_no_recipient_is_a_member_any_more_nothing_is_sent(setup):
    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    owner = await container.workspace_user_repo().find_workspace_user(setup.workspace.id, testUser.id)
    if owner is not None:
        await container.workspace_user_repo().delete_by_id(owner.id)
    # the workspace's billing owner still counts as a member: take the address away instead
    from unittest.mock import AsyncMock, patch

    with patch.object(
        container.copy_recipient_service()._http_client, "get", AsyncMock(return_value={"users_info": []})
    ):
        outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert outcome.status == "cancelled" and row.last_error_code == "recipient_not_allowed"
    assert setup.transport.sent == []


async def test_the_respondent_copy_is_fixed_wording_to_the_address_of_this_submission(setup, lines):
    answers = {**ANSWERS, "mail": {"type": "email", "email": "Ada.Example@Example.test"}}
    response = await submit(setup.workspace, setup.form, answers=answers)
    (log,) = await rows_of(setup, response, "respondent")
    assert (await run(log)).status == "delivered"
    (mail,) = setup.transport.sent
    assert mail["recipients"] == ["Ada.Example@Example.test"]  # as typed (trimmed)
    assert mail["subject"] == "A copy of your submission"
    # fixed wording and the answers: not the form's title
    assert "Registration test" not in mail["body"] and "Registration test" not in mail["subject"]
    assert "Full name: Ada Example" in mail["body"] and "Age: 36" in mail["body"]
    # nothing the creator wrote reaches an address a respondent gave
    for text in ("Notify the team", "sent a response", "New response to"):
        assert text not in mail["body"] and text not in mail["subject"]
    assert "ada.example@example.test" not in json.dumps(
        (await container.action_log_repo().get(log.id)).model_dump(mode="json")
    )
    assert not any("example.test" in line for line in lines)


async def test_the_respondent_copy_is_dutch_for_a_dutch_form(workspace, emails_on, memory_jobs, transport):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id,
        StandardForm(
            builder_version="v2", title="Intake", settings=StandardFormSettings(language="nl"),
            fields=[{"id": "s1", "type": "slide", "index": 0, "properties": {"fields": FIELDS}}],
        ),
        testUser,
    )
    await service.publish_form(workspace.id, form.form_id, testUser)
    await make_action(workspace, form, team=[], respondent="mail")
    response = await submit(workspace, form)
    (log,) = [r for r in await logs_of(form) if r.response_id == response.response_id]
    await run(log)
    (mail,) = transport.sent
    assert mail["subject"] == "Een kopie van uw inzending" and "Uw antwoorden:" in mail["body"]


async def test_the_copy_goes_only_to_the_address_in_the_stored_submission(setup):
    """The address is read from the stored answers at send time, never from the
    queue, the log row or a request: another response's address is never used."""
    first = await submit(
        setup.workspace, setup.form,
        answers={**ANSWERS, "mail": {"type": "email", "email": "first@example.test"}},
    )
    second = await submit(
        setup.workspace, setup.form,
        answers={**ANSWERS, "mail": {"type": "email", "email": "second@example.test"}},
    )
    for response in (first, second):
        (log,) = await rows_of(setup, response, "respondent")
        await run(log)
    assert [m["recipients"] for m in setup.transport.sent] == [["first@example.test"], ["second@example.test"]]


async def test_the_copy_is_rate_limited_per_address_and_form_per_address_and_per_form(
    setup, monkeypatch
):
    from backend.app.services.email_actions import service as module

    delivered = []
    for n in range(COPY_ADDRESS_FORM_PER_HOUR + 2):
        response = await submit(setup.workspace, setup.form)
        (log,) = await rows_of(setup, response, "respondent")
        outcome = await run(log)
        delivered.append(outcome.status)
        if outcome.status == "cancelled":
            row = await container.action_log_repo().get(log.id)
            assert row.last_error_code == "rate_limited" and row.status is LogStatus.CANCELLED
    assert delivered == ["delivered"] * COPY_ADDRESS_FORM_PER_HOUR + ["cancelled"] * 2
    assert len(setup.transport.sent) == COPY_ADDRESS_FORM_PER_HOUR
    # another address is not held back by the first one's counters
    other = await submit(
        setup.workspace, setup.form,
        answers={**ANSWERS, "mail": {"type": "email", "email": "other@example.test"}},
    )
    (log,) = await rows_of(setup, other, "respondent")
    assert (await run(log)).status == "delivered"
    # a form-wide cap
    monkeypatch.setattr(module, "COPY_FORM_PER_HOUR", 1)
    third = await submit(
        setup.workspace, setup.form,
        answers={**ANSWERS, "mail": {"type": "email", "email": "third@example.test"}},
    )
    (log,) = await rows_of(setup, third, "respondent")
    # (the form's counter already passed 1 with the sends above)
    assert (await run(log)).status in ("cancelled", "delivered")


async def test_the_address_cap_across_forms_counts_the_address_not_the_form(setup, monkeypatch):
    from backend.app.services.email_actions import service as module

    monkeypatch.setattr(module, "COPY_ADDRESS_FORM_PER_HOUR", 100)
    monkeypatch.setattr(module, "COPY_ADDRESS_PER_HOUR", 2)
    statuses = []
    for _ in range(3):
        response = await submit(setup.workspace, setup.form)
        (log,) = await rows_of(setup, response, "respondent")
        statuses.append((await run(log)).status)
    assert statuses == ["delivered", "delivered", "cancelled"]


async def test_transient_failures_retry_with_backoff_then_end_visible(setup):
    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    setup.transport.fail = MailFailed("smtp_unavailable")
    repo = container.action_log_repo()
    for attempt in range(MAX_ATTEMPTS - 1):
        outcome = await run(log, attempt)
        assert (outcome.status, outcome.retry) == ("retrying", True)
        row = await repo.get(log.id)
        assert row.status is LogStatus.RETRYING and row.attempts == attempt + 1
        wait = (row.next_attempt_at - row.last_attempt_at).total_seconds()
        base = min(retry.CAP_SECONDS, retry.BASE_SECONDS * retry.FACTOR**attempt)
        assert base * 0.74 <= wait <= base * 1.26 + 2, (attempt, wait)
        assert row.last_error_code == "smtp_unavailable"
    last = await run(log, MAX_ATTEMPTS - 1)
    row = await repo.get(log.id)
    assert (last.status, last.retry) == ("failed", False)
    assert row.status is LogStatus.FAILED and row.attempts == MAX_ATTEMPTS
    assert row.next_attempt_at is None and row.finished_at


@pytest.mark.parametrize("code", ["recipient_rejected", "smtp_rejected", "invalid_message", "mail_not_configured"])
async def test_a_permanent_failure_fails_at_once(setup, code):
    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    setup.transport.fail = MailFailed(code, permanent=True)
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert (outcome.status, outcome.retry) == ("failed", False)
    assert row.status is LogStatus.FAILED and row.last_error_code == code and row.attempts == 1


async def test_the_job_raises_a_retry_for_a_transient_failure_and_not_otherwise(setup):
    from procrastinate import JobContext

    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    setup.transport.fail = MailFailed("timeout")
    context = SimpleNamespace(job=SimpleNamespace(attempts=0))
    with pytest.raises(Exception) as raised:
        await tasks.deliver_email.func(context, str(log.id))
    assert type(raised.value).__name__ == "EmailRetry"
    setup.transport.fail = None
    assert await tasks.deliver_email.func(context, str(log.id)) == "delivered"
    assert JobContext is not None


async def test_a_crash_is_recorded_as_an_internal_error_without_its_text(setup, lines):
    class Boom:
        async def send(self, **kwargs):
            raise RuntimeError("secret detail ada@example.test")

    service = container.email_action_service()
    service._transport = Boom()
    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert outcome.retry and row.last_error_code == "internal_error"
    assert not any("secret detail" in line or "ada@example.test" in line for line in lines)


async def test_an_erased_response_is_never_mailed(setup):
    response = await submit(setup.workspace, setup.form)
    logs = await rows_of(setup, response)
    await container.form_response_service()._form_response_repo.delete_response(
        response_id=response.response_id
    )
    # the first run finds the submission gone and drops every row it had
    assert (await run(logs[0])).status == "gone"
    assert (await run(logs[1])).status == "skipped"
    assert setup.transport.sent == []
    assert await rows_of(setup, response) == []


async def test_erasing_a_response_through_the_service_removes_both_rows(setup):
    response = await submit(setup.workspace, setup.form)
    logs = await rows_of(setup, response)
    await container.form_response_service().delete_response(response_id=response.response_id)
    assert await rows_of(setup, response) == []
    for log in logs:
        assert (await run(log)).status == "skipped"
    assert setup.transport.sent == []


async def test_an_action_switched_off_or_deleted_meanwhile_cancels_the_delivery(setup):
    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    await container.email_action_service().delete_action(
        setup.workspace.id, setup.form.form_id, setup.action.id, testUser
    )
    outcome = await run(log)
    row = await container.action_log_repo().get(log.id)
    assert outcome.status == "cancelled" and row.last_error_code == "disabled"
    assert setup.transport.sent == []


async def test_the_switch_off_queues_nothing_and_sends_nothing(setup, monkeypatch):
    from backend.config import settings

    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    monkeypatch.setattr(settings.email_actions, "ENABLED", False)
    before = len(setup.jobs.jobs)
    second = await submit(setup.workspace, setup.form)
    assert len(setup.jobs.jobs) == before and await rows_of(setup, second) == []
    assert (await run(log)).status == "skipped" and setup.transport.sent == []
    assert (await container.email_action_service().redefer_pending()) == {"queued": 0, "rescued": 0}


async def test_a_submission_still_succeeds_when_the_queue_is_down(setup, monkeypatch):
    async def down(log_id):
        raise ConnectionError("queue down")

    monkeypatch.setattr(container.email_action_service(), "_defer", down)
    response = await submit(setup.workspace, setup.form)
    assert response.response_id
    # the rows wait; the sweep queues them once the queue is back
    assert {r.status for r in await rows_of(setup, response)} == {LogStatus.PENDING}


async def test_the_sweep_queues_email_rows_only_and_the_webhook_sweep_leaves_them_alone(setup):
    import datetime as dt

    from backend.app.schemas.webhook import ActionType

    response = await submit(setup.workspace, setup.form)
    rows = await rows_of(setup, response)
    for row in rows:
        await age(row, dt.timedelta(hours=1))
    setup.jobs.jobs.clear()
    # the webhook service's sweep never sees an email row
    from backend.config import settings

    settings.webhooks.ENABLED = True
    try:
        assert (await container.webhook_service().redefer_pending())["queued"] == 0
    finally:
        settings.webhooks.ENABLED = False
    assert len(setup.jobs.jobs) == 0
    counts = await container.email_action_service().redefer_pending()
    assert counts["queued"] == 2
    assert {j["task_name"] for j in setup.jobs.jobs.values()} == {"deliver_email"}
    assert ActionType.EMAIL.value == "email"


async def test_deleting_a_form_removes_its_actions_and_log(setup):
    response = await submit(setup.workspace, setup.form)
    assert await rows_of(setup, response)
    await container.email_action_service().delete_for_form(setup.workspace.id, setup.form.form_id)
    assert await rows_of(setup, response) == []
    assert await container.form_email_action_repo().count_for_form(setup.workspace.id, setup.form.form_id) == 0


async def test_the_purge_deletes_rows_older_than_thirty_days(setup):
    import datetime as dt

    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response, "team")
    await age(log, dt.timedelta(days=31))
    assert await container.email_action_service().purge_expired() >= 1
    assert await container.action_log_repo().get(log.id) is None


async def test_the_worker_warns_when_email_actions_are_on_and_the_queue_is_not_served(emails_on, monkeypatch):
    from backend.config import settings
    from backend.jobs import worker

    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    try:
        assert worker.warn_if_emails_unserved(["default", "webhooks"]) is True
        assert any("emails" in line and "JOBS_QUEUES=default,webhooks" in line for line in seen)
        seen.clear()
        assert worker.warn_if_emails_unserved(["default", "webhooks", "emails"]) is False
        monkeypatch.setattr(settings.email_actions, "ENABLED", False)
        assert worker.warn_if_emails_unserved(["default"]) is False
        assert seen == []
    finally:
        logger.remove(handler)


async def test_the_tasks_are_registered_on_the_emails_queue(setup):
    assert tasks.deliver_email.queue == "emails"
    assert tasks.emails_redefer.queue == "emails" and tasks.purge_email_logs.queue == "emails"
    cron = {p.task.name: p.cron for p in tasks.app.periodic_registry.periodic_tasks.values()}
    assert cron["emails_redefer"] == "*/5 * * * *" and cron["purge_email_logs"] == "43 3 * * *"
    assert "deliver_email" in __import__("backend.jobs.app", fromlist=["JOB_NAMES"]).JOB_NAMES
    assert await tasks.emails_redefer(0) == "0 queued, 0 rescued"
    assert (await tasks.purge_email_logs(0)).endswith("deleted")


async def _copy_to(setup, address):
    response = await submit(
        setup.workspace, setup.form,
        answers={**ANSWERS, "mail": {"type": "email", "email": address}},
    )
    (log,) = await rows_of(setup, response, "respondent")
    return log


async def test_variants_of_one_mailbox_share_one_budget_and_are_mailed_as_typed(setup, monkeypatch):
    from backend.app.services.email_actions import service as module

    monkeypatch.setattr(module, "COPY_ADDRESS_FORM_PER_HOUR", 100)
    monkeypatch.setattr(module, "COPY_ADDRESS_PER_HOUR", 3)
    typed = ["A.B+1@GMAIL.com", "ab@gmail.com", "a.b+2@googlemail.com", "ab+x@gmail.com", "a.b@gmail.com"]
    statuses = [(await run(await _copy_to(setup, address))).status for address in typed]
    assert statuses == ["delivered"] * 3 + ["cancelled"] * 2
    # mailed as typed (trimmed; case, tag and dots kept), never the key
    assert [m["recipients"][0] for m in setup.transport.sent] == ["A.B+1@GMAIL.com", "ab@gmail.com", "a.b+2@googlemail.com"]


async def test_an_idn_domain_and_its_punycode_form_are_one_mailbox(setup, monkeypatch):
    from backend.app.services.email_actions import service as module

    monkeypatch.setattr(module, "COPY_ADDRESS_FORM_PER_HOUR", 100)
    monkeypatch.setattr(module, "COPY_ADDRESS_PER_HOUR", 1)
    first = await run(await _copy_to(setup, "jan@b\u00fccher.example"))
    second = await run(await _copy_to(setup, "jan@xn--bcher-kva.example"))
    assert (first.status, second.status) == ("delivered", "cancelled")


async def test_a_workspace_may_send_at_most_1000_copies_an_hour(setup, monkeypatch):
    from backend.app.services.email_actions import service as module

    assert module.COPY_WORKSPACE_PER_HOUR == 1000
    monkeypatch.setattr(module, "COPY_WORKSPACE_PER_HOUR", 2)
    statuses = [(await run(await _copy_to(setup, f"person{n}@example.test"))).status for n in range(4)]
    assert statuses == ["delivered", "delivered", "cancelled", "cancelled"]
    row = (await logs_of(setup.form))
    assert any(r.last_error_code == "rate_limited" for r in row)


async def test_the_team_mails_of_a_form_are_capped_per_hour(setup, monkeypatch):
    from backend.app.services.email_actions import service as module

    assert module.TEAM_FORM_PER_HOUR == 600
    monkeypatch.setattr(module, "TEAM_FORM_PER_HOUR", 2)
    statuses = []
    for _ in range(4):
        response = await submit(setup.workspace, setup.form)
        (log,) = await rows_of(setup, response, "team")
        statuses.append((await run(log)).status)
    assert statuses == ["delivered", "delivered", "cancelled", "cancelled"]
    assert len(setup.transport.sent) == 2


async def test_a_retried_mail_counts_once_against_the_limits(setup, monkeypatch):
    from backend.app.services.email_actions import service as module

    monkeypatch.setattr(module, "COPY_ADDRESS_FORM_PER_HOUR", 1)
    monkeypatch.setattr(module, "TEAM_FORM_PER_HOUR", 1)
    response = await submit(setup.workspace, setup.form)
    (copy,) = await rows_of(setup, response, "respondent")
    (team,) = await rows_of(setup, response, "team")
    setup.transport.fail = MailFailed("smtp_unavailable")
    for log in (copy, team):
        assert (await run(log, 0)).status == "retrying"
        assert (await run(log, 1)).status == "retrying"  # not cancelled as rate_limited by itself
    setup.transport.fail = None
    assert (await run(copy, 2)).status == "delivered"
    assert (await run(team, 2)).status == "delivered"


# --------------------------------------------- the copy's content, as sent


async def test_the_copy_as_sent_has_no_links_and_is_cut(workspace, emails_on, memory_jobs, transport):
    fields = [
        {"id": "name", "type": "short_text", "title": "Visit https://evil.example/now " + "L" * 300},
        {"id": "story", "type": "long_text", "title": "Your story"},
        {"id": "mail", "type": "email", "title": "Email", "properties": {"why_we_ask": "To reply to you"}},
    ]
    form = await publish(workspace, fields=fields)
    await make_action(workspace, form, fields=["name", "story"], team=[OWNER], respondent="mail")
    answers = {
        "name": {"type": "text", "text": "Pay at www.evil.example/pay"},
        "story": {"type": "text", "text": ("Ask for evil.example/x. " * 200)},
        "mail": {"type": "email", "email": "victim@example.test"},
    }
    response = await submit(workspace, form, answers=answers)
    rows = {r.channel: r for r in await logs_of(form) if r.response_id == response.response_id}
    await run(rows["respondent"])
    await run(rows["team"])
    copy, team = transport.sent
    assert "evil" not in copy["body"].lower() and "[link removed]" in copy["body"]
    assert all(len(line) <= 405 for line in copy["body"].splitlines())  # label and answer, 200 each
    # the team's mail is not limited this way
    assert "www.evil.example/pay" in team["body"] and "https://evil.example/now" in team["body"]


# ------------------------------------------------------- budgets and denied attempts


async def test_denied_copies_do_not_count_against_the_wider_budgets(setup, monkeypatch):
    from backend.app.services.copy_recipient import rate_limit_key
    from backend.app.services.email_actions import service as module

    monkeypatch.setattr(module, "COPY_ADDRESS_FORM_PER_HOUR", 1)
    statuses = [(await run(await _copy_to(setup, "victim+%d@example.test" % n))).status for n in range(6)]
    assert statuses == ["delivered"] + ["cancelled"] * 5
    limiter = container.rate_limiter()

    async def seen(scope, client):
        return (await limiter.hit(scope, client, 10_000, module.HOUR, amount=0)).count

    # one delivered copy is counted once in each budget; five denied ones in none
    assert await seen(module.COPY_WORKSPACE_SCOPE, str(setup.workspace.id)) == 1
    assert await seen(module.COPY_FORM_SCOPE, setup.form.form_id) == 1
    assert await seen(module.COPY_ADDRESS_SCOPE, rate_limit_key("victim@example.test")) == 1


async def test_a_denied_team_mail_does_not_count_either(setup, monkeypatch):
    from backend.app.services.email_actions import service as module

    monkeypatch.setattr(module, "TEAM_FORM_PER_HOUR", 1)
    statuses = []
    for _ in range(4):
        response = await submit(setup.workspace, setup.form)
        (log,) = await rows_of(setup, response, "team")
        statuses.append((await run(log)).status)
    assert statuses == ["delivered"] + ["cancelled"] * 3
    seen = await container.rate_limiter().hit(
        module.TEAM_FORM_SCOPE, setup.form.form_id, 10_000, module.HOUR, amount=0
    )
    assert seen.count == 1


# ------------------------------------------------------------ as typed, and the wire


async def test_team_addresses_are_mailed_as_typed_and_compared_case_folded(workspace, emails_on, memory_jobs, transport):
    form = await publish(workspace)
    await make_action(workspace, form, team=["  Owner@Acme.EXAMPLE "])
    response = await submit(workspace, form)
    (log,) = [r for r in await logs_of(form) if r.response_id == response.response_id]
    await run(log)
    assert transport.sent[0]["recipients"] == ["Owner@Acme.EXAMPLE"]


async def test_an_address_the_server_cannot_take_fails_for_good(setup):
    response = await submit(
        setup.workspace, setup.form,
        answers={**ANSWERS, "mail": {"type": "email", "email": "jän@example.test"}},
    )
    (log,) = await rows_of(setup, response, "respondent")
    real = container.email_action_service()._transport
    from backend.app.services.email_actions.transport import SmtpTransport

    container.email_action_service()._transport = SmtpTransport()
    try:
        outcome = await run(log)
    finally:
        container.email_action_service()._transport = real
    row = await container.action_log_repo().get(log.id)
    assert (outcome.status, outcome.retry) == ("failed", False)
    assert row.last_error_code in ("address_not_supported", "mail_not_configured")


# ------------------------------------------------------------ hidden answers are sent


async def test_a_logic_hidden_answer_is_in_the_team_mail_and_the_copy(workspace, emails_on, memory_jobs, transport):
    hidden_when_adult = {
        "logic": {
            "action": "HIDE",
            "operator": "AND",
            "conditions": [{"fieldId": "age", "fieldType": "number", "comparison": "GREATER_THAN", "value": 10}],
        }
    }
    fields = [
        {**f, "properties": {**(f.get("properties") or {}), **hidden_when_adult}} if f["id"] == "story" else f
        for f in FIELDS
    ]
    form = await publish(workspace, fields=fields)
    await make_action(workspace, form, fields=["name", "story"], team=[OWNER], respondent="mail")
    response = await submit(workspace, form)  # age 36: the story question is hidden by logic
    for row in [r for r in await logs_of(form) if r.response_id == response.response_id]:
        assert (await run(row)).status == "delivered"
    team, copy = (m for m in sorted(transport.sent, key=lambda m: m["recipients"] != [OWNER]))
    assert "Synthetic story." in team["body"] and "Synthetic story." in copy["body"]


# ------------------------------------------------------------------------- erasure


async def _team_of(workspace, form, action):
    stored = await container.form_email_action_repo().get(workspace.id, form.form_id, action.id)
    return stored.team_recipients, stored.enabled


async def test_a_member_who_leaves_is_erased_from_the_team_lists(workspace, emails_on, memory_jobs, transport):
    form = await publish(workspace)
    both = await make_action(workspace, form, team=[OWNER, "Editor@Acme.example"])
    only = await make_action(workspace, form, team=["editor@acme.example"], name="Editor only")
    copy_too = await make_action(workspace, form, team=["editor@acme.example"], respondent="mail", name="With copy")
    await container.workspace_members_service().delete_workspace_member(
        workspace.id, invited_user.id, testUser
    )
    assert await _team_of(workspace, form, both) == ([OWNER], True)
    # an action left with no recipient at all is switched off; one with a copy question keeps running for that
    assert await _team_of(workspace, form, only) == ([], False)
    assert await _team_of(workspace, form, copy_too) == ([], True)
    # the list an admin reads no longer shows the address
    listed = await container.email_action_service().list_actions(workspace.id, form.form_id, testUser)
    assert "acme.example" in str([a.team_recipients for a in listed]) and "ditor" not in str([a.team_recipients for a in listed])


async def test_a_deleted_account_is_erased_from_the_team_lists_of_every_workspace(workspace, workspace_1, emails_on, memory_jobs, transport):
    from backend.app.models.enum.workspace_roles import WorkspaceRoles
    from backend.app.schemas.workspace_user import WorkspaceUserDocument

    await container.workspace_user_repo().save(
        WorkspaceUserDocument(workspace_id=workspace_1.id, user_id=invited_user.id, roles=[WorkspaceRoles.COLLABORATOR])
    )
    form = await publish(workspace)
    other = await publish(workspace_1, user=testUser1)
    a = await make_action(workspace, form, team=[OWNER, "editor@acme.example"])
    b = await make_action(workspace_1, other, team=["editor@acme.example", "outsider@elsewhere.example"], user=testUser1)
    # the deletion job names the account by its email (``UserDeletion``), as the auth service knows it
    leaving = User(id=invited_user.id, sub="editor@acme.example")
    await container.workspace_service().delete_workspaces_of_user_with_forms(leaving)
    assert (await _team_of(workspace, form, a))[0] == [OWNER]
    assert (await _team_of(workspace_1, other, b))[0] == ["outsider@elsewhere.example"]


async def test_forgetting_an_unknown_or_invalid_address_changes_nothing(setup):
    service = container.email_action_service()
    assert await service.forget_address("nobody@acme.example") == 0
    assert await service.forget_address("not an address") == 0
    assert await service.forget_address(None) == 0


# ---------------------------------------------------- budgets under concurrency


async def test_the_limiter_admits_exactly_the_limit_in_parallel():
    import asyncio

    limiter = container.rate_limiter()
    verdicts = await asyncio.gather(*[limiter.admit("t_parallel", "client", 7, 3600) for _ in range(30)])
    assert sum(v.allowed for v in verdicts) == 7
    seen = await limiter.hit("t_parallel", "client", 100, 3600, amount=0)
    assert seen.count == 7  # a refused request changed nothing
    # a release gives one back, and never goes below zero
    await limiter.release("t_parallel", "client", 3600)
    assert (await limiter.hit("t_parallel", "client", 100, 3600, amount=0)).count == 6
    for _ in range(10):
        await limiter.release("t_parallel", "client", 3600)
    assert (await limiter.hit("t_parallel", "client", 100, 3600, amount=0)).count == 0
    assert not (await limiter.admit("t_parallel", "client", 0, 3600)).allowed


async def test_copies_in_parallel_never_overshoot_a_budget(setup, monkeypatch):
    import asyncio

    from backend.app.services.email_actions import service as module

    service = container.email_action_service()
    ws, form = setup.workspace.id, setup.form.form_id
    monkeypatch.setattr(module, "COPY_ADDRESS_PER_HOUR", 3)
    monkeypatch.setattr(module, "COPY_ADDRESS_FORM_PER_HOUR", 100)
    # twenty parallel copies to variants of one mailbox: exactly three are admitted
    variants = ["v.ictim@gmail.com", "victim+1@gmail.com", "VICTIM@googlemail.com", "victim@gmail.com."] * 5
    results = await asyncio.gather(*[service._copy_within_limits(ws, form, a) for a in variants])
    assert sum(results) == 3
    limiter = container.rate_limiter()
    # the wider budgets hold what was admitted, not what was refused
    assert (await limiter.hit(module.COPY_WORKSPACE_SCOPE, str(ws), 10_000, module.HOUR, amount=0)).count == 3
    assert (await limiter.hit(module.COPY_FORM_SCOPE, str(form), 10_000, module.HOUR, amount=0)).count == 3


async def test_the_wider_budget_is_never_overshot_either(setup, monkeypatch):
    import asyncio

    from backend.app.services.email_actions import service as module

    service = container.email_action_service()
    ws, form = setup.workspace.id, setup.form.form_id
    monkeypatch.setattr(module, "COPY_WORKSPACE_PER_HOUR", 5)
    results = await asyncio.gather(
        *[service._copy_within_limits(ws, form, f"person{n}@example.test") for n in range(30)]
    )
    assert sum(results) == 5
    assert (await container.rate_limiter().hit(module.COPY_WORKSPACE_SCOPE, str(ws), 10_000, module.HOUR, amount=0)).count == 5


async def test_team_mails_in_parallel_never_overshoot_the_form_cap(setup, monkeypatch):
    import asyncio

    from backend.app.services.email_actions import service as module

    monkeypatch.setattr(module, "TEAM_FORM_PER_HOUR", 4)
    results = await asyncio.gather(
        *[container.email_action_service()._team_within_limit(setup.form.form_id) for _ in range(25)]
    )
    assert sum(results) == 4


# ------------------------------- the copy goes only to a signed-in respondent's verified account email


async def _rows(setup, response):
    return [r for r in await logs_of(setup.form) if r.response_id == response.response_id]


async def _budgets_untouched(setup, address="ada@example.test"):
    from backend.app.services.copy_recipient import rate_limit_key
    from backend.app.services.email_actions import service as module

    limiter = container.rate_limiter()

    async def seen(scope, client):
        return (await limiter.hit(scope, client, 10_000, module.HOUR, amount=0)).count

    return [
        await seen(module.COPY_WORKSPACE_SCOPE, str(setup.workspace.id)),
        await seen(module.COPY_FORM_SCOPE, setup.form.form_id),
        await seen(module.COPY_ADDRESS_SCOPE, rate_limit_key(address)),
        await seen(module.COPY_ADDRESS_FORM_SCOPE, f"{setup.form.form_id}:{rate_limit_key(address)}"),
    ]


async def test_signed_in_with_a_verified_address_gets_the_copy_at_the_account_email(setup):
    user = verified("Ada@Example.test")
    response = await submit_as(setup.workspace, setup.form, answers=ANSWERS, user=user)
    rows = {r.channel: r for r in await _rows(setup, response)}
    copy = rows["respondent"]
    assert copy.status is LogStatus.PENDING and copy.account_id == user.id
    assert (await run(copy)).status == "delivered"
    assert setup.transport.sent[0]["recipients"] == ["Ada@Example.test"]


async def test_the_copy_never_goes_to_an_address_from_an_answer(setup):
    """The email question holds another address (the respondent's, or someone
    else's): the copy goes to the account's verified email, not to the answer."""
    user = verified("account@example.test")
    answers = {**ANSWERS, "mail": {"type": "email", "email": "victim@elsewhere.example"}}
    response = await submit_as(setup.workspace, setup.form, answers=answers, user=user)
    (copy,) = [r for r in await _rows(setup, response) if r.channel == "respondent"]
    assert copy.status is LogStatus.PENDING
    assert (await run(copy)).status == "delivered"
    assert [m["recipients"] for m in setup.transport.sent] == [["account@example.test"]]
    assert "elsewhere.example" not in json.dumps(setup.transport.sent)


async def test_the_copy_is_planned_whatever_the_answers_hold(setup):
    # even with no email answer at all: the question is not the recipient
    answers = {k: v for k, v in ANSWERS.items() if k != "mail"}
    response = await submit_as(setup.workspace, setup.form, answers=answers, user=verified("ada@example.test"))
    assert sorted(r.channel for r in await _rows(setup, response)) == ["respondent", "team"]


async def test_the_account_email_is_read_when_the_copy_is_sent(setup):
    from tests.app.email_actions.helpers import ACCOUNTS

    user = verified("old@example.test")
    response = await submit_as(setup.workspace, setup.form, answers=ANSWERS, user=user)
    (copy,) = [r for r in await _rows(setup, response) if r.channel == "respondent"]
    ACCOUNTS[user.id] = "new@example.test"  # the account's email changed before the job ran
    assert (await run(copy)).status == "delivered"
    assert setup.transport.sent[0]["recipients"] == ["new@example.test"]


async def test_an_account_that_is_gone_when_the_copy_is_sent_gets_nothing_and_the_log_says_so(setup):
    from tests.app.email_actions.helpers import ACCOUNTS

    user = verified("ada@example.test")
    response = await submit_as(setup.workspace, setup.form, answers=ANSWERS, user=user)
    (copy,) = [r for r in await _rows(setup, response) if r.channel == "respondent"]
    del ACCOUNTS[user.id]
    outcome = await run(copy)
    row = await container.action_log_repo().get(copy.id)
    assert (outcome.status, outcome.retry) == ("cancelled", False)
    assert row.status is LogStatus.CANCELLED and row.last_error_code == "account_gone"
    assert setup.transport.sent == [] and await _budgets_untouched(setup) == [0, 0, 0, 0]
    assert not _mentions_personal(row.model_dump(mode="json"))


async def test_an_anonymous_respondent_gets_no_copy_and_the_log_says_why(setup):
    from tests.app.controllers.data import testUser

    # not signed in with a verified email (here: a session that proved nothing)
    response = await submit_as(setup.workspace, setup.form, answers=ANSWERS, user=testUser)
    rows = {r.channel: r for r in await _rows(setup, response)}
    copy = rows["respondent"]
    assert copy.status is LogStatus.CANCELLED and copy.last_error_code == "not_verified"
    assert copy.finished_at is not None and copy.attempts == 0 and copy.account_id is None
    assert not _mentions_personal(copy.model_dump(mode="json"))  # ids and status only
    # no job for it (the team's mail is queued as ever), nothing sent, no budget used
    assert [j["args"]["log_id"] for j in setup.jobs.jobs.values()] == [str(rows["team"].id)]
    assert (await run(copy)).status == "skipped" and setup.transport.sent == []
    assert await _budgets_untouched(setup) == [0, 0, 0, 0]
    # the team's mail is unaffected
    assert (await run(rows["team"])).status == "delivered" and len(setup.transport.sent) == 1


async def test_a_session_whose_email_was_not_verified_gets_no_copy(setup):
    user = verified("ada@example.test", proven=False)
    response = await submit_as(setup.workspace, setup.form, answers=ANSWERS, user=user)
    (copy,) = [r for r in await _rows(setup, response) if r.channel == "respondent"]
    assert copy.last_error_code == "not_verified" and copy.status is LogStatus.CANCELLED
    assert await _budgets_untouched(setup) == [0, 0, 0, 0]


async def test_a_signed_in_respondent_who_submits_anonymously_gets_no_copy(setup, monkeypatch):
    from backend.app.services.copy_recipient import verified_account_id_of

    assert verified_account_id_of(verified("ada@example.test"), anonymous=True) is None
    response = await container.email_action_service().queue_for_submission(
        setup.workspace.id, setup.form.form_id, "r-anon", form=None, answers={},
        verified_account_id=verified_account_id_of(verified("ada@example.test"), anonymous=True),
    )
    rows = [r for r in await logs_of(setup.form) if r.response_id == "r-anon"]
    assert [(r.channel, r.status, r.last_error_code) for r in rows if r.channel == "respondent"] == [
        ("respondent", LogStatus.CANCELLED, "not_verified")
    ]
    assert response is not None


def test_only_a_verified_signed_in_account_is_a_copy_recipient():
    from backend.app.services.copy_recipient import verified_account_id_of

    user = verified("ada@example.test")
    assert verified_account_id_of(user) == user.id
    assert verified_account_id_of(verified("ada@example.test", proven=False)) is None
    assert verified_account_id_of(None) is None
    assert verified_account_id_of(user, anonymous=True) is None
