"""The legacy list, Slack and Discord formats end to end: a webhook that a
built-in action moved into (they cannot be created through the API) sends the
body the executor sent, on the same queue, retry and log as every webhook, to
the same checked destinations; creators can only move a legacy list webhook to
the signed envelope."""

import json
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from loguru import logger

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.webhook import LogStatus
from backend.app.services.registration import client
from backend.app.services.registration.client import PinnedBackend
from backend.app.services.webhooks import formats, payload
from backend.app.services.webhooks.sealing import seal_url, unseal_url
from backend.app.services.webhooks.service import (
    FieldDto,
    WebhookCreateDto,
    WebhookUpdateDto,
)
from tests.app.controllers.data import testUser
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.registration.conftest import memory_jobs  # noqa: F401
from tests.app.registration.helpers import ANSWERS, publish, submit
from tests.app.registration.tls_server import PUBLIC_ADDRESS, DialToServer, TlsServer
from tests.app.webhooks.helpers import logs_of, make_webhook

pytestmark = pytest.mark.asyncio

SLACK_URL = "https://hooks.slack.com/services/T000/B000/token-value"
DISCORD_URL = "https://discord.com/api/webhooks/123456/token-value"
LEGACY_URL = "https://case.example.org/hooks/old"


@pytest.fixture(autouse=True)
def switched_on(webhooks_on, public_dns):
    pass


@pytest.fixture()
def lines():
    seen = []
    handler = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    yield seen
    logger.remove(handler)


def tls_for(host):
    """A local https server answering as ``host`` (the chat formats may only go
    to their own hosts, so the one in ``conftest`` is not enough)."""

    @pytest.fixture()
    async def fixture(monkeypatch):
        async with TlsServer(host) as server:

            async def resolve(name, port=443):
                return [PUBLIC_ADDRESS]

            monkeypatch.setattr(client, "resolve", resolve)
            monkeypatch.setattr(
                client,
                "network_backend",
                lambda name, address: PinnedBackend(
                    name, address, inner=DialToServer(server)
                ),
            )
            monkeypatch.setattr(client, "ssl_context", server.client_context)
            yield server

    return fixture


slack_server = tls_for("hooks.slack.com")
discord_server = tls_for("discord.com")
legacy_server = tls_for("case.example.org")


async def moved(workspace, form, format_, url, *, secret=True, **values):
    """What the move of a built-in action leaves: a webhook row of that format
    (made by hand here: the API cannot create one)."""
    created = await make_webhook(workspace, form, ["name"], enabled=True)
    repo = container.form_webhook_repo()
    row = await repo.get(workspace.id, form.form_id, created.id)
    row.format = format_
    row.fields = []
    row.all_questions = format_ == formats.ENVELOPE
    row.created_via = "migrated_builtin"
    row.source_action_id = "65b0000000000000000000a1"
    row.url_sealed = seal_url(container.crypto(), workspace.id, row.id, url)
    row.host = url.split("/")[2]
    if not secret:
        row.secret_sealed = None
        row.secret_set_at = None
    for key, value in values.items():
        setattr(row, key, value)
    await repo.save(row)
    return SimpleNamespace(id=str(row.id), secret=created.secret)


async def deliver(workspace, form, hook, memory_jobs):
    response = await submit(workspace, form)
    (row,) = [
        r
        for r in await logs_of(form)
        if r.response_id == response.response_id and r.action_id == hook.id
    ]
    outcome = await container.webhook_service().run_delivery(str(row.id))
    return response, row, outcome


