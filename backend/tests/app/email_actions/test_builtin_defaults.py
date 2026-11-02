"""An email action that replaced a built-in action: the default words in English
and Dutch, and ``all_questions`` (the action names every question the form has
now, as the built-in "send me a copy" mail did). A creator cannot turn
``all_questions`` on, and picking questions ends it."""

import json
from types import SimpleNamespace

import pytest

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.builtin_actions.links import responses_link
from backend.app.services.email_actions import defaults, templates
from backend.app.services.email_actions.service import (
    EmailActionCreateDto,
    EmailActionUpdateDto,
    TemplateDto,
)
from backend.app.services.webhooks.service import FieldDto
from tests.app.controllers.data import testUser
from tests.app.email_actions.helpers import OWNER, logs_of, make_action
from tests.app.email_actions.helpers import submit_as_owner_of_the_address as submit
from tests.app.registration.helpers import publish


LINK = responses_link("https://app.example.org", "acme", "65b0f1")


def test_the_default_words():
    en, nl = defaults.default_templates()
    assert en.subject == "You have got a new response in {{form_title}}"
    assert nl.subject == "U heeft een nieuwe reactie ontvangen op {{form_title}}"
    assert en.body == nl.body == "{{answers}}"


def test_the_default_words_with_a_link_to_the_responses():
    en, nl = defaults.default_templates(LINK)
    assert en.body == f"{{{{answers}}}}\n\nView all responses: {LINK}"
    assert nl.body == f"{{{{answers}}}}\n\nBekijk alle reacties: {LINK}"


def test_the_default_words_pass_the_checks_of_a_saved_template():
    from backend.app.services.email_actions.service import EmailActionService

    en, nl = defaults.default_templates(LINK)
    checked_en, checked_nl = EmailActionService._checked_templates(
        TemplateDto(**en.model_dump()), TemplateDto(**nl.model_dump()), []
    )
    assert (checked_en, checked_nl) == (en, nl)
    for text, built_ins in (
        (en.subject, templates.BUILT_INS_SUBJECT),
        (en.body, templates.BUILT_INS_BODY),
    ):
        assert templates.placeholder_problem(text, built_ins) is None


@pytest.fixture()
async def setup(workspace, emails_on, memory_jobs, transport):
    form = await publish(workspace)
    en, nl = defaults.default_templates(LINK)
    action = await make_action(
        workspace,
        form,
        fields=("name",),
        en=TemplateDto(**en.model_dump()),
        nl=TemplateDto(**nl.model_dump()),
    )
    repo = container.form_email_action_repo()
    row = await repo.get(workspace.id, form.form_id, action.id)
    # what the move of a built-in action leaves
    row.fields = []
    row.all_questions = True
    row.created_via = "migrated_builtin"
    row.source_action_id = "65b0000000000000000000a1"
    await repo.save(row)
    return SimpleNamespace(workspace=workspace, form=form, action=action, transport=transport)


async def rows_of(setup, response):
    return [r for r in await logs_of(setup.form) if r.response_id == response.response_id]


async def run(log):
    return await container.email_action_service().run_delivery(str(log.id))


@pytest.mark.asyncio
async def test_the_mail_names_every_question_the_form_has(setup):
    response = await submit(setup.workspace, setup.form)
    (log,) = await rows_of(setup, response)
    assert (await run(log)).status == "delivered"
    (mail,) = setup.transport.sent
    assert mail["recipients"] == [OWNER]
    assert mail["subject"] == "You have got a new response in Registration test"
    # every question a mail can carry, in form order (a file is not one), with
    # the answers: as the built-in mail listed them
    assert mail["body"].startswith(
        "Full name: Ada Example\nYour story: Synthetic story.\nEmail: ada@example.test\n"
        "Age: 36\nAgree?: Yes\nBirth date: 1990-01-02\nColour: Green\nColours: Red, Blue\n"
    )
    assert "Document" not in mail["body"] and "Read this" not in mail["body"]
    assert mail["body"].endswith(f"View all responses: {LINK}")


@pytest.mark.asyncio
async def test_a_question_added_later_is_in_the_next_mail(setup):
    # the same stored action, a form that has one more question now
    form = await container.form_repo().get_latest_version_of_form(setup.form.form_id)
    mapping = container.email_action_service()._mapping_of(form, [], True)
    assert [source for source, _key in mapping][:3] == ["name", "story", "mail"]
    extra = {"id": "extra", "type": "short_text", "title": "Extra question"}
    page = form.fields[0]
    page.properties.fields.append(type(page.properties.fields[0])(**extra))
    grown = container.email_action_service()._mapping_of(form, [], True)
    assert ("extra", "extra") in grown and len(grown) == len(mapping) + 1


