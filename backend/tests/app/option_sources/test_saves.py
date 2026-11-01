"""The switch and the checks on every way a form is written: the builder's create
and update, the spec check, the last gate (``persist_form``, used by chat, MCP and
imports), templates, copies and provider imports. Stored sources keep working."""

import copy

import pytest
from common.ids import RecordId
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.template import StandardFormTemplate
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_writes import persist_form
from backend.app.services.option_sources import read
from backend.app.services.option_sources.checks import strip_option_sources
from backend.config import settings
from tests.app.controllers.data import testUser, testUser1
from tests.app.option_sources.helpers import make_list, publish, question, submit

pytestmark = pytest.mark.asyncio


def slide(*questions):
    return [
        {
            "id": "s1",
            "type": "slide",
            "index": 0,
            "properties": {"fields": list(questions)},
        }
    ]


def new_form(*questions, title="Saves"):
    return StandardForm(builder_version="v2", title=title, fields=slide(*questions))


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def code_of(error: HTTPException) -> str:
    return (
        error.content["code"] if isinstance(error.content, dict) else str(error.content)
    )


def list_q(created, field_id="city", **extra):
    return question(field_id, source={"kind": "list", "list_id": created.id}, **extra)


@pytest.fixture()
async def city_list(workspace, monkeypatch):
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", True)
    return await make_list(workspace)


# -------------------------------------------------------------- the switch


async def test_the_switch_is_off_by_default_and_a_new_source_is_refused(
    workspace, city_list, monkeypatch
):
    from backend.config.application import Application

    assert Application.model_fields["OPTION_SOURCES_ENABLED"].default is False
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    service = container.workspace_form_service()
    error = await refused(
        service.create_form(workspace.id, new_form(list_q(city_list)), testUser)
    )
    assert error.status_code == 422 and code_of(error) == "option_sources_disabled"
    assert error.content["errors"] == [{"fieldId": "city"}]
    # a form without a source is fine
    await service.create_form(
        workspace.id, new_form(question("plain", "short_text")), testUser
    )


async def test_a_stored_source_keeps_saving_and_a_changed_one_is_refused(
    workspace, city_list, monkeypatch
):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id, new_form(list_q(city_list), title="One"), testUser
    )
    other = await make_list(workspace, name="Other")
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    stored = await container.form_service().get_form_document_by_id(form.form_id)
    # a new title, a moved question, another question: the source is as stored
    edited = StandardForm(**stored.model_dump())
    edited.title = "Renamed"
    edited.fields[0].properties.fields.append(
        StandardForm(**new_form(question("n", "short_text")).model_dump())
        .fields[0]
        .properties.fields[0]
    )
    await service.update_form(workspace.id, form.form_id, edited, testUser)
    # ... but pointing it at another list is a change
    changed = StandardForm(
        **(
            await container.form_service().get_form_document_by_id(form.form_id)
        ).model_dump()
    )
    changed.fields[0].properties.fields[0].properties.option_source.list_id = other.id
    error = await refused(
        service.update_form(workspace.id, form.form_id, changed, testUser)
    )
    assert code_of(error) == "option_sources_disabled"
    # taking the source away asks nothing of the switch
    cleared = StandardForm(
        **(
            await container.form_service().get_form_document_by_id(form.form_id)
        ).model_dump()
    )
    cleared.fields[0].properties.fields[0].properties.option_source = None
    await service.update_form(workspace.id, form.form_id, cleared, testUser)


async def test_a_response_to_a_stored_source_is_still_checked_while_the_switch_is_off(
    workspace, city_list, monkeypatch
):
    form = await publish(workspace, [list_q(city_list)], title="Published")
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    first = city_list.items[0].id
    await submit(
        workspace, form, {"city": {"type": "choice", "choice": {"value": first}}}
    )
    error = await refused(
        submit(
            workspace,
            form,
            {"city": {"type": "choice", "choice": {"value": "li" + "0" * 22}}},
        )
    )
    assert error.content["errors"] == [
        {"fieldId": "city", "rule": "option_unavailable"}
    ]