async def test_a_legacy_list_webhook_sends_the_executors_body_signed(
    workspace, legacy_server, memory_jobs, lines
):
    form = await publish(workspace)
    hook = await moved(workspace, form, formats.LEGACY_LIST, LEGACY_URL)
    response, log, outcome = await deliver(workspace, form, hook, memory_jobs)
    assert outcome.status == "delivered"
    (request,) = legacy_server.requests
    sent = json.loads(request.body)
    assert isinstance(sent, list)  # a bare list, not the envelope
    assert [e["field_id"] for e in sent] == [
        "name", "story", "mail", "age", "agree", "born", "colour", "colours",
        "upload", "people.0.pname", "people.0.pyears", "people.1.pname",
        "people.1.pyears", "intro",
    ]
    by_id = {e["field_id"]: e for e in sent}
    assert by_id["name"] == {"field_id": "name", "title": "Full name", "answer": "Ada Example"}
    assert by_id["agree"]["answer"] == "Yes" and by_id["colours"]["answer"] == "Red, Blue"
    assert by_id["people.1.pyears"]["answer"] == ""
    # the executor's own serialization, byte for byte
    assert request.body == json.dumps(sent).encode()
    h = request.headers
    assert h["content-type"] == "application/json"
    # new: the signature headers of every webhook
    timestamp = int(h["x-bettercollected-timestamp"])
    assert payload.verify(hook.secret, timestamp, request.body, h["x-bettercollected-signature"])
    assert h["x-bettercollected-delivery"] == str(log.id)
    # nothing of the answers in logs, the log row or the queue
    done = await container.action_log_repo().get(log.id)
    assert done.status is LogStatus.DELIVERED
    stored = json.dumps(done.model_dump(mode="json"))
    for text in ("Ada Example", "ada@example.test", "Synthetic story."):
        assert text not in stored and not any(text in line for line in lines)
        assert text not in json.dumps(list(memory_jobs.jobs.values()), default=str)


async def test_the_legacy_list_matches_the_executors_own_code(
    workspace, legacy_server, memory_jobs
):
    from tests.app.builtin_actions.regenerate_golden import (
        EXECUTOR_FORM,
        load_executor_form,
    )

    if not EXECUTOR_FORM.exists():
        pytest.skip("the actions executor is no longer in the repository")
    form = await publish(workspace)
    hook = await moved(workspace, form, formats.LEGACY_LIST, LEGACY_URL)
    response, _log, outcome = await deliver(workspace, form, hook, memory_jobs)
    assert outcome.status == "delivered"
    executor = load_executor_form()
    latest = await container.form_repo().get_latest_version_of_form(form.form_id)
    expected = executor.get_questions_and_answers(
        formats.form_view(latest), {"response_id": response.response_id, "answers": ANSWERS}
    )
    assert legacy_server.requests[0].body == json.dumps(expected).encode()


async def test_slack_gets_its_message_unsigned(workspace, slack_server, memory_jobs):
    form = await publish(workspace)
    hook = await moved(workspace, form, formats.SLACK, SLACK_URL, secret=False)
    response, log, outcome = await deliver(workspace, form, hook, memory_jobs)
    assert outcome.status == "delivered"
    (request,) = slack_server.requests
    assert request.target == "/services/T000/B000/token-value"
    sent = json.loads(request.body)
    (attachment,) = sent["attachments"]
    assert "Registration test" in attachment["title"]
    assert f"/dashboard/forms/{form.form_id}/?view=Responses|here>" in attachment["text"]
    assert attachment["fields"][0] == {"title": "Full name", "value": "Ada Example", "short": False}
    assert attachment["footer"] == "Thank you for using Bettercollected"
    h = request.headers
    assert "x-bettercollected-signature" not in h and "x-bettercollected-timestamp" not in h
    assert h["x-bettercollected-delivery"] == str(log.id)
    assert request.body == json.dumps(sent).encode()


async def test_discord_gets_its_message_unsigned(workspace, discord_server, memory_jobs):
    form = await publish(workspace)
    hook = await moved(workspace, form, formats.DISCORD, DISCORD_URL, secret=False)
    _response, _log, outcome = await deliver(workspace, form, hook, memory_jobs)
    assert outcome.status == "delivered"
    (request,) = discord_server.requests
    sent = json.loads(request.body)
    assert sent["content"].endswith("**Registration test**")
    (embed,) = sent["embeds"]
    assert embed["fields"][0] == {"name": "Full name", "value": "Ada Example", "inline": False}
    assert len(embed["fields"]) <= 25
    assert "x-bettercollected-signature" not in request.headers


