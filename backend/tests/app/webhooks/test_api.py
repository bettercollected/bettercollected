"""Webhook configuration: the secret is generated, shown once and sealed, the
address is checked, only mapped questions can be chosen, a form can only use its
own workspace, changes are audited, the test event is real and rate limited, the
log is retained 30 days, and the respondent's form names the destination."""

import datetime as dt
import json

import pytest
from common.clock import utcnow
from httpx import AsyncClient
from loguru import logger

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.webhook import LogStatus
from backend.app.services.registration.secrets import SecretUnreadable, unseal
from backend.app.services.webhooks import payload
from backend.app.services.webhooks.sealing import seal_url, unseal_url
from backend.app.services.webhooks.service import (
    MAX_WEBHOOKS_PER_FORM,
    FieldDto,
    WebhookCreateDto,
    WebhookUpdateDto,
)
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.registration.helpers import publish, submit
from tests.app.webhooks.helpers import URL, logs_of, make_webhook

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def lines():
    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    yield seen
    logger.remove(handler)


@pytest.fixture(autouse=True)
def switched_on(webhooks_on, public_dns):
    pass


def service():
    return container.webhook_service()


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    content = error.content
    return content["code"] if isinstance(content, dict) else str(content)


async def test_the_secret_is_generated_shown_once_and_sealed(workspace, lines):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    assert created.secret.startswith("whsec_") and len(created.secret) >= 40
    other = await make_webhook(workspace, form, ["name"])
    assert other.secret != created.secret
    # the only response that carries it is the create (and the rotate)
    dumped = created.model_dump_json(by_alias=True)
    assert json.loads(dumped)["secret"] == created.secret
    listed = await service().list_webhooks(workspace.id, form.form_id, testUser)
    assert created.secret not in json.dumps([w.model_dump(mode="json") for w in listed])
    assert all(w.has_secret and w.secret_set_at for w in listed)
    row = await container.form_webhook_repo().get(workspace.id, form.form_id, created.id)
    assert created.secret not in json.dumps(row.model_dump(mode="json")) and row.secret_sealed
    # sealed for this workspace and webhook: it opens only for them
    crypto = container.crypto()
    assert unseal(crypto, workspace.id, created.id, row.secret_sealed) == created.secret
    with pytest.raises(SecretUnreadable):
        unseal(crypto, workspace.id, other.id, row.secret_sealed)
    with pytest.raises(SecretUnreadable):
        unseal(crypto, "another-workspace", created.id, row.secret_sealed)
    assert not any(created.secret in line for line in lines)


async def test_rotating_shows_a_new_secret_once_and_the_old_one_stops_working(workspace, tls, memory_jobs):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    rotated = await service().rotate_secret(workspace.id, form.form_id, created.id, testUser)
    assert rotated.secret != created.secret and rotated.id == created.id
    response = await submit(workspace, form)
    (log,) = [r for r in await logs_of(form) if r.response_id == response.response_id]
    await service().run_delivery(str(log.id))
    (request,) = tls.requests
    stamp = int(request.headers["x-bettercollected-timestamp"])
    signature = request.headers["x-bettercollected-signature"]
    assert payload.verify(rotated.secret, stamp, request.body, signature)
    assert not payload.verify(created.secret, stamp, request.body, signature)


async def test_the_address_is_checked_and_stored_normalised(workspace):
    form = await publish(workspace)
    for url, code in [
        ("http://case.example.org/h", "not_https"),
        ("https://user:pw@case.example.org/h", "invalid_url"),
        ("https://case.example.org:8443/h", "invalid_url"),
        ("https://127.0.0.1/h", "invalid_url"),
        ("https://localhost/h", "invalid_url"),
    ]:
        error = await refused(make_webhook(workspace, form, url=url))
        assert error.status_code == 422 and code_of(error) == code, url
    created = await make_webhook(workspace, form, url="https://Case.Example.ORG/h#x")
    assert created.host == "case.example.org"
    detail = await service().get_webhook(workspace.id, form.form_id, created.id, testUser)
    assert detail.url == "https://case.example.org/h"