# ------------------------------------------------------------ the shape on save


@pytest.mark.parametrize(
    "build",
    [
        lambda c: question("a", "short_text", source={"kind": "list", "list_id": c.id}),
        lambda c: question(
            "a",
            source={"kind": "list", "list_id": c.id},
            choices=[{"id": "x", "value": "X"}],
        ),
        lambda c: question("a", source={"kind": "list"}),
        lambda c: question(
            "a", source={"kind": "list", "list_id": c.id, "parent_field_id": "missing"}
        ),
        lambda c: {
            "id": "g",
            "type": "group",
            "title": "g",
            "properties": {"fields": [list_q(c, "in")]},
        },
    ],
)
async def test_a_malformed_source_is_refused_on_save(workspace, city_list, build):
    service = container.workspace_form_service()
    error = await refused(
        service.create_form(workspace.id, new_form(build(city_list)), testUser)
    )
    assert error.status_code == 422 and code_of(error) == "option_source_invalid"
    assert error.content["errors"]


async def test_the_source_must_exist_in_this_workspace_and_be_readable_by_the_saver(
    workspace, workspace_1, city_list
):
    service = container.workspace_form_service()
    theirs = await make_list(workspace_1, name="Theirs", user=testUser1)
    error = await refused(
        service.create_form(workspace.id, new_form(list_q(theirs)), testUser)
    )
    assert code_of(error) == "option_source_invalid"
    # another form's answers: the saver needs response.read on it (every role that edits forms has it; the
    # privacy officer, who has not, edits none, and a key never does: see test_sources)
    people = await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="People",
    )
    source = {"kind": "form_answers", "form_id": people.form_id, "question_id": "name"}
    created = await service.create_form(
        workspace.id, new_form(question("who", source=source)), testUser
    )
    assert created.form_id
    # a form cannot take its options from its own answers
    own = await service.create_form(
        workspace.id, new_form(question("name", "short_text", "Name")), testUser
    )
    update = StandardForm(
        **(
            await container.form_service().get_form_document_by_id(own.form_id)
        ).model_dump()
    )
    update.fields[0].properties.fields.append(
        StandardForm(
            **new_form(
                question(
                    "who",
                    source={
                        "kind": "form_answers",
                        "form_id": own.form_id,
                        "question_id": "name",
                    },
                )
            ).model_dump()
        )
        .fields[0]
        .properties.fields[0]
    )
    error = await refused(
        service.update_form(workspace.id, own.form_id, update, testUser)
    )
    assert (
        code_of(error) == "option_source_invalid"
        and "own answers" in error.content["message"]
    )


async def test_a_condition_on_a_sourced_question_can_only_test_whether_it_is_answered(
    workspace, city_list
):
    def condition(comparison):
        return question(
            "next",
            "short_text",
            "Next",
            logic={
                "action": "SHOW",
                "operator": "AND",
                "conditions": [
                    {
                        "field_id": "city",
                        "field_type": "dropdown",
                        "comparison": comparison,
                        "value": "x",
                    }
                ],
            },
        )

    service = container.workspace_form_service()
    await service.create_form(
        workspace.id, new_form(list_q(city_list), condition("IS_NOT_EMPTY")), testUser
    )
    error = await refused(
        service.create_form(
            workspace.id, new_form(list_q(city_list), condition("IS_EQUAL")), testUser
        )
    )
    assert (
        code_of(error) == "option_source_invalid"
        and "answered" in error.content["message"]
    )


# --------------------------------------------------------- persist_form (the last gate)


class Repo:
    def __init__(self, stored):
        self.stored, self.saved = stored, []

    async def get_form_document_by_id(self, form_id):
        return self.stored

    async def save_form(self, document):
        self.saved.append(document)