async def test_a_chat_row_pointing_elsewhere_is_never_sent_to(
    workspace, legacy_server, memory_jobs
):
    form = await publish(workspace)
    # stored (by whatever means) with a host that is not Slack's
    hook = await moved(workspace, form, formats.SLACK, LEGACY_URL, secret=False)
    _response, log, outcome = await deliver(workspace, form, hook, memory_jobs)
    assert outcome.status == "failed"
    assert legacy_server.requests == []
    done = await container.action_log_repo().get(log.id)
    assert done.status is LogStatus.FAILED and done.last_error_code == "host_not_allowed"
    assert done.attempts == 1  # permanent: not retried


async def test_a_chat_name_that_resolves_inward_is_refused_at_every_send(
    workspace, slack_server, memory_jobs, monkeypatch
):
    form = await publish(workspace)
    hook = await moved(workspace, form, formats.SLACK, SLACK_URL, secret=False)

    async def inward(name, port=443):
        return ["169.254.169.254"]

    monkeypatch.setattr(client, "resolve", inward)
    _response, log, outcome = await deliver(workspace, form, hook, memory_jobs)
    assert outcome.status == "failed" and slack_server.requests == []
    assert (await container.action_log_repo().get(log.id)).last_error_code == "not_allowed"


async def test_a_slack_test_event_sends_the_questions_and_no_answers(
    workspace, slack_server, memory_jobs
):
    form = await publish(workspace)
    slack = await moved(workspace, form, formats.SLACK, SLACK_URL, secret=False)
    row = await container.webhook_service().send_test(
        workspace.id, form.form_id, slack.id, testUser
    )
    assert (await container.webhook_service().run_delivery(row.id)).status == "delivered"
    (request,) = slack_server.requests
    fields = json.loads(request.body)["attachments"][0]["fields"]
    assert fields[0]["title"] == "Full name" and fields[0]["value"] == "—"
    assert b"Ada Example" not in request.body
    assert request.headers["x-bettercollected-event"] == "test"


async def test_a_legacy_test_event_sends_the_questions_and_no_answers(
    workspace, legacy_server, memory_jobs
):
    form = await publish(workspace)
    legacy = await moved(workspace, form, formats.LEGACY_LIST, LEGACY_URL)
    row = await container.webhook_service().send_test(
        workspace.id, form.form_id, legacy.id, testUser
    )
    assert (await container.webhook_service().run_delivery(row.id)).status == "delivered"
    (request,) = legacy_server.requests
    sent = json.loads(request.body)
    assert sent[0]["title"] == "Full name" and sent[0]["answer"] is None
    assert b"Ada Example" not in request.body
    assert request.headers["x-bettercollected-event"] == "test"
    assert "x-bettercollected-signature" in request.headers


async def test_an_all_questions_envelope_sends_every_question_under_its_id(
    workspace, legacy_server, memory_jobs
):
    form = await publish(workspace)
    hook = await moved(
        workspace, form, formats.ENVELOPE, LEGACY_URL, all_questions=True
    )
    _response, _log, outcome = await deliver(workspace, form, hook, memory_jobs)
    assert outcome.status == "delivered"
    sent = json.loads(legacy_server.requests[0].body)
    # the signed envelope, with every question a webhook can send (no file, no
    # statement), keyed by the question's id
    assert list(sent) == ["event", "delivery_id", "form_id", "response_id", "submitted_at", "data"]
    assert list(sent["data"]) == [
        "name", "story", "mail", "age", "agree", "born", "colour", "colours", "people"
    ]
    assert sent["data"]["name"] == "Ada Example" and sent["data"]["age"] == 36


# ---------------------------------------------------------------- the API


async def test_the_list_shows_the_format_and_creators_cannot_choose_one(
    workspace, client: AsyncClient
):
    form = await publish(workspace)
    legacy = await moved(workspace, form, formats.LEGACY_LIST, LEGACY_URL)
    base = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/webhooks"
    listed = await client.get(base, cookies=_cookies(testUser))
    assert listed.status_code == 200, listed.text
    (row,) = [w for w in listed.json() if w["id"] == legacy.id]
    assert row["format"] == "legacy_list" and row["allQuestions"] is False
    assert "url" not in row and "secret" not in row
    # a create that asks for a format gets the signed envelope: the field is not
    # one a creator can set
    created = await client.post(
        base,
        cookies=_cookies(testUser),
        json={"url": LEGACY_URL, "fields": [{"source": "name"}], "format": "slack"},
    )
    assert created.status_code in (200, 201), created.text
    assert created.json()["format"] == "envelope"