async def test_a_name_that_resolves_inward_is_refused_when_saved(workspace, monkeypatch):
    from backend.app.services.registration import client

    form = await publish(workspace)

    async def resolve(host, port=443):
        return ["10.1.2.3"]

    monkeypatch.setattr(client, "resolve", resolve)
    error = await refused(make_webhook(workspace, form))
    assert error.status_code == 422 and code_of(error) == "not_allowed"
    assert await container.form_webhook_repo().count_for_form(workspace.id, form.form_id) == 0


async def test_only_questions_of_the_form_can_be_mapped_with_unique_keys(workspace):
    form = await publish(workspace)
    for fields, code in [
        ([FieldDto(source="nope")], "unknown_variable"),
        ([FieldDto(source="upload")], "file_not_sent"),
        ([FieldDto(source="intro")], "variable_not_supported"),
        ([FieldDto(source="name", key="a b")], "invalid_key"),
        ([FieldDto(source="name", key="1x")], "invalid_key"),
        ([FieldDto(source="name", key="x"), FieldDto(source="age", key="x")], "invalid_key"),
        ([FieldDto(source="name", key="x"), FieldDto(source="name", key="y")], "invalid_key"),
        ([FieldDto(source="people.pname")], "unknown_variable"),
    ]:
        error = await refused(make_webhook(workspace, form, fields=fields))
        assert (error.status_code, code_of(error)) == (422, code), fields
    created = await make_webhook(
        workspace, form, fields=[FieldDto(source="name", key="full_name"), FieldDto(source="people")]
    )
    assert [(f.source, f.key) for f in created.fields] == [("name", "full_name"), ("people", "people")]


async def test_the_variables_list_marks_files_as_not_sent(workspace):
    form = await publish(workspace)
    listed = {v.source: v for v in await service().list_variables(workspace.id, form.form_id, testUser)}
    assert listed["name"].supported and not listed["upload"].supported
    assert listed["upload"].reason == "file_not_sent"
    assert "people.pname" not in listed


async def test_a_form_has_a_limited_number_of_webhooks(workspace):
    form = await publish(workspace)
    for _ in range(MAX_WEBHOOKS_PER_FORM):
        await make_webhook(workspace, form, ["name"])
    error = await refused(make_webhook(workspace, form, ["name"]))
    assert (error.status_code, code_of(error)) == (422, "too_many_webhooks")


async def test_update_enable_disable_and_delete_are_audited_without_values(workspace, lines):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    ws, fid = workspace.id, form.form_id
    await service().update_webhook(ws, fid, created.id, WebhookUpdateDto(enabled=False), testUser)
    await service().update_webhook(ws, fid, created.id, WebhookUpdateDto(enabled=True), testUser)
    updated = await service().update_webhook(
        ws, fid, created.id,
        WebhookUpdateDto(url="https://other.example.org/x", fields=[FieldDto(source="name")]),
        testUser,
    )
    assert updated.host == "other.example.org" and [f.source for f in updated.fields] == ["name"]
    # nothing changed: no entry
    await service().update_webhook(ws, fid, created.id, WebhookUpdateDto(enabled=True), testUser)
    await service().rotate_secret(ws, fid, created.id, testUser)
    await service().delete_webhook(ws, fid, created.id, testUser)
    entries = list(reversed(await service().list_audit(ws, fid, testUser)))
    assert [e.event for e in entries] == [
        "created", "disabled", "enabled", "updated", "secret_rotated", "deleted",
    ]
    assert entries[3].changed == ["url", "fields"]
    assert all(e.actor_id == str(testUser.id) and e.webhook_id == created.id for e in entries)
    stored = json.dumps([e.model_dump(mode="json") for e in entries])
    for text in ("whsec_", "example.org/x", "hooks/intake", created.secret):
        assert text not in stored
    assert await container.form_webhook_repo().count_for_form(ws, fid) == 0
    assert not any(created.secret in line or "hooks/intake" in line for line in lines)


