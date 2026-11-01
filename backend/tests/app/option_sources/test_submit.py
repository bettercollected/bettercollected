"""A respondent's answer to a question whose options come from a source: it must
be an option offered now (stale ones are refused with a clear code), the server
writes the label snapshot and drops any a client sent, a dependent list follows
its parent, and an edit only re-checks what it changes."""

import pytest

from backend.app.container import container
from backend.app.exceptions import HTTPException
from tests.app.controllers.data import testUser, testUser1
from tests.app.option_sources.helpers import (
    choice,
    choices,
    ids_of,
    make_list,
    publish,
    question,
    stored_answers,
    submit,
)
from tests.app.option_sources.helpers import text as text_answer

pytestmark = pytest.mark.asyncio

COUNTRIES = [{"id": "nl", "value": "Netherlands"}, {"id": "de", "value": "Germany"}]


@pytest.fixture(autouse=True)
def switched_on(sources_on):
    pass


def list_source(created, parent=None):
    source = {"kind": "list", "list_id": created.id}
    if parent:
        source["parent_field_id"] = parent
    return source


async def refused(awaitable) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        await awaitable
    return raised.value


def problems(error: HTTPException):
    assert error.status_code == 422
    assert error.content["code"] == "invalid_answers"
    return [(e["fieldId"], e["rule"]) for e in error.content["errors"]]


@pytest.fixture()
async def city_form(workspace):
    created = await make_list(workspace)
    form = await publish(
        workspace,
        [
            question("country", "dropdown", "Country", choices=COUNTRIES),
            question(
                "city", "dropdown", "City", source=list_source(created, "country")
            ),
            question(
                "cities",
                "multiple_choice",
                "Cities",
                source=list_source(created),
                allow_multiple_selection=True,
            ),
            question("note", "short_text", "Note"),
        ],
        title="Cities form",
    )
    return created, form


async def test_a_chosen_item_is_stored_with_its_label_snapshot(workspace, city_form):
    created, form = city_form
    ids = ids_of(created)
    await submit(
        workspace,
        form,
        {
            "city": choice(ids["Amsterdam"]),
            "cities": choices(ids["Berlin"], ids["Anywhere"]),
        },
    )
    [answers] = await stored_answers(workspace, form)
    assert answers["city"]["choice"] == {
        "value": ids["Amsterdam"],
        "label": "Amsterdam",
    }
    assert answers["cities"]["choices"]["values"] == [ids["Berlin"], ids["Anywhere"]]
    assert answers["cities"]["choices"]["labels"] == {
        ids["Berlin"]: "Berlin",
        ids["Anywhere"]: "Anywhere",
    }


async def test_the_snapshot_is_the_servers_whatever_a_client_sent(workspace, city_form):
    created, form = city_form
    ids = ids_of(created)
    await submit(
        workspace,
        form,
        {
            "city": choice(ids["Utrecht"], label="A forged label"),
            "cities": choices(
                ids["Berlin"],
                labels={ids["Berlin"]: "Forged", "li" + "0" * 22: "Extra"},
            ),
            "country": choice("nl", label="Forged static label"),
        },
    )
    [answers] = await stored_answers(workspace, form)
    assert answers["city"]["choice"]["label"] == "Utrecht"
    assert answers["cities"]["choices"]["labels"] == {ids["Berlin"]: "Berlin"}
    # a label slot on a question with its own options is dropped
    assert "label" not in answers["country"]["choice"]


async def test_a_stale_or_foreign_option_is_refused_with_a_clear_code(
    workspace, workspace_1, city_form
):
    created, form = city_form
    ids = ids_of(created)
    from backend.app.services.option_lists.service import ItemDto, OptionListUpdateDto

    # the item is removed after the respondent loaded the form
    await container.option_list_service().update_list(
        workspace.id,
        created.id,
        OptionListUpdateDto(
            items=[
                ItemDto(id=ids["Utrecht"], label="Utrecht"),
                ItemDto(id=ids["Anywhere"], label="Anywhere"),
            ],
            expected_revision=1,
        ),
        testUser,
    )
    error = await refused(
        submit(
            workspace,
            form,
            {"city": choice(ids["Amsterdam"]), "note": text_answer("kept?")},
        )
    )
    assert problems(error) == [("city", "option_unavailable")]
    assert await stored_answers(workspace, form) == []  # nothing stored
    # an id that never existed, and one of another workspace's list
    other = await make_list(workspace_1, name="Theirs", user=testUser1)
    for option_id in ("li" + "0" * 22, other.items[0].id, "not-an-id"):
        error = await refused(submit(workspace, form, {"cities": choices(option_id)}))
        assert problems(error) == [("cities", "option_unavailable")]
    await submit(workspace, form, {"city": choice(ids["Utrecht"])})
    assert len(await stored_answers(workspace, form)) == 1