async def test_a_creator_can_only_move_a_legacy_list_to_the_signed_format(
    workspace, client: AsyncClient
):
    form = await publish(workspace)
    legacy = await moved(workspace, form, formats.LEGACY_LIST, LEGACY_URL)
    base = f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/webhooks/{legacy.id}"
    for value in ("slack", "discord", "legacy_list", "nonsense"):
        got = await client.patch(base, cookies=_cookies(testUser), json={"format": value})
        assert got.status_code == 422, (value, got.text)
    # fields have no meaning for a format that sends every question
    got = await client.patch(
        base, cookies=_cookies(testUser), json={"fields": [{"source": "name"}]}
    )
    assert got.status_code == 422 and got.json()["code"] == "format_has_no_fields"
    got = await client.patch(base, cookies=_cookies(testUser), json={"format": "envelope"})
    assert got.status_code == 200, got.text
    assert got.json()["format"] == "envelope"
    row = await container.form_webhook_repo().get(workspace.id, form.form_id, legacy.id)
    assert row.format == "envelope" and row.secret_sealed  # still signed, same secret
    audit = await container.webhook_service().list_audit(workspace.id, form.form_id, testUser)
    assert any(a.changed == ["format"] for a in audit)


async def test_a_slack_or_discord_row_cannot_be_moved_or_pointed_elsewhere(workspace):
    form = await publish(workspace)
    slack = await moved(workspace, form, formats.SLACK, SLACK_URL, secret=False)
    service = container.webhook_service()
    for request, code in (
        (WebhookUpdateDto(format="envelope"), "format_locked"),
        (WebhookUpdateDto(url="https://evil.example.org/hooks"), "host_not_allowed"),
        (WebhookUpdateDto(url="https://hooks.slack.com.evil.example/x"), "host_not_allowed"),
        (WebhookUpdateDto(fields=[FieldDto(source="name")]), "format_has_no_fields"),
    ):
        with pytest.raises(HTTPException) as refused:
            await service.update_webhook(workspace.id, form.form_id, slack.id, request, testUser)
        assert refused.value.content["code"] == code
    with pytest.raises(HTTPException) as refused:
        await service.rotate_secret(workspace.id, form.form_id, slack.id, testUser)
    assert refused.value.content["code"] == "format_not_signed"
    # another Slack address is fine
    await service.update_webhook(
        workspace.id,
        form.form_id,
        slack.id,
        WebhookUpdateDto(url="https://hooks.slack.com/services/T1/B1/other"),
        testUser,
    )
    row = await container.form_webhook_repo().get(workspace.id, form.form_id, slack.id)
    assert unseal_url(container.crypto(), workspace.id, row.id, row.url_sealed).endswith("/T1/B1/other")
    assert row.format == "slack"


async def test_picking_questions_ends_all_questions(workspace):
    form = await publish(workspace)
    hook = await moved(workspace, form, formats.ENVELOPE, LEGACY_URL, all_questions=True)
    await container.webhook_service().update_webhook(
        workspace.id,
        form.form_id,
        hook.id,
        WebhookUpdateDto(fields=[FieldDto(source="name")]),
        testUser,
    )
    row = await container.form_webhook_repo().get(workspace.id, form.form_id, hook.id)
    assert row.all_questions is False and [f.source for f in row.fields] == ["name"]


async def test_the_privacy_panel_names_the_host_of_a_moved_webhook(workspace, client: AsyncClient):
    form = await publish(workspace)
    await moved(workspace, form, formats.SLACK, SLACK_URL, secret=False)
    destination = await container.webhook_service().destination_for(
        workspace.id, form.form_id
    )
    assert destination == {"hosts": ["hooks.slack.com"]}


async def test_the_new_fields_default_for_rows_stored_before(workspace):
    form = await publish(workspace)
    created = await make_webhook(workspace, form)
    row = await container.form_webhook_repo().get(workspace.id, form.form_id, created.id)
    assert (row.format, row.all_questions, row.created_via, row.source_action_id) == (
        "envelope",
        False,
        None,
        None,
    )