async def test_switch_off_refuses_create_enable_and_test_but_not_disable_or_delete(
    workspace, monkeypatch, tls, memory_jobs
):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    off = await make_webhook(workspace, form, enabled=False)
    monkeypatch.setattr(settings.webhooks, "ENABLED", False)
    ws, fid = workspace.id, form.form_id
    for call in (
        make_webhook(workspace, form),
        service().update_webhook(ws, fid, off.id, WebhookUpdateDto(enabled=True), testUser),
        service().send_test(ws, fid, created.id, testUser),
    ):
        error = await refused(call)
        assert (error.status_code, code_of(error)) == (422, "webhooks_off")
    assert memory_jobs.jobs == {} and tls.requests == []
    await service().update_webhook(ws, fid, created.id, WebhookUpdateDto(enabled=False), testUser)
    # other edits of a switched off webhook are fine while the server is off
    await service().update_webhook(ws, fid, off.id, WebhookUpdateDto(fields=[FieldDto(source="age")]), testUser)
    await service().delete_webhook(ws, fid, created.id, testUser)
    assert (await service().list_webhooks(ws, fid, testUser))[0].id == off.id
    assert service().status().enabled is False


async def test_a_webhook_of_another_workspace_or_form_is_not_there(workspace, workspace_1):
    form = await publish(workspace)
    other_form = await publish(workspace_1, user=testUser1)
    created = await make_webhook(workspace, form)
    foreign = await make_webhook(workspace_1, other_form, user=testUser1)
    ws, fid = workspace.id, form.form_id
    # another workspace's webhook, through this workspace's form
    for call in (
        service().update_webhook(ws, fid, foreign.id, WebhookUpdateDto(enabled=False), testUser),
        service().delete_webhook(ws, fid, foreign.id, testUser),
        service().rotate_secret(ws, fid, foreign.id, testUser),
        service().send_test(ws, fid, foreign.id, testUser),
    ):
        assert (await refused(call)).status_code == 404
    # this workspace's webhook, through another workspace's form
    for call in (
        service().update_webhook(workspace_1.id, other_form.form_id, created.id, WebhookUpdateDto(enabled=False), testUser1),
        service().delete_webhook(workspace_1.id, other_form.form_id, created.id, testUser1),
    ):
        assert (await refused(call)).status_code == 404
    # a form of another workspace
    assert (await refused(service().list_webhooks(ws, other_form.form_id, testUser))).status_code == 404
    assert (await refused(make_webhook(workspace, other_form))).status_code == 404
    assert len(await service().list_webhooks(workspace_1.id, other_form.form_id, testUser1)) == 1


# --------------------------------------------------------------- test event


async def test_the_test_event_is_a_real_signed_delivery_of_sample_data(workspace, tls, memory_jobs, lines):
    form = await publish(workspace)
    created = await make_webhook(workspace, form, ["name", "age", "mail", "agree", "born", "colour", "colours", "people"])
    queued = await service().send_test(workspace.id, form.form_id, created.id, testUser)
    assert queued.event == "test" and queued.response_id is None and queued.status == "pending"
    (job,) = memory_jobs.jobs.values()
    assert job["queue_name"] == "webhooks" and job["args"] == {"log_id": queued.id}
    assert tls.requests == []
    outcome = await service().run_delivery(queued.id)
    assert outcome.status == "delivered"
    (request,) = tls.requests
    sent = json.loads(request.body)
    assert sent["event"] == "test" and sent["response_id"] is None and sent["delivery_id"] == queued.id
    assert sent["data"] == {
        "name": "Example text", "age": 42, "mail": "person@example.com", "agree": True,
        "born": "2026-01-31", "colour": "Example option", "colours": ["Example option"], "people": [],
    }
    assert request.headers["x-bettercollected-event"] == "test"
    assert payload.verify(
        created.secret, int(request.headers["x-bettercollected-timestamp"]), request.body,
        request.headers["x-bettercollected-signature"],
    )
    assert not any("Example text" in line for line in lines)


async def test_a_test_goes_to_a_webhook_that_is_switched_off(workspace, tls, memory_jobs):
    form = await publish(workspace)
    created = await make_webhook(workspace, form, enabled=False)
    queued = await service().send_test(workspace.id, form.form_id, created.id, testUser)
    assert (await service().run_delivery(queued.id)).status == "delivered"
    assert len(tls.requests) == 1