async def test_a_dependent_list_offers_only_the_parents_items(workspace, city_form):
    created, form = city_form
    ids = ids_of(created)
    ok = await submit(
        workspace, form, {"country": choice("nl"), "city": choice(ids["Amsterdam"])}
    )
    assert ok.response_id
    # a German city with the Netherlands chosen
    error = await refused(
        submit(
            workspace, form, {"country": choice("nl"), "city": choice(ids["Berlin"])}
        )
    )
    assert problems(error) == [("city", "option_unavailable")]
    # an item without a group is offered whatever the parent says
    await submit(
        workspace, form, {"country": choice("de"), "city": choice(ids["Anywhere"])}
    )
    # no answer to the parent: nothing is filtered
    await submit(workspace, form, {"city": choice(ids["Berlin"])})
    assert len(await stored_answers(workspace, form)) == 3


async def test_a_question_the_respondent_does_not_see_is_not_refused(workspace):
    created = await make_list(workspace)
    ids = ids_of(created)
    form = await publish(
        workspace,
        [
            question(
                "gate",
                "dropdown",
                "Gate",
                choices=[{"id": "y", "value": "Yes"}, {"id": "n", "value": "No"}],
            ),
            {
                **question("city", "dropdown", "City", source=list_source(created)),
                "properties": {
                    "option_source": list_source(created),
                    "logic": {
                        "action": "SHOW",
                        "operator": "AND",
                        "conditions": [
                            {
                                "field_id": "gate",
                                "field_type": "dropdown",
                                "comparison": "IS_EQUAL",
                                "value": "Yes",
                            }
                        ],
                    },
                },
            },
        ],
    )
    # hidden by logic: a stale id there is kept as it was sent (hidden answers stay stored)
    await submit(
        workspace, form, {"gate": choice("n"), "city": choice("li" + "0" * 22)}
    )
    # shown: refused
    error = await refused(
        submit(workspace, form, {"gate": choice("y"), "city": choice("li" + "0" * 22)})
    )
    assert problems(error) == [("city", "option_unavailable")]
    await submit(workspace, form, {"gate": choice("y"), "city": choice(ids["Berlin"])})


async def test_an_edit_rechecks_only_a_changed_choice(workspace, city_form):
    created, form = city_form
    ids = ids_of(created)
    service = container.option_source_service()
    latest = await container.form_service().get_latest_version_of_form(form.form_id)
    stored = {
        "city": {
            "type": "choice",
            "choice": {"value": ids["Amsterdam"], "label": "Amsterdam"},
        }
    }
    # the item has since gone from the list
    from backend.app.services.option_lists.service import ItemDto, OptionListUpdateDto

    await container.option_list_service().update_list(
        workspace.id,
        created.id,
        OptionListUpdateDto(
            items=[ItemDto(id=ids["Berlin"], label="Berlin")], expected_revision=1
        ),
        testUser,
    )
    # the same choice sent again (with a forged label) keeps the stored label and passes
    kept = await service.apply(
        workspace.id,
        latest,
        {"city": choice(ids["Amsterdam"], label="Forged")},
        previous=stored,
        context={**stored, "note": text_answer("x")},
    )
    assert kept["city"]["choice"] == {"value": ids["Amsterdam"], "label": "Amsterdam"}
    # a changed choice must be offered now
    error = await refused(
        service.apply(
            workspace.id, latest, {"city": choice(ids["Utrecht"])}, previous=stored
        )
    )
    assert problems(error) == [("city", "option_unavailable")]
    changed = await service.apply(
        workspace.id, latest, {"city": choice(ids["Berlin"])}, previous=stored
    )
    assert changed["city"]["choice"] == {"value": ids["Berlin"], "label": "Berlin"}
    # a multiple choice: kept ids keep their labels, a new one is checked
    prior = {
        "cities": {
            "type": "choices",
            "choices": {
                "values": [ids["Amsterdam"]],
                "labels": {ids["Amsterdam"]: "Amsterdam"},
            },
        }
    }
    both = await service.apply(
        workspace.id,
        latest,
        {"cities": choices(ids["Amsterdam"], ids["Berlin"])},
        previous=prior,
    )
    assert both["cities"]["choices"]["labels"] == {
        ids["Amsterdam"]: "Amsterdam",
        ids["Berlin"]: "Berlin",
    }


