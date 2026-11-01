"""The address question in a webhook, a registration body and an email action:
it can be mapped, a delivery carries the six parts in the shape the public API
answers them in, an unanswered address (or a country alone) is ``null``, a part
that is not clean text never leaves, the test event carries a made-up address,
an email reads it as one line and a condition asks about its postcode.
Everything here is synthetic."""

import json

import pytest
from common.models.standard_form import FieldLogicCondition, StandardForm

from backend.app.exceptions import HTTPException
from backend.app.schemas.webhook import ActionCondition
from backend.app.services import action_conditions
from backend.app.services.email_actions import templates
from backend.app.services.registration import body
from backend.app.services.webhooks import payload

PARTS = ("street", "house_number", "house_number_addition", "postcode", "city", "country")
HOME = {"id": "home", "type": "address", "title": "Home"}
ABROAD = {
    "id": "abroad",
    "type": "address",
    "title": "Abroad",
    "properties": {"countries": ["NL", "BE"]},
}
ONLY_BE = {"id": "be", "type": "address", "title": "Belgium", "properties": {"countries": ["BE"]}}
FULL = {
    "street": "Keizersgracht",
    "house_number": "12",
    "house_number_addition": "A",
    "postcode": "1015 CS",
    "city": "Amsterdam",
    "country": "NL",
}


def form_of(*fields):
    return StandardForm(
        builder_version="v2",
        title="t",
        fields=[{"id": "s1", "type": "slide", "properties": {"fields": list(fields or [HOME])}}],
    )


def answer(address):
    return {"type": "address", "address": address}


def data_of(answers, sources=("home",), form=None):
    return payload.build_data(form or form_of(), [(s, s) for s in sources], answers, None)


def test_an_address_question_is_mappable():
    variable = body.variables_of(form_of())["home"]
    assert variable.supported and variable.reason is None
    assert [v.source for v in body.mappable(form_of())] == ["home"]


def test_it_is_sent_as_its_six_parts():
    assert data_of({"home": answer(FULL)}) == {"home": FULL}
    assert json.dumps(data_of({"home": answer(FULL)}))


def test_unanswered_or_a_country_alone_is_null():
    assert data_of({}) == {"home": None}
    assert data_of({"home": answer({})}) == {"home": None}
    assert data_of({"home": answer({"country": "NL"})}) == {"home": None}
    assert data_of({"home": answer({"street": "", "country": "NL"})}) == {"home": None}


def test_a_part_left_out_is_null_and_the_one_allowed_country_is_filled_in():
    sent = data_of({"home": answer({"postcode": "1015 CS", "house_number": "12"})})["home"]
    assert sent == {
        "street": None,
        "house_number": "12",
        "house_number_addition": None,
        "postcode": "1015 CS",
        "city": None,
        "country": "NL",
    }
    belgian = data_of({"be": answer({"street": "Rue Neuve", "city": "Bruxelles"})}, ["be"], form_of(ONLY_BE))
    assert belgian["be"]["country"] == "BE"
    # several countries allowed and none given: no guess
    several = data_of({"abroad": answer({"street": "Rue Neuve"})}, ["abroad"], form_of(ABROAD))
    assert several["abroad"]["country"] is None


@pytest.mark.parametrize(
    "part, value",
    [
        ("street", " padded"),
        ("street", "a‮b"),
        ("city", "x" * 101),
        ("house_number", "1\n2"),
        ("postcode", 1015),
        ("country", "nl"),
        ("country", "XX"),
        ("country", "https://evil.example"),
    ],
)
def test_a_part_that_is_not_clean_text_never_leaves(part, value):
    sent = data_of({"home": answer({**FULL, part: value})})["home"]
    if part == "country":
        # the question allows the Netherlands alone: that is what it is
        assert sent["country"] == "NL"
    else:
        assert sent[part] is None
    assert {k: v for k, v in sent.items() if k != part} == {k: v for k, v in FULL.items() if k != part}


def test_a_stored_value_of_another_shape_is_null():
    for odd in ("Keizersgracht 12", ["Keizersgracht"], 12, None):
        assert data_of({"home": answer(odd)}) == {"home": None}
    # unknown keys are never sent
    sent = data_of({"home": answer({**FULL, "extra": "x"})})["home"]
    assert set(sent) == set(PARTS)