async def test_test_events_are_rate_limited(workspace, tls, memory_jobs):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    from backend.app.services.webhooks.service import TEST_PER_WINDOW

    for _ in range(TEST_PER_WINDOW):
        await service().send_test(workspace.id, form.form_id, created.id, testUser)
    error = await refused(service().send_test(workspace.id, form.form_id, created.id, testUser))
    assert error.status_code == 429 and code_of(error) == "rate_limited"
    assert int(error.headers["Retry-After"]) >= 1
    assert len(memory_jobs.jobs) == TEST_PER_WINDOW


# ---------------------------------------------------------------- the log


async def test_the_log_lists_ids_statuses_and_timings_never_answers(workspace, tls, memory_jobs):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    response = await submit(workspace, form)
    (log,) = await logs_of(form)
    await service().run_delivery(str(log.id))
    page = await service().list_deliveries(workspace.id, form.form_id, testUser)
    assert page.total == 1
    (item,) = page.items
    assert item.status == "delivered" and item.action_type == "webhook"
    assert item.webhook_id == created.id and item.host == "case.example.org"
    assert item.response_id == response.response_id and item.attempts == 1
    assert item.last_http_status == 200 and item.last_duration_ms is not None
    dumped = json.dumps(item.model_dump(mode="json"))
    for text in ("Ada Example", "ada@example.test", "hooks/intake", created.secret):
        assert text not in dumped
    only_failed = await service().list_deliveries(workspace.id, form.form_id, testUser, statuses=["failed"])
    assert only_failed.total == 0 and only_failed.items == []
    junk = await service().list_deliveries(workspace.id, form.form_id, testUser, statuses=["nonsense"])
    assert junk.total == 0


async def age(repo, row, delta):
    """Move a row's creation back in time (the column the purge reads)."""
    from sqlalchemy import update

    from backend.db.models import ActionLogRow

    async with repo._session() as session, session.begin():
        await session.execute(
            update(ActionLogRow)
            .where(ActionLogRow.id == str(row.id))
            .values(created_at=utcnow() - delta)
        )


async def test_the_purge_deletes_runs_older_than_30_days_and_keeps_the_rest(workspace, memory_jobs):
    form = await publish(workspace)
    await make_webhook(workspace, form)
    repo = container.action_log_repo()
    for _ in range(3):
        await submit(workspace, form)
    rows = await logs_of(form)
    assert len(rows) == 3
    old, edge, fresh = rows
    await age(repo, old, dt.timedelta(days=31))
    await age(repo, edge, dt.timedelta(days=29, hours=23))
    assert await service().purge_expired() == 1
    left = {str(r.id) for r in await logs_of(form)}
    assert left == {str(edge.id), str(fresh.id)}
    assert await service().purge_expired() == 0


async def test_the_purge_task_runs_daily_on_its_queue(workspace, memory_jobs):
    from backend.jobs import tasks

    form = await publish(workspace)
    await make_webhook(workspace, form)
    await submit(workspace, form)
    (row,) = await logs_of(form)
    await age(container.action_log_repo(), row, dt.timedelta(days=40))
    assert await tasks.purge_action_logs(0) == "1 deleted"
    assert await logs_of(form) == []
    assert tasks.app.periodic_registry.periodic_tasks  # registered with a cron
    assert any(
        p.task.name == "purge_action_logs" and p.cron == "41 3 * * *"
        for p in tasks.app.periodic_registry.periodic_tasks.values()
    )


async def test_deleting_the_form_removes_its_webhooks_log_and_audit(workspace, memory_jobs):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    await submit(workspace, form)
    assert await logs_of(form)
    await container.workspace_form_service().delete_form_from_workspace(
        workspace.id, form.form_id, testUser
    )
    assert await container.form_webhook_repo().get_by_id(created.id) is None
    assert await logs_of(form) == []
    assert await container.webhook_audit_repo().list_for_form(workspace.id, form.form_id) == []


# --------------------------------------------------------- privacy panel