async def test_the_check_can_be_set_to_log_only(workspace, city_form):
    created, form = city_form
    latest = await container.form_service().get_latest_version_of_form(form.form_id)
    answers = await container.option_source_service().apply(
        workspace.id, latest, {"city": choice("li" + "0" * 22)}, enforce=False
    )
    # not refused (RESPONSE_VALIDATION_ENFORCE off): no label either
    assert "label" not in answers["city"]["choice"]


async def test_an_answer_of_another_form_is_a_valid_choice_and_its_label_is_kept(
    workspace,
):
    registered = await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="People",
    )
    for name in ("Alice", "Bob"):
        await submit(workspace, registered, {"name": text_answer(name)})
    options = (
        await container.option_source_service().options(
            workspace.id,
            {
                "kind": "form_answers",
                "form_id": registered.form_id,
                "question_id": "name",
            },
        )
    ).options
    by_label = {o.label: o.id for o in options}
    form = await publish(
        workspace,
        [
            question(
                "who",
                "dropdown",
                "Who",
                source={
                    "kind": "form_answers",
                    "form_id": registered.form_id,
                    "question_id": "name",
                },
            )
        ],
        title="Who comes",
    )
    await submit(workspace, form, {"who": choice(by_label["Bob"])})
    [answers] = await stored_answers(workspace, form)
    assert answers["who"]["choice"] == {"value": by_label["Bob"], "label": "Bob"}
    # Bob asks for deletion: a later respondent cannot pick him, the stored answer keeps its label
    repo = container.form_response_repo()
    scope = await container.form_response_service().scope(
        workspace.id, [registered.form_id]
    )
    for row in await repo.list_by_form_id(scope):
        decrypted = container.form_response_service().decrypt_form_response(
            workspace_id=workspace.id, response=row.model_copy(deep=True)
        )
        if decrypted.answers["name"]["text"] == "Bob":
            await repo.add_deletion_request(row, row.response_id)
    error = await refused(submit(workspace, form, {"who": choice(by_label["Bob"])}))
    assert problems(error) == [("who", "option_unavailable")]
    await submit(workspace, form, {"who": choice(by_label["Alice"])})
    assert {
        a["who"]["choice"]["label"] for a in await stored_answers(workspace, form)
    } == {"Alice", "Bob"}


async def test_with_the_switch_off_a_new_choice_from_another_form_is_refused_a_list_choice_is_not(
    workspace, city_form, monkeypatch
):
    from backend.config import settings

    created, list_form = city_form
    ids = ids_of(created)
    people = await publish(
        workspace,
        [question("name", "short_text", "Name", share_as_choices=True)],
        title="People",
    )
    await submit(workspace, people, {"name": text_answer("Alice")})
    answer_source = {
        "kind": "form_answers",
        "form_id": people.form_id,
        "question_id": "name",
    }
    offered = (
        await container.option_source_service().options(workspace.id, answer_source)
    ).options
    form = await publish(
        workspace,
        [question("who", "dropdown", "Who", source=answer_source)],
        title="Who comes",
    )
    monkeypatch.setattr(settings, "OPTION_SOURCES_ENABLED", False)
    error = await refused(submit(workspace, form, {"who": choice(offered[0].id)}))
    assert problems(error) == [("who", "option_unavailable")]
    # a workspace list keeps working as before
    await submit(workspace, list_form, {"cities": choices(ids["Berlin"])})
    [answers] = await stored_answers(workspace, list_form)
    assert answers["cities"]["choices"]["labels"] == {ids["Berlin"]: "Berlin"}