def test_what_goes_out_always_validates_against_its_own_schema():
    jsonschema = pytest.importorskip("jsonschema")
    form = form_of(HOME, ABROAD)
    index = body.variables_of(form)
    mapping = [("home", "home"), ("abroad", "abroad")]
    for answers in (
        {"home": answer(FULL), "abroad": answer({**FULL, "country": "BE"})},
        {},
        {"home": answer({"street": "a\x00b", "postcode": "1"}), "abroad": answer({"country": "XX"})},
        {"home": answer({"postcode": "1015 CS"})},
    ):
        values, schema = body.build_values(index, mapping, answers, None, [], None)
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(values)
    _values, schema = body.build_values(index, mapping, {"home": answer(FULL)}, None, [], None)
    home = schema["properties"]["home"]
    assert home["type"] == "object" and home["required"] == list(PARTS)
    assert home["additionalProperties"] is False
    assert home["properties"]["country"] == {"type": "string", "pattern": body.COUNTRY_CODE_PATTERN}
    assert home["properties"]["street"]["maxLength"] == 100


def test_a_repeating_group_carries_an_address_per_item():
    group = {
        "id": "homes",
        "type": "group",
        "title": "Homes",
        "properties": {
            "repeat": {"minItems": 0, "maxItems": 3, "itemLabel": "Home"},
            "fields": [{"id": "where", "type": "address", "title": "Where"}],
        },
    }
    answers = {
        "homes": {
            "type": "group",
            "items": [{"where": answer(FULL)}, {}],
        }
    }
    form = form_of(group)
    values, schema = body.build_values(body.variables_of(form), [("homes", "homes")], answers, None, [], None)
    assert values["homes"] == [{"where": FULL}, {"where": None}]
    item = schema["properties"]["homes"]["items"]["properties"]
    assert item["where"]["type"] == ["object", "null"]
    # an email reads each item's address as one line
    assert templates.format_value(values["homes"]).startswith("1. Keizersgracht 12 A, 1015 CS Amsterdam\n")


def test_the_sample_is_an_address_of_the_same_shape():
    sample = payload.sample_data(form_of(), [("home", "home")])["home"]
    assert set(sample) == set(PARTS) and sample["country"] == "NL"
    sample["street"] = "changed"
    assert payload.sample_data(form_of(), [("home", "home")])["home"]["street"] == "Example street"


def test_an_email_reads_an_address_as_one_line():
    assert templates.format_value(FULL) == "Keizersgracht 12 A, 1015 CS Amsterdam"
    assert templates.format_value({**FULL, "country": "BE"}) == "Keizersgracht 12 A, 1015 CS Amsterdam, BE"
    sent = data_of({"home": answer({"postcode": "1015 CS", "house_number": "12"})})["home"]
    assert templates.format_value(sent) == "12, 1015 CS"
    entries = [("home", "Home", FULL)]
    assert "Keizersgracht 12 A, 1015 CS Amsterdam" in templates.answers_block(entries, "en")


# -------------------------------------------------------------- conditions


def c(field, comparison, value=None):
    return FieldLogicCondition(field_id=field, comparison=comparison, value=value)


def checked(*items):
    return action_conditions.checked_condition(
        form_of(), ActionCondition(operator="AND", conditions=list(items))
    )


@pytest.mark.parametrize("comparison", ["IS_EQUAL", "IS_NOT_EQUAL", "STARTS_WITH", "IS_EMPTY", "IS_NOT_EMPTY"])
def test_a_condition_on_an_address_keeps_each_postcode_comparison(comparison):
    kept = checked(c("home", comparison, "10"))
    assert kept.conditions[0].comparison == comparison and kept.conditions[0].field_type == "address"


@pytest.mark.parametrize("comparison", ["CONTAINS", "GREATER_THAN", "ENDS_WITH", "DOES_NOT_CONTAIN"])
def test_a_condition_on_an_address_refuses_a_comparison_that_never_fires(comparison):
    with pytest.raises(HTTPException) as raised:
        checked(c("home", comparison, "10"))
    assert raised.value.status_code == 422 and raised.value.content["code"] == "invalid_condition"


def test_a_condition_reads_the_postcode():
    form = form_of()

    def holds(comparison, value, answers):
        # a condition is stored as the save checked it (with the question's type)
        condition = action_conditions.checked_condition(
            form, ActionCondition(operator="AND", conditions=[c("home", comparison, value)])
        )
        return action_conditions.conditions_hold(condition, form, answers)

    answered = {"home": answer(FULL)}
    assert holds("STARTS_WITH", "10", answered) == (True, None)
    assert holds("STARTS_WITH", "20", answered) == (False, action_conditions.NOT_MET)
    assert holds("IS_EQUAL", "1015 CS", answered) == (True, None)
    assert holds("IS_EMPTY", None, {}) == (True, None)
    assert holds("IS_NOT_EMPTY", None, answered) == (True, None)