async def test_the_privacy_panel_names_the_hosts_of_enabled_webhooks(workspace, client: AsyncClient, monkeypatch):
    form = await publish(workspace)
    ws, fid = workspace.id, form.form_id
    assert await service().destination_for(ws, fid) is None
    hook = await make_webhook(workspace, form, url="https://one.example.org/a")
    await make_webhook(workspace, form, ["name"], url="https://one.example.org/b")
    await make_webhook(workspace, form, ["name"], url="https://two.example.org/b")
    await make_webhook(workspace, form, ["name"], url="https://off.example.org/b", enabled=False)
    assert await service().destination_for(ws, fid) == {"hosts": ["one.example.org", "two.example.org"]}
    # the published form carries it for respondents
    published = await client.get(f"/api/v1/workspaces/{ws}/forms/{fid}?published=true")
    assert published.status_code == 200, published.text
    assert published.json()["webhookDestination"] == {"hosts": ["one.example.org", "two.example.org"]}
    # the draft read (staff) does not
    monkeypatch.setattr(settings.webhooks, "ENABLED", False)
    assert await service().destination_for(ws, fid) is None
    again = await client.get(f"/api/v1/workspaces/{ws}/forms/{fid}?published=true")
    assert "webhookDestination" not in again.json() or again.json()["webhookDestination"] is None
    monkeypatch.setattr(settings.webhooks, "ENABLED", True)
    await service().delete_webhook(ws, fid, hook.id, testUser)


# --------------------------------------------------- the address is sealed


TOKEN_URL = "https://case.example.org/hooks/intake?key=tok-8f3a1c"


async def test_the_address_is_sealed_and_only_the_owner_view_opens_it(workspace, lines):
    form = await publish(workspace)
    created = await make_webhook(workspace, form, url=TOKEN_URL)
    ws, fid = workspace.id, form.form_id
    # the stored row holds the host in clear and the address only sealed
    row = await container.form_webhook_repo().get(ws, fid, created.id)
    stored = json.dumps(row.model_dump(mode="json"))
    for text in ("tok-8f3a1c", "hooks/intake", "https://"):
        assert text not in stored
    assert row.host == "case.example.org" and row.url_sealed
    assert unseal_url(container.crypto(), ws, created.id, row.url_sealed) == TOKEN_URL
    # the create response, the list and the audit trail never carry it
    listed = await service().list_webhooks(ws, fid, testUser)
    audit = await service().list_audit(ws, fid, testUser)
    for dump in (
        created.model_dump_json(by_alias=True),
        json.dumps([w.model_dump(mode="json") for w in listed]),
        json.dumps([a.model_dump(mode="json") for a in audit]),
    ):
        assert "tok-8f3a1c" not in dump and "hooks/intake" not in dump
        assert '"url"' not in dump
    # the owner-facing view opens it
    detail = await service().get_webhook(ws, fid, created.id, testUser)
    assert detail.url == TOKEN_URL and detail.host == "case.example.org"
    # logs never have it
    assert not any("tok-8f3a1c" in line or "hooks/intake" in line for line in lines)


async def test_a_sealed_address_is_bound_to_its_webhook_and_purpose(workspace):
    form = await publish(workspace)
    one = await make_webhook(workspace, form, url=TOKEN_URL)
    two = await make_webhook(workspace, form, ["name"])
    crypto = container.crypto()
    row = await container.form_webhook_repo().get(workspace.id, form.form_id, one.id)
    other = await container.form_webhook_repo().get(workspace.id, form.form_id, two.id)
    with pytest.raises(SecretUnreadable):
        unseal_url(crypto, workspace.id, two.id, row.url_sealed)
    with pytest.raises(SecretUnreadable):
        unseal_url(crypto, "another-workspace", one.id, row.url_sealed)
    with pytest.raises(SecretUnreadable):
        unseal_url(crypto, workspace.id, one.id, "not a ciphertext")
    with pytest.raises(SecretUnreadable):
        unseal_url(crypto, workspace.id, one.id, "")
    # the sealed address cannot be opened as a secret, nor the secret as an address
    with pytest.raises(SecretUnreadable):
        unseal(crypto, workspace.id, one.id, row.url_sealed)
    with pytest.raises(SecretUnreadable):
        unseal_url(crypto, workspace.id, one.id, row.secret_sealed)
    # a copied sealed address does not open under another webhook's id either
    assert other.url_sealed != row.url_sealed


