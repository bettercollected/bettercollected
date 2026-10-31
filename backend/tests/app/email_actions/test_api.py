"""Configuration of an email action: the switch, the mail server, the templates
(unknown placeholders refused), recipients (members only), the respondent
question, limits, the test mail (to the caller only, rate limited), the
preview, the delivery log and the respondent's privacy panel."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.email_actions.service import (
    MAX_ACTIONS_PER_FORM,
    EmailActionUpdateDto,
    PreviewRequestDto,
    TestRequestDto,
)
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.controllers.test_permission_matrix import _cookies
from tests.app.email_actions.helpers import EN, NL, OWNER, logs_of, make_action
from tests.app.registration.helpers import publish, submit

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def switched_on(emails_on, transport, memory_jobs):
    pass


def service():
    return container.email_action_service()


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    return error.content["code"] if isinstance(error.content, dict) else str(error.content)


async def test_an_action_is_saved_with_normalised_members_and_checked_keys(workspace):
    form = await publish(workspace)
    created = await make_action(workspace, form, team=["  OWNER@Acme.Example ", "owner@acme.example", "editor@acme.example"])
    # as typed (trimmed); each mailbox once, compared case-folded
    assert created.team_recipients == ["OWNER@Acme.Example", "editor@acme.example"]
    assert [(f.source, f.key) for f in created.fields] == [("name", "name"), ("age", "age")]
    assert created.condition is None and created.enabled


@pytest.mark.parametrize(
    "address,code",
    [
        ("outsider@elsewhere.example", "recipient_not_allowed"),
        ("attacker@evil.example", "recipient_not_allowed"),
        ("owner+news@acme.example", "recipient_not_allowed"),
        ("owner@acme.example\r\nBcc: attacker@evil.example", "invalid_recipient"),
        ("owner@acme.example,attacker@evil.example", "invalid_recipient"),
        ("Owner <owner@acme.example>", "invalid_recipient"),
        ("not an address", "invalid_recipient"),
    ],
)
async def test_a_team_address_must_be_one_plain_member_address(workspace, address, code):
    form = await publish(workspace)
    error = await refused(make_action(workspace, form, team=[address]))
    assert code_of(error) == code and error.status_code == 422
    assert "evil.example" not in str(error.content) and "elsewhere.example" not in str(error.content)
    assert await container.form_email_action_repo().count_for_form(workspace.id, form.form_id) == 0


async def test_at_most_five_team_addresses_and_five_actions(workspace):
    form = await publish(workspace)
    error = await refused(make_action(workspace, form, team=[f"u{n}@acme.example" for n in range(6)]))
    assert code_of(error) in ("too_many_recipients", "invalid_recipient", "recipient_not_allowed")
    for _ in range(MAX_ACTIONS_PER_FORM):
        await make_action(workspace, form)
    assert code_of(await refused(make_action(workspace, form))) == "too_many_actions"


async def test_a_recipient_is_required_and_the_respondent_question_must_be_an_email_one(workspace):
    form = await publish(workspace)
    assert code_of(await refused(make_action(workspace, form, team=[]))) == "no_recipient"
    for source in ("name", "nope", "people"):
        assert code_of(await refused(make_action(workspace, form, team=[], respondent=source))) == "invalid_respondent_field"
    ok = await make_action(workspace, form, team=[], respondent="mail")
    assert ok.respondent_field == "mail" and ok.team_recipients == []


@pytest.mark.parametrize(
    "en_subject,code",
    [
        ("Hello {{unknown}}", "unknown_placeholder"),
        ("Hello {{answers}}", "unknown_placeholder"),  # not in a subject
        ("Hello {{name|upper}}", "invalid_placeholder"),
        ("Hello {{ name", "invalid_placeholder"),
    ],
)
async def test_templates_with_unknown_or_malformed_placeholders_are_refused(workspace, en_subject, code):
    form = await publish(workspace)
    error = await refused(make_action(workspace, form, en=EN.model_copy(update={"subject": en_subject})))
    assert code_of(error) == code


async def test_both_languages_are_required(workspace):
    form = await publish(workspace)
    error = await refused(make_action(workspace, form, nl=NL.model_copy(update={"body": "  \n "})))
    assert code_of(error) == "template_missing"


async def test_questions_are_checked_like_a_webhooks(workspace):
    form = await publish(workspace)
    assert code_of(await refused(make_action(workspace, form, fields=["nope"]))) == "unknown_variable"
    assert code_of(await refused(make_action(workspace, form, fields=["upload"]))) == "file_not_sent"
    assert code_of(await refused(make_action(workspace, form, fields=["intro"]))) == "variable_not_supported"
    from backend.app.services.webhooks.service import FieldDto

    assert code_of(await refused(make_action(workspace, form, fields=[FieldDto(source="name", key="answers")]))) == "invalid_key"
    assert code_of(await refused(make_action(workspace, form, fields=[FieldDto(source="name", key="a b")]))) == "invalid_key"


async def test_the_templates_are_cleaned_when_saved(workspace):
    form = await publish(workspace)
    created = await make_action(
        workspace, form, en=EN.model_copy(update={"subject": "Hi\r\nBcc: x@y.example {{name}}"})
    )
    assert "\n" not in created.en.subject and "\r" not in created.en.subject


async def test_an_update_checks_the_whole_action_again(workspace):
    form = await publish(workspace)
    created = await make_action(workspace, form)
    # unmapping a question a template names is refused
    error = await refused(service().update_action(
        workspace.id, form.form_id, created.id, EmailActionUpdateDto(fields=[]), testUser))
    assert code_of(error) == "unknown_placeholder"
    # an explicit null removes the respondent question
    withcopy = await make_action(workspace, form, respondent="mail")
    updated = await service().update_action(
        workspace.id, form.form_id, withcopy.id, EmailActionUpdateDto(respondent_field=None), testUser)
    assert updated.respondent_field is None
    # nothing changed: unchanged
    same = await service().update_action(
        workspace.id, form.form_id, created.id, EmailActionUpdateDto(name="Notify the team"), testUser)
    assert same.name == "Notify the team"


async def test_an_action_of_another_workspace_or_form_is_not_there(workspace, workspace_1):
    form = await publish(workspace)
    other = await publish(workspace_1, user=testUser1)
    foreign = await make_action(workspace_1, other, team=["outsider@elsewhere.example"], user=testUser1)
    for call in (
        service().update_action(workspace.id, form.form_id, foreign.id, EmailActionUpdateDto(enabled=False), testUser),
        service().delete_action(workspace.id, form.form_id, foreign.id, testUser),
        service().send_test(workspace.id, form.form_id, foreign.id, TestRequestDto(), testUser),
    ):
        assert (await refused(call)).status_code == 404


# ------------------------------------------------------------------ the switch


async def test_switch_off_refuses_create_enable_and_test_and_queues_nothing(workspace, monkeypatch):
    form = await publish(workspace)
    created = await make_action(workspace, form)
    monkeypatch.setattr(settings.email_actions, "ENABLED", False)
    assert code_of(await refused(make_action(workspace, form))) == "email_actions_off"
    off = await service().update_action(workspace.id, form.form_id, created.id, EmailActionUpdateDto(enabled=False), testUser)
    assert off.enabled is False
    on = await refused(service().update_action(workspace.id, form.form_id, created.id, EmailActionUpdateDto(enabled=True), testUser))
    assert code_of(on) == "email_actions_off"
    test = await refused(service().send_test(workspace.id, form.form_id, created.id, TestRequestDto(), testUser))
    assert code_of(test) == "email_actions_off"
    await submit(workspace, form)
    assert await logs_of(form) == []
    assert service().status().model_dump() == {"enabled": False, "configured": True}
    assert await service().destination_for(workspace.id, form.form_id) is None


async def test_no_mail_server_means_no_enabling(workspace, monkeypatch):
    form = await publish(workspace)
    monkeypatch.setattr(settings.mail_settings, "smtp_server", "")
    assert code_of(await refused(make_action(workspace, form))) == "mail_not_configured"
    saved_off = await make_action(workspace, form, enabled=False)
    assert saved_off.enabled is False
    assert code_of(await refused(service().update_action(
        workspace.id, form.form_id, saved_off.id, EmailActionUpdateDto(enabled=True), testUser))) == "mail_not_configured"
    assert service().status().configured is False


# --------------------------------------------------------------------- previews


async def test_the_preview_is_rendered_by_the_real_renderer_with_made_up_answers(workspace):
    form = await publish(workspace)
    from backend.app.services.webhooks.service import FieldDto

    preview = await service().preview(
        workspace.id, form.form_id,
        PreviewRequestDto(language="nl", subject="Van {{name}} ({{form_title}})", body="{{answers}}",
                          fields=[FieldDto(source="name"), FieldDto(source="age")]),
        testUser,
    )
    assert preview.subject == "Van Example text (Registration test)"
    assert preview.body == "Full name: Example text\nAge: 42"
    bad = await refused(service().preview(
        workspace.id, form.form_id, PreviewRequestDto(subject="{{x}}", body="b"), testUser))
    assert code_of(bad) == "unknown_placeholder"


# ---------------------------------------------------------------------- test mail


async def test_a_test_mail_goes_to_the_current_user_only_with_made_up_answers(workspace, transport, auth_users):
    form = await publish(workspace)
    action = await make_action(workspace, form, team=["owner@acme.example", "editor@acme.example"], respondent="mail")
    row = await service().send_test(workspace.id, form.form_id, action.id, TestRequestDto(), testUser)
    (mail,) = transport.sent
    assert mail["recipients"] == ["test@email.com"]  # the caller's own address, no team address
    assert mail["subject"].startswith("[Test] ") and "Example text" in mail["body"]
    assert row.status == "delivered" and row.event == "test" and row.channel == "team"
    copy = await service().send_test(workspace.id, form.form_id, action.id, TestRequestDto(channel="respondent"), testUser)
    assert transport.sent[1]["recipients"] == ["test@email.com"] and copy.channel == "respondent"
    # a failure is logged with our code, not the server's text
    from backend.app.services.email_actions.transport import MailFailed

    transport.fail = MailFailed("smtp_unavailable")
    failed = await service().send_test(workspace.id, form.form_id, action.id, TestRequestDto(), testUser)
    assert failed.status == "failed" and failed.last_error_code == "smtp_unavailable"
    stored = [r for r in await logs_of(form) if r.event == "test"]
    assert len(stored) == 3 and all("test@email.com" not in r.model_dump_json() for r in stored)


async def test_a_test_mail_for_a_copy_needs_a_copy(workspace):
    form = await publish(workspace)
    action = await make_action(workspace, form)
    error = await refused(service().send_test(workspace.id, form.form_id, action.id, TestRequestDto(channel="respondent"), testUser))
    assert code_of(error) == "no_copy"


async def test_test_mails_are_rate_limited_per_action(workspace, transport):
    form = await publish(workspace)
    action = await make_action(workspace, form)
    for _ in range(5):
        await service().send_test(workspace.id, form.form_id, action.id, TestRequestDto(), testUser)
    error = await refused(service().send_test(workspace.id, form.form_id, action.id, TestRequestDto(), testUser))
    assert error.status_code == 429 and code_of(error) == "rate_limited"
    assert "Retry-After" in error.headers and len(transport.sent) == 5


# ------------------------------------------------------------------ privacy panel


async def test_the_privacy_panel_says_who_gets_mail_and_nothing_when_off_or_disabled(workspace):
    form = await publish(workspace)
    assert await service().destination_for(workspace.id, form.form_id) is None
    team = await make_action(workspace, form)
    assert await service().destination_for(workspace.id, form.form_id) == {"team": True, "copy": False}
    copy = await make_action(workspace, form, team=[], respondent="mail")
    assert await service().destination_for(workspace.id, form.form_id) == {"team": True, "copy": True}
    for action in (team, copy):
        await service().update_action(workspace.id, form.form_id, action.id, EmailActionUpdateDto(enabled=False), testUser)
    assert await service().destination_for(workspace.id, form.form_id) is None


async def test_the_published_form_carries_the_destination_for_respondents(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    ws, fid = workspace.id, form.form_id
    plain = await client.get(f"/api/v1/workspaces/{ws}/forms/{fid}?published=true")
    assert plain.status_code == 200 and not plain.json().get("emailDestination")
    await make_action(workspace, form, respondent="mail")
    published = await client.get(f"/api/v1/workspaces/{ws}/forms/{fid}?published=true")
    assert published.status_code == 200, published.text
    assert published.json()["emailDestination"] == {"team": True, "copy": True}
    monkeypatch.setattr(settings.email_actions, "ENABLED", False)
    again = await client.get(f"/api/v1/workspaces/{ws}/forms/{fid}?published=true")
    assert not again.json().get("emailDestination")


async def test_the_form_is_not_served_when_the_destination_cannot_be_read(client: AsyncClient, workspace, monkeypatch):
    form = await publish(workspace)
    await make_action(workspace, form)

    async def broken(*args, **kwargs):
        raise RuntimeError("database down")

    monkeypatch.setattr(container.email_action_service(), "destination_for", broken)
    response = await client.get(f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}?published=true")
    assert response.status_code == 503 and response.json()["code"] == "form_unavailable"


# ------------------------------------------------------------------- the log


async def test_the_delivery_log_lists_only_email_rows(workspace, transport):
    form = await publish(workspace)
    action = await make_action(workspace, form, respondent="mail")
    await submit(workspace, form)
    page = await service().list_deliveries(workspace.id, form.form_id, testUser)
    assert page.total == 2 and {d.channel for d in page.items} == {"team", "respondent"}
    assert {d.action_id for d in page.items} == {action.id}
    dumped = page.model_dump_json()
    for text in ("acme.example", "Ada Example", "ada@example.test"):
        assert text not in dumped
    waiting = await service().list_deliveries(workspace.id, form.form_id, testUser, statuses=["pending"])
    assert waiting.total == 2
    assert (await service().list_deliveries(workspace.id, form.form_id, testUser, statuses=["nonsense"])).total == 0
    # webhooks list their own rows only
    from backend.app.schemas.webhook import ActionType

    assert await container.action_log_repo().count_for_form(workspace.id, form.form_id, None, ActionType.WEBHOOK) == 0