async def test_persist_form_takes_a_list_source_with_the_switch_but_never_another_forms_answers(
    workspace, city_list, monkeypatch
):
    stored = new_form(question("plain", "short_text"))
    stored.form_id = "f"
    repo = Repo(stored)
    with_list = new_form(list_q(city_list))
    assert await persist_form(repo, stored, with_list, parts=["fields"])
    from_answers = new_form(
        question(
            "who",
            source={
                "kind": "form_answers",
                "form_id": str(RecordId()),
                "question_id": "n",
            },
        )
    )
    error = await refused(
        persist_form(Repo(stored), stored, from_answers, parts=["fields"])
    )
    assert code_of(error) == "option_source_forbidden"
    # stored as it is, a form-answers source passes
    again = Repo(from_answers)
    from_answers.form_id = "f"
    assert await persist_form(
        again, from_answers, copy.deepcopy(from_answers), parts=["fields"]
    )
    # an op that gave a sourced question options of its own is refused
    broken = copy.deepcopy(with_list)
    broken.fields[0].properties.fields[0].properties.choices = [
        {"id": "c", "value": "C"}
    ]
    error = await refused(
        persist_form(Repo(with_list), with_list, broken, parts=["fields"])
    )
    assert code_of(error) == "option_source_invalid"
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    fresh = new_form(question("plain", "short_text"))
    fresh.form_id = "f"
    error = await refused(
        persist_form(Repo(fresh), fresh, copy.deepcopy(with_list), parts=["fields"])
    )
    assert code_of(error) == "option_sources_disabled"


# --------------------------------------------------------------- the spec check


def spec_document(*fields):
    return {
        "specVersion": "1",
        "title": "S",
        "pages": [{"id": "p1", "fields": list(fields)}],
    }


async def test_the_spec_check_reports_a_broken_source_and_warns_while_the_switch_is_off(
    city_list, monkeypatch
):
    good = spec_document(
        {
            "id": "c",
            "type": "dropdown",
            "title": "C",
            "optionSource": {"kind": "list", "listId": city_list.id},
        }
    )
    result = check_spec_document(good)
    assert result["valid"] is True and not any(
        "optionSource" in w["path"] for w in result["warnings"]
    )
    bad = spec_document(
        {
            "id": "c",
            "type": "short_text",
            "title": "C",
            "optionSource": {"kind": "list", "listId": city_list.id},
        }
    )
    result = check_spec_document(bad)
    assert result["valid"] is False and any(
        "optionSource" in e["path"] for e in result["errors"]
    )
    both = spec_document(
        {
            "id": "c",
            "type": "dropdown",
            "title": "C",
            "choices": [{"id": "a", "value": "A"}],
            "optionSource": {"kind": "list", "listId": city_list.id},
        }
    )
    assert check_spec_document(both)["valid"] is False
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    result = check_spec_document(good)
    assert result["valid"] is True
    assert any(
        w["path"].endswith("/optionSource") and "OPTION_SOURCES_ENABLED" in w["message"]
        for w in result["warnings"]
    )


# ------------------------------------------------- copies, templates, imports


async def test_templates_never_keep_a_source_and_a_copy_loses_what_belongs_to_the_original(
    workspace, city_list
):
    templates = container.form_template_service()
    body = StandardFormTemplate(title="T", fields=new_form(list_q(city_list)).fields)
    created = await templates.create_new_template(
        workspace.id, None, None, testUser, body
    )
    assert not list(read.sourced_questions(created))
    # a form copied from a template (an older one that has a source) loses it
    service = container.workspace_form_service()
    with_source = new_form(list_q(city_list))
    copy_of = await service.create_form(
        workspace.id, with_source, testUser, drop_unusable_settings=True
    )
    assert not list(
        read.sourced_questions(
            await container.form_service().get_form_document_by_id(copy_of.form_id)
        )
    )