@pytest.mark.asyncio
async def test_the_respondent_copy_of_such_an_action_leaves_out_hidden_calculations(
    workspace, emails_on, memory_jobs, transport
):
    form = await publish(
        workspace,
        fields=[
            {
                "id": "mail",
                "type": "email",
                "title": "Email",
                "properties": {"why_we_ask": "To reply to you"},
            },
            {"id": "qty", "type": "number", "title": "Quantity"},
            {
                "id": "risk",
                "type": "calculated",
                "title": "Risk score",
                "properties": {
                    "expression": {"*": [{"var": "qty"}, 2]},
                    "hidden_from_respondents": True,
                },
            },
        ],
    )
    en, nl = defaults.default_templates()
    action = await make_action(
        workspace,
        form,
        fields=("mail",),
        respondent="mail",
        en=TemplateDto(**en.model_dump()),
        nl=TemplateDto(**nl.model_dump()),
    )
    repo = container.form_email_action_repo()
    row = await repo.get(workspace.id, form.form_id, action.id)
    row.fields, row.all_questions = [], True
    await repo.save(row)
    answers = {
        "mail": {"type": "email", "email": "ada@example.test"},
        "qty": {"type": "number", "number": 4},
    }
    response = await submit(workspace, form, answers=answers)
    rows = [r for r in await logs_of(form) if r.response_id == response.response_id]
    assert sorted(r.channel for r in rows) == ["respondent", "team"]
    for log in rows:
        assert (await run(log)).status == "delivered"
    bodies = {tuple(m["recipients"]): m["body"] for m in transport.sent}
    team = bodies[(OWNER,)]
    copy = bodies[("ada@example.test",)]
    assert "Quantity: 4" in team and "Risk score: 8" in team  # staff see it
    assert "Quantity: 4" in copy and "Risk score" not in copy  # the respondent does not


@pytest.mark.asyncio
async def test_editing_the_words_is_checked_against_every_question(setup):
    service = container.email_action_service()
    ok = await service.update_action(
        setup.workspace.id,
        setup.form.form_id,
        setup.action.id,
        EmailActionUpdateDto(
            en=TemplateDto(subject="From {{name}}", body="{{name}} wrote {{age}}\n{{answers}}")
        ),
        testUser,
    )
    assert ok.all_questions is True
    with pytest.raises(HTTPException) as refused:
        await service.update_action(
            setup.workspace.id,
            setup.form.form_id,
            setup.action.id,
            EmailActionUpdateDto(
                en=TemplateDto(subject="From {{nobody}}", body="{{answers}}")
            ),
            testUser,
        )
    assert refused.value.content["code"] == "unknown_placeholder"
    row = await container.form_email_action_repo().get(
        setup.workspace.id, setup.form.form_id, setup.action.id
    )
    assert row.all_questions is True and row.fields == []


@pytest.mark.asyncio
async def test_picking_questions_ends_all_questions(setup):
    updated = await container.email_action_service().update_action(
        setup.workspace.id,
        setup.form.form_id,
        setup.action.id,
        EmailActionUpdateDto(fields=[FieldDto(source="name")]),
        testUser,
    )
    assert updated.all_questions is False and [f.source for f in updated.fields] == ["name"]
    row = await container.form_email_action_repo().get(
        setup.workspace.id, setup.form.form_id, setup.action.id
    )
    assert row.all_questions is False


@pytest.mark.asyncio
async def test_a_creator_cannot_turn_it_on(workspace, emails_on, memory_jobs, transport):
    form = await publish(workspace)
    en, nl = defaults.default_templates()
    created = await container.email_action_service().create_action(
        workspace.id,
        form.form_id,
        EmailActionCreateDto.model_validate(
            {
                "name": "Mine",
                "en": en.model_dump(),
                "nl": nl.model_dump(),
                "fields": [{"source": "name"}],
                "teamRecipients": [OWNER],
                "allQuestions": True,
                "createdVia": "migrated_builtin",
            }
        ),
        testUser,
    )
    assert created.all_questions is False
    row = await container.form_email_action_repo().get(workspace.id, form.form_id, created.id)
    assert (row.all_questions, row.created_via, row.source_action_id) == (False, None, None)
    updated = await container.email_action_service().update_action(
        workspace.id,
        form.form_id,
        created.id,
        EmailActionUpdateDto.model_validate({"allQuestions": True}),
        testUser,
    )
    assert updated.all_questions is False


@pytest.mark.asyncio
async def test_a_test_mail_of_such_an_action_names_every_question(setup):
    from backend.app.services.email_actions.service import TestRequestDto

    delivery = await container.email_action_service().send_test(
        setup.workspace.id, setup.form.form_id, setup.action.id, TestRequestDto(), testUser
    )
    assert delivery.status == "delivered"
    (mail,) = setup.transport.sent
    # a test mail goes to the person who asked for it, nobody else
    assert mail["recipients"] != [OWNER] and len(mail["recipients"]) == 1
    assert "Full name:" in mail["body"] and "Colours:" in mail["body"]
    assert "Ada Example" not in json.dumps(mail)  # made-up answers, never real ones
