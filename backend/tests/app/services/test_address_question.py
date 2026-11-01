"""The address question on the server: submission, a repeating group, logic on
the postcode, the one-line export cell, what the AI insights see and what the
edit operations accept. The rules of the answer are in the shared cases
(docs/spec/answer-validation.cases.json); this covers the paths around them."""

import contextlib
import json

import pytest

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.ai.insights import _answer_text
from backend.app.services.answer_validation import validate_answers
from backend.app.services.repeating_groups import (
    ADDRESS_COMPARISONS,
    comparable_answer_value,
    evaluate_condition,
)
from backend.config import settings
from tests.app.controllers.data import testUser

SECRET_STREET = "Confidential Street"
PAGES = [
    {
        "id": "p1",
        "type": "slide",
        "properties": {
            "fields": [
                {"id": "home", "type": "address", "title": "Home", "validations": {"required": True}},
                {"id": "work", "type": "address", "title": "Work", "properties": {"countries": ["NL", "BE"]}},
            ]
        },
    }
]


def _address(**kw):
    parts = {
        "street": "Keizersgracht",
        "house_number": "12",
        "house_number_addition": "A",
        "postcode": "1015 CS",
        "city": "Amsterdam",
        "country": "NL",
    }
    parts.update(kw)
    return {"type": "address", "address": {k: v for k, v in parts.items() if v is not None}}


GOOD = {"home": _address()}


def _form(pages=PAGES):
    return _parse_form_body(json.dumps({"title": "Home", "builderVersion": "v2", "fields": pages}))


@contextlib.contextmanager
def _switch(on: bool):
    before = settings.ADDRESS_QUESTION_ENABLED
    settings.ADDRESS_QUESTION_ENABLED = on
    try:
        yield
    finally:
        settings.ADDRESS_QUESTION_ENABLED = before


async def _published(workspace):
    service = container.workspace_form_service()
    with _switch(True):
        form = await service.create_form(workspace.id, _form(), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)
    return form


async def _submit(workspace, form, answers):
    return await container.workspace_form_service().submit_response(
        workspace.id, form.form_id, StandardFormResponseCamelModel(answers=answers), testUser
    )


async def test_a_valid_submission_is_stored_with_every_part_while_the_switch_is_off(client, workspace, test_user_cookies):
    form = await _published(workspace)
    assert settings.ADDRESS_QUESTION_ENABLED is False
    other = _address(country="BE", street="Rue Neuve", house_number="5", postcode="1000", city="Bruxelles", house_number_addition=None)
    response = await _submit(workspace, form, {**GOOD, "work": other})
    page = await client.get(
        f"/api/v1/workspaces/{workspace.id}/submissions/{response.response_id}", cookies=test_user_cookies
    )
    assert page.status_code == 200, page.text
    stored = page.json()["response"]["answers"]
    home = stored["home"]["address"]
    assert home == {
        "street": "Keizersgracht",
        "house_number": "12",
        "house_number_addition": "A",
        "postcode": "1015 CS",
        "city": "Amsterdam",
        "country": "NL",
    }
    # the API names the parts as they are stored
    assert stored["work"]["address"]["country"] == "BE"


async def test_problems_are_refused_with_ids_and_codes_never_the_answer(workspace):
    form = await _published(workspace)
    answers = {
        "home": _address(street=SECRET_STREET, postcode="1015cs"),
        "work": _address(country="DE"),
    }
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, form, answers)
    assert error.value.status_code == 422
    assert error.value.content["code"] == "invalid_answers"
    assert sorted((e["fieldId"], e["rule"]) for e in error.value.content["errors"]) == [
        ("home", "format"),
        ("work", "country"),
    ]
    text = json.dumps(error.value.content)
    for secret in (SECRET_STREET, "1015", "Keizersgracht"):
        assert secret not in text


async def test_a_required_address_left_out_or_half_given_is_refused(workspace):
    form = await _published(workspace)
    for home in (None, {"type": "address", "address": {"postcode": "1015 CS", "house_number": "12"}}):
        answers = {"home": home} if home else {}
        with pytest.raises(HTTPException) as error:
            await _submit(workspace, form, answers)
        assert error.value.content["errors"] == [{"fieldId": "home", "rule": "required"}]


async def test_answers_in_another_types_slot_are_the_wrong_type(workspace):
    form = await _published(workspace)
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, form, {"home": {"type": "text", "text": SECRET_STREET}})
    assert {"fieldId": "home", "rule": "type"} in error.value.content["errors"]
    assert SECRET_STREET not in json.dumps(error.value.content)