async def test_updating_the_address_reseals_it_and_audits_the_name_only(workspace):
    form = await publish(workspace)
    created = await make_webhook(workspace, form, url=TOKEN_URL)
    ws, fid = workspace.id, form.form_id
    before = (await container.form_webhook_repo().get(ws, fid, created.id)).url_sealed
    # the same address again: nothing changes, no entry
    await service().update_webhook(ws, fid, created.id, WebhookUpdateDto(url=TOKEN_URL), testUser)
    assert (await container.form_webhook_repo().get(ws, fid, created.id)).url_sealed == before
    new = "https://other.example.org/x?key=tok-new"
    updated = await service().update_webhook(ws, fid, created.id, WebhookUpdateDto(url=new), testUser)
    assert updated.host == "other.example.org"
    assert (await service().get_webhook(ws, fid, created.id, testUser)).url == new
    entries = await service().list_audit(ws, fid, testUser)
    assert [e.event for e in reversed(entries)] == ["created", "updated"]
    assert entries[0].changed == ["url"]
    assert "tok-new" not in json.dumps([e.model_dump(mode="json") for e in entries])
    # an edit that leaves the address out keeps it
    await service().update_webhook(ws, fid, created.id, WebhookUpdateDto(enabled=False), testUser)
    assert (await service().get_webhook(ws, fid, created.id, testUser)).url == new


async def test_the_job_opens_the_address_and_sends_to_it(workspace, tls, memory_jobs):
    form = await publish(workspace)
    await make_webhook(workspace, form, url=TOKEN_URL)
    await submit(workspace, form)
    (log,) = await logs_of(form)
    assert (await service().run_delivery(str(log.id))).status == "delivered"
    (request,) = tls.requests
    assert request.target == "/hooks/intake?key=tok-8f3a1c"
    for job in memory_jobs.jobs.values():
        assert "tok-8f3a1c" not in json.dumps(job, default=str)
    stored = json.dumps((await container.action_log_repo().get(log.id)).model_dump(mode="json"))
    assert "tok-8f3a1c" not in stored


async def test_an_unreadable_address_fails_the_delivery_for_good(workspace, tls, memory_jobs):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    await submit(workspace, form)
    (log,) = await logs_of(form)
    repo = container.form_webhook_repo()
    row = await repo.get(workspace.id, form.form_id, created.id)
    row.url_sealed = "garbage"
    await repo.save(row)
    outcome = await service().run_delivery(str(log.id))
    done = await container.action_log_repo().get(log.id)
    assert (outcome.status, outcome.retry) == ("failed", False)
    assert done.last_error_code == "url_unreadable" and tls.requests == []
    error = await refused(service().get_webhook(workspace.id, form.form_id, created.id, testUser))
    assert error.status_code == 409 and code_of(error) == "url_unreadable"
    # saving a new address repairs it
    await service().update_webhook(
        workspace.id, form.form_id, created.id, WebhookUpdateDto(url=TOKEN_URL), testUser
    )
    assert (await service().get_webhook(workspace.id, form.form_id, created.id, testUser)).url == TOKEN_URL


async def test_the_form_is_not_served_when_the_disclosure_cannot_be_read(
    workspace, client: AsyncClient, monkeypatch, memory_jobs
):
    """Fail closed: if the privacy panel could not name the webhook hosts, the
    published form is refused, so no one submits to a form whose destinations
    were not shown."""
    form = await publish(workspace)
    await make_webhook(workspace, form)
    ws, fid = workspace.id, form.form_id
    ok = await client.get(f"/api/v1/workspaces/{ws}/forms/{fid}?published=true")
    assert ok.status_code == 200 and ok.json()["webhookDestination"] == {"hosts": ["case.example.org"]}

    async def broken(*args, **kwargs):
        raise RuntimeError("database trouble")

    monkeypatch.setattr(container.webhook_service(), "destination_for", broken)
    refused_load = await client.get(f"/api/v1/workspaces/{ws}/forms/{fid}?published=true")
    assert refused_load.status_code == 503, refused_load.text
    assert refused_load.json()["code"] == "form_unavailable"
    assert "webhookDestination" not in refused_load.text
    assert memory_jobs.jobs == {}