async def test_a_duplicate_keeps_a_list_source_and_loses_another_forms_answers(
    workspace, city_list
):
    people = await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="People",
    )
    form = await container.workspace_form_service().create_form(
        workspace.id,
        new_form(
            list_q(city_list),
            question(
                "who",
                source={
                    "kind": "form_answers",
                    "form_id": people.form_id,
                    "question_id": "name",
                },
            ),
        ),
        testUser,
    )
    copy_form = await container.workspace_form_service().duplicate_form(
        workspace.id, form.form_id, testUser
    )
    kept = {
        str(read.get(q, "id")): s["kind"]
        for q, s in read.sourced_questions(
            await container.form_service().get_form_document_by_id(copy_form.form_id)
        )
    }
    assert kept == {"city": "list"}
    original = {
        str(read.get(q, "id"))
        for q, _ in read.sourced_questions(
            await container.form_service().get_form_document_by_id(form.form_id)
        )
    }
    assert original == {"city", "who"}


def _shares(document):
    return [
        read.get(read.props(f), "share_as_choices") is True
        for f, _ in read.every_field(document)
    ]


async def test_a_copy_never_inherits_the_decision_to_share_answers(
    workspace, monkeypatch
):
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", True)
    original = await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="Original",
    )
    forms = container.form_service()
    service = container.workspace_form_service()
    assert _shares(await forms.get_form_document_by_id(original.form_id)) == [True]
    # a duplicate
    copy_form = await service.duplicate_form(workspace.id, original.form_id, testUser)
    assert _shares(await forms.get_form_document_by_id(copy_form.form_id)) == [False]
    # a template made from the form, and a form made from a template body
    template = await service.duplicate_form(
        workspace.id, original.form_id, testUser, is_template=True
    )
    assert _shares(template) == [False]
    created = await service.create_form(
        workspace.id,
        new_form(question("name", "short_text", "Name", share_as_choices=True)),
        testUser,
        drop_unusable_settings=True,
    )
    assert _shares(await forms.get_form_document_by_id(created.form_id)) == [False]
    # a form written by its creator, not copied, keeps what they chose
    own = await service.create_form(
        workspace.id,
        new_form(question("name", "short_text", "Name", share_as_choices=True)),
        testUser,
    )
    assert _shares(await forms.get_form_document_by_id(own.form_id)) == [True]


async def test_a_provider_import_carries_no_stamp_and_no_sharing(workspace):
    await container.form_import_service().save_converted_form_and_responses(
        {
            "form": {
                "form_id": "imported-form-stamp",
                "title": "Imported",
                "settings": {"provider": "google"},
                "fields": slide(
                    question("name", "short_text", "Name", share_as_choices=True)
                ),
            },
            "responses": [
                {
                    "response_id": "imported-response-stamp",
                    "provider": "google",
                    "answers": {},
                    "shared_as_choices": ["name"],
                }
            ],
        },
        "",
        workspace.id,
    )
    stored = await container.form_response_repo().get_response(
        "imported-response-stamp"
    )
    assert stored.shared_as_choices is None
    document = await container.form_service().get_form_document_by_id(
        "imported-form-stamp"
    )
    assert _shares(document) == [False]


async def test_a_provider_import_never_carries_a_source():
    form = new_form(list_q(type("L", (), {"id": "x" * 24})()))
    assert strip_option_sources(form) == 1 and not list(read.sourced_questions(form))


async def test_persist_form_checks_that_a_list_belongs_to_the_callers_workspace(
    workspace, workspace_1, city_list
):
    theirs = await make_list(workspace_1, name="Theirs", user=testUser1)
    stored = new_form(question("plain", "short_text"))
    stored.form_id = "f"
    service = container.option_source_service()

    async def check(new, old):
        await service.ensure_lists_belong(workspace.id, new, old)

    await persist_form(
        Repo(stored),
        stored,
        new_form(list_q(city_list)),
        parts=["fields"],
        lists_check=check,
    )
    fresh = new_form(question("plain", "short_text"))
    fresh.form_id = "f"
    error = await refused(
        persist_form(
            Repo(fresh),
            fresh,
            new_form(list_q(theirs)),
            parts=["fields"],
            lists_check=check,
        )
    )
    assert code_of(error) == "option_source_invalid"