async def test_a_part_that_is_not_text_never_reaches_the_rules(workspace):
    form = await _published(workspace)
    with pytest.raises(Exception):
        await _submit(workspace, form, {"home": {"type": "address", "address": {"street": {"a": 1}}}})


def test_a_group_item_can_hold_an_address():
    form = _form(
        [
            {
                "id": "p1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": "g",
                            "type": "group",
                            "title": "People",
                            "properties": {
                                "repeat": {"minItems": 1, "maxItems": 3},
                                "fields": [{"id": "home", "type": "address", "title": "Home", "validations": {"required": True}}],
                            },
                        }
                    ]
                },
            }
        ]
    )
    good = {"g": {"type": "group", "items": [{"home": _address()}]}}
    assert validate_answers(form, good) == []
    bad = {"g": {"type": "group", "items": [{"home": _address(postcode="x")}, {}]}}
    got = sorted((p.field_id, p.rule, p.item) for p in validate_answers(form, bad))
    assert got == [("home", "format", 0), ("home", "required", 1)]


def test_a_country_alone_is_no_answer():
    form = _form()
    only_country = {"type": "address", "address": {"country": "NL"}}
    # required: it is still missing; optional: nothing was answered
    got = [(p.field_id, p.rule) for p in validate_answers(form, {"home": only_country, "work": only_country})]
    assert got == [("home", "required")]
    assert validate_answers(form, {"home": _address(), "work": only_country}) == []


def test_a_part_that_cannot_be_encoded_is_refused_not_a_server_error():
    form = _form()
    got = [(p.field_id, p.rule) for p in validate_answers(form, {"home": _address(street="\ud800")})]
    assert got == [("home", "format")]


def test_a_condition_reads_the_postcode_as_text():
    answers = {"q": _address()}
    condition = lambda comparison, value=None: {  # noqa: E731
        "field_id": "q",
        "field_type": "address",
        "comparison": comparison,
        "value": value,
    }
    assert comparable_answer_value(answers["q"], "address") == "1015 CS"
    assert evaluate_condition(answers, condition("STARTS_WITH", "10"))
    assert evaluate_condition(answers, condition("STARTS_WITH", "1015 c"))
    assert not evaluate_condition(answers, condition("STARTS_WITH", "20"))
    assert evaluate_condition(answers, condition("IS_EQUAL", "1015 CS"))
    assert evaluate_condition(answers, condition("IS_NOT_EQUAL", "1015 CT"))
    assert evaluate_condition(answers, condition("IS_NOT_EMPTY"))
    assert not evaluate_condition({}, condition("IS_NOT_EMPTY"))
    assert evaluate_condition({}, condition("IS_EMPTY"))
    # the other comparisons have no meaning for an address and never hold
    for comparison in ("CONTAINS", "GREATER_THAN", "ENDS_WITH", "DOES_NOT_CONTAIN"):
        assert not evaluate_condition(answers, condition(comparison, "10"))


def test_no_part_other_than_the_postcode_is_a_condition():
    answer = _address(postcode=None)
    assert comparable_answer_value(answer, "address") is None
    assert comparable_answer_value({"address": "x"}, "address") is None
    assert comparable_answer_value({"type": "address", "address": {"postcode": ""}}, "address") is None


def test_the_operations_and_the_logic_share_one_list_of_comparisons():
    from backend.app.services.ai.ops import ADDRESS_COMPARISONS as OPS_COMPARISONS

    assert OPS_COMPARISONS == ADDRESS_COMPARISONS


def test_the_ai_insights_never_read_an_address():
    answer = _address(street=SECRET_STREET)
    assert _answer_text(answer, {}) == "[address]"
    assert SECRET_STREET not in str(_answer_text(answer, {}))
    assert _answer_text({"type": "address", "address": {}}, {}) is None


def test_the_one_line_has_the_country_unless_it_is_nl():
    from common.address import one_line

    assert one_line(_address()["address"]) == "Keizersgracht 12 A, 1015 CS Amsterdam"
    assert one_line(_address(country="BE", house_number_addition=None)["address"]) == "Keizersgracht 12, 1015 CS Amsterdam, BE"
    assert one_line({"street": " X ", "city": "Y"}) == "X, Y"
    assert one_line({"country": "BE"}) == ""
    assert one_line(None) == "" and one_line("text") == ""


def test_a_formula_and_a_field_rule_cannot_use_an_address_but_a_rule_may_describe_it():
    from backend.app.services.calculated_fields import NOT_VARIABLES
    from backend.app.services.field_rules import NOT_RULE_TARGETS, VALUE_TYPES

    assert "address" in NOT_VARIABLES
    assert "address" not in NOT_RULE_TARGETS  # required, title and description may apply
    assert "address" not in VALUE_TYPES  # never set or locked: the form cannot invent one
