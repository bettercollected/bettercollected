"""Choice-level logic (services/option_logic.py): the model, the save checks
and repair, the caps, the edit's reach, the spec and the edit operations, and
the submit, edit and builder-save paths. The evaluation itself has its shared
cases in docs/spec/option-logic.cases.json (test_option_logic_cases.py)."""

import json

import pytest
from common.form_spec import form_to_spec_dict, spec_to_form
from common.models.standard_form import (
    FORM_OPTION_CONDITIONS_MAX,
    OPTION_CONDITIONS_MAX,
    StandardChoice,
    StandardForm,
    raw_option_logic_problem,
)
from pydantic import ValidationError

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.minified_form import FormDtoCamelModel
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_writes import persist_form
from backend.app.services.option_logic import (
    ensure_valid_option_logic,
    form_has_option_logic,
    option_keys_affected,
    option_logic_problems,
    option_logic_warnings,
    option_states,
    prune_option_logic,
)
from tests.app.controllers.data import testUser


@pytest.fixture(autouse=True)
def choice_logic_on(monkeypatch):
    """These tests are about what choice logic does; the switch that refuses
    new choice logic has its own tests (test_choice_logic_switch.py)."""
    from backend.config import settings

    monkeypatch.setattr(settings, "CHOICE_LOGIC_ENABLED", True)


COUNTRIES = [
    {"id": "nl", "value": "Netherlands"},
    {"id": "de", "value": "Germany"},
    {"id": "be", "value": "Belgium"},
]
CITIES = [
    {"id": "ams", "value": "Amsterdam"},
    {"id": "ber", "value": "Berlin"},
    {"id": "bru", "value": "Brussels"},
]
FILTER = {
    "fieldId": "country",
    "mapping": [
        {"when": "nl", "show": ["ams"]},
        {"when": "de", "show": ["ber"]},
        {"when": "be", "show": ["bru"]},
    ],
}


def _field(field_id, field_type="dropdown", choices=None, **properties):
    field = {"id": field_id, "type": field_type, "title": field_id.title()}
    if choices is not None:
        properties["choices"] = choices
    if properties:
        field["properties"] = properties
    return field


def _country():
    return _field("country", choices=COUNTRIES)


def _city(**properties):
    properties.setdefault("optionFilter", FILTER)
    properties.setdefault("choices", CITIES)
    return _field("city", **properties)


def _body(*pages):
    fields = [
        {"id": f"p{i}", "type": "slide", "properties": {"fields": page}}
        for i, page in enumerate(pages)
    ]
    return {"title": "Options", "builderVersion": "v2", "fields": fields}


def _form(*pages):
    return _parse_form_body(json.dumps(_body(*pages)))


def _unchecked_form(*pages):
    """A form as the model reads it, without the builder body's count of
    option conditions (which refuses a payload this large first)."""
    return StandardForm(**FormDtoCamelModel(**_body(*pages)).model_dump(mode="json"))


def _is(field_id, value, field_type="dropdown"):
    return {
        "fieldId": field_id,
        "fieldType": field_type,
        "comparison": "IS_EQUAL",
        "value": value,
    }


def _show(*conditions, action="SHOW"):
    return {"action": action, "conditions": list(conditions)}


def _choice(answer):
    return {"type": "choice", "choice": {"value": answer}}


def _messages(form):
    return [p.message for p in option_logic_problems(form)]


# --- model and spec ------------------------------------------------------------


def test_the_model_reads_option_logic_and_a_filter_in_both_spellings():
    choice = StandardChoice.model_validate(
        {"id": "a", "logic": _show(_is("country", "x"))}
    )
    assert choice.logic.conditions[0].field_id == "country"
    form = _form([_country(), _city()])
    assert form.fields[0].properties.fields[1].properties.option_filter.field_id == (
        "country"
    )
    # a bare filter in snake_case reads too (stored forms)
    stored = StandardForm.model_validate(form.model_dump(mode="json"))
    assert stored.fields[0].properties.fields[1].properties.option_filter.mapping[
        0
    ].show == ["ams"]


def test_an_option_has_at_most_so_many_conditions():
    many = _show(*[_is("country", str(i)) for i in range(OPTION_CONDITIONS_MAX + 1)])
    with pytest.raises(ValidationError):
        StandardChoice.model_validate({"id": "a", "logic": many})


def test_the_spec_round_trips_option_logic_and_the_filter():
    form = _form(
        [
            _country(),
            _city(
                choices=[
                    {
                        "id": "ams",
                        "value": "Amsterdam",
                        "logic": _show(_is("country", "Netherlands")),
                    },
                    *CITIES[1:],
                ]
            ),
        ]
    )
    document = form_to_spec_dict(form)
    city = document["pages"][0]["fields"][1]
    assert city["optionFilter"]["fieldId"] == "country"
    assert city["choices"][0]["logic"]["action"] == "SHOW"
    back = spec_to_form(
        __import__("common.form_spec", fromlist=["FormSpec"]).FormSpec.model_validate(
            document
        )
    )
    again = back.fields[0].properties.fields[1].properties
    assert again.option_filter.mapping[2].show == ["bru"]
    assert again.choices[0].logic.conditions[0].value == "Netherlands"


def test_the_spec_check_reports_problems_with_a_path():
    form = _form([_country(), _city()])
    document = form_to_spec_dict(form)
    document["pages"][0]["fields"][1]["optionFilter"]["mapping"][0]["when"] = "nope"
    result = check_spec_document(document)
    assert not result["valid"]
    assert result["errors"][0]["path"] == "/pages/0/fields/1/optionFilter"
    assert "nope" in result["errors"][0]["message"]
    # an option's own logic
    document = form_to_spec_dict(form)
    document["pages"][0]["fields"][1]["choices"][0]["logic"] = {
        "action": "SHOW",
        "conditions": [{"fieldId": "city", "comparison": "IS_EQUAL", "value": "x"}],
    }
    result = check_spec_document(document)
    assert [e["path"] for e in result["errors"]] == [
        "/pages/0/fields/1/choices/0/logic"
    ]


def test_the_spec_check_warns_about_options_that_can_never_be_offered():
    form = _form(
        [
            _country(),
            _city(
                optionFilter={
                    "fieldId": "country",
                    "mapping": [{"when": "nl", "show": ["ams"]}],
                }
            ),
        ]
    )
    result = check_spec_document(form_to_spec_dict(form))
    assert result["valid"]
    messages = [w["message"] for w in result["warnings"]]
    assert any("'Berlin' is never offered" in m for m in messages)
    assert any("Choosing 'Germany'" in m for m in messages)


# --- save checks ----------------------------------------------------------------


def test_a_valid_form_has_no_problems():
    form = _form([_country(), _city()])
    assert form_has_option_logic(form)
    assert option_logic_problems(form) == []


def test_a_form_without_option_logic_costs_nothing():
    form = _form([_country()])
    assert not form_has_option_logic(form)
    assert ensure_valid_option_logic(form) == []
    assert option_states(form, {}).hidden == {}


@pytest.mark.parametrize(
    "fields, expected",
    [
        # a filter that reads a later question
        (
            [_city(), _country()],
            "can only read an earlier question",
        ),
        # a filter that reads itself
        (
            [
                _field(
                    "city",
                    choices=CITIES,
                    optionFilter={
                        "fieldId": "city",
                        "mapping": [{"when": "ams", "show": ["ber"]}],
                    },
                )
            ],
            "cannot read its own question",
        ),
        # an unknown question
        (
            [
                _city(
                    optionFilter={
                        "fieldId": "gone",
                        "mapping": [{"when": "a", "show": ["b"]}],
                    }
                )
            ],
            "not a question of this form",
        ),
        # an entry that names an unknown option of the earlier question
        (
            [
                _country(),
                _city(
                    optionFilter={
                        "fieldId": "country",
                        "mapping": [{"when": "xx", "show": ["ams"]}],
                    }
                ),
            ],
            "'xx' is not an option of 'Country'",
        ),
        # ... or of this one
        (
            [
                _country(),
                _city(
                    optionFilter={
                        "fieldId": "country",
                        "mapping": [{"when": "nl", "show": ["xx"]}],
                    }
                ),
            ],
            "an entry names an option that 'City' does not have",
        ),
        # a filter on a text question
        (
            [
                _field("name", "short_text"),
                _city(
                    optionFilter={
                        "fieldId": "name",
                        "mapping": [{"when": "a", "show": ["ams"]}],
                    }
                ),
            ],
            "not a single or multiple choice",
        ),
        # option logic on a question that has no choices
        (
            [
                _field(
                    "name",
                    "short_text",
                    choices=[{"id": "a", "value": "A", "logic": _show(_is("x", "y"))}],
                )
            ],
            "cannot have logic",
        ),
    ],
)
def test_problems_the_save_refuses(fields, expected):
    form = _form(fields)
    assert any(expected in message for message in _messages(form)), _messages(form)


@pytest.mark.parametrize(
    "condition, expected",
    [
        (_is("city", "x"), "its own question"),
        (_is("gone", "x"), "not a question of this form"),
        (_is("later", "x"), "can only depend on an earlier question"),
        (_is("note", "x", "short_text"), "internal field"),
        (
            {
                "fieldId": "country",
                "comparison": "IS_EQUAL",
                "value": "x",
                "groupMode": "ANY",
            },
            "groupMode only applies",
        ),
    ],
)
def test_option_conditions_are_checked_like_logic_and_must_read_earlier_questions(
    condition, expected
):
    note = _field("note", "short_text")
    note["internal"] = True
    form = _form(
        [
            _country(),
            note,
            _field(
                "city",
                choices=[
                    {"id": "ams", "value": "Amsterdam", "logic": _show(condition)},
                    CITIES[1],
                ],
            ),
            _field("later", "short_text"),
        ]
    )
    assert any(expected in m for m in _messages(form)), _messages(form)


def test_option_logic_is_for_page_level_choice_questions_only():
    group = _field(
        "g",
        "group",
        fields=[_field("inner", choices=CITIES, optionFilter=FILTER)],
        repeat={"minItems": 1, "maxItems": 2},
    )
    form = _form([_country(), group])
    assert any("repeating group" in m for m in _messages(form))


def test_too_many_options_for_option_logic():
    many = [{"id": f"o{i}", "value": str(i)} for i in range(201)]
    form = _form(
        [
            _country(),
            _field(
                "city",
                choices=many,
                optionFilter={
                    "fieldId": "country",
                    "mapping": [{"when": "nl", "show": ["o1"]}],
                },
            ),
        ]
    )
    assert any("more than 200 options" in m for m in _messages(form))


def test_the_form_caps_count_conditions_and_filters():
    # 51 questions each with a filter
    sources = [_country()]
    filtered = [
        _field(
            f"c{i}",
            choices=CITIES,
            optionFilter={
                "fieldId": "country",
                "mapping": [{"when": "nl", "show": ["ams"]}],
            },
        )
        for i in range(51)
    ]
    form = _unchecked_form(sources + filtered)
    assert any("at most 50 option filters" in m for m in _messages(form))
    with pytest.raises(HTTPException) as error:
        ensure_valid_option_logic(form, drop=True)  # caps refuse even in repair mode
    assert error.value.status_code == 422
    assert error.value.content["code"] == "invalid_option_logic"


def test_raw_counts_refuse_a_payload_before_it_is_parsed():
    fields = [
        {
            "properties": {
                "choices": [
                    {"id": f"o{i}", "logic": {"conditions": [{}] * 20}}
                    for i in range(FORM_OPTION_CONDITIONS_MAX // 20 + 1)
                ]
            }
        }
    ]
    assert "at most 1000 option conditions" in raw_option_logic_problem(fields)
    assert raw_option_logic_problem([{"properties": {"choices": []}}]) is None
    with pytest.raises(HTTPException):
        _parse_form_body(
            json.dumps({"title": "x", "builderVersion": "v2", "fields": fields})
        )


# --- repair ---------------------------------------------------------------------


def test_the_repair_drops_what_is_broken_and_keeps_the_rest():
    form = _form(
        [
            _country(),
            _field(
                "city",
                choices=[
                    {
                        "id": "ams",
                        "value": "Amsterdam",
                        "logic": _show(_is("country", "Netherlands"), _is("gone", "x")),
                    },
                    {"id": "ber", "value": "Berlin", "logic": _show(_is("gone", "x"))},
                    CITIES[2],
                ],
                optionFilter={
                    "fieldId": "country",
                    "mapping": [
                        {"when": "nl", "show": ["ams", "nowhere"]},
                        {"when": "ghost", "show": ["ber"]},
                    ],
                },
            ),
        ]
    )
    assert prune_option_logic(form) >= 4
    city = form.fields[0].properties.fields[1].properties
    assert [c.value for c in city.choices[0].logic.conditions] == ["Netherlands"]
    assert city.choices[1].logic is None
    assert [(e.when, e.show) for e in city.option_filter.mapping] == [("nl", ["ams"])]
    assert option_logic_problems(form) == []
    # nothing left to repair
    assert prune_option_logic(form) == 0


def test_a_filter_whose_source_is_gone_is_dropped_whole():
    form = _form([_city()])
    assert prune_option_logic(form) == 1
    assert form.fields[0].properties.fields[0].properties.option_filter is None


def test_a_builder_style_save_repairs_instead_of_refusing():
    form = _form([_city(), _country()])  # the source moved after the question
    repaired = ensure_valid_option_logic(form, drop=True)
    assert [r["fieldId"] for r in repaired] == ["city"]
    assert "earlier question" in repaired[0]["message"]
    assert form.fields[0].properties.fields[0].properties.option_filter is None
    # the spec path is strict
    strict = _form([_city(), _country()])
    with pytest.raises(HTTPException) as error:
        ensure_valid_option_logic(strict)
    assert error.value.content["errors"][0]["fieldId"] == "city"


# --- states, the edit's reach, warnings ------------------------------------------


def test_states_hold_minimum_choices_and_none_left():
    form = _form([_country(), _city()])
    answers = StandardFormResponseCamelModel(answers={"country": _choice("nl")}).answers
    states = option_states(form, answers)
    assert states.hidden_options("city") == frozenset({"ber", "bru"})
    assert states.min_choices(form.fields[0].properties.fields[1], 3) == 1
    assert not states.is_none_left("city")


def test_the_replay_reads_no_more_than_the_caps_allow():
    # 20 conditions on each of 60 options is beyond the form cap: the options
    # past it are offered (such a form cannot be saved)
    conditions = [_is("country", "Netherlands") for _ in range(20)]
    choices = [
        {"id": f"o{i}", "value": str(i), "logic": _show(*conditions)} for i in range(60)
    ]
    form = _unchecked_form([_country(), _field("pick", choices=choices)])
    states = option_states(
        form, StandardFormResponseCamelModel(answers={"country": _choice("de")}).answers
    )
    assert len(states.hidden_options("pick")) == FORM_OPTION_CONDITIONS_MAX // 20


def test_duplicated_selections_do_not_cost_more():
    form = _form([_country(), _city()])
    answers = {
        "country": {"type": "choices", "choices": {"values": ["nl"] * 5000}},
        "city": {"type": "choices", "choices": {"values": ["ams"] * 5000}},
    }
    states = option_states(form, answers)
    assert states.hidden_options("city") == frozenset({"ber", "bru"})


def test_an_edit_reaches_questions_that_read_what_changed_through_others():
    street = _field(
        "street",
        choices=[
            {"id": "s1", "value": "Damrak"},
            {"id": "s2", "value": "Dam", "logic": _show(_is("city", "Amsterdam"))},
        ],
    )
    form = _form([_country(), _city(), street])
    assert option_keys_affected(form, ["country"]) == {"city", "street"}
    assert option_keys_affected(form, ["city"]) == {"street"}
    assert option_keys_affected(form, ["street"]) == set()
    assert option_keys_affected(_form([_country()]), ["country"]) == set()


def test_warnings_name_the_options_and_questions():
    form = _form(
        [
            _country(),
            _city(
                optionFilter={
                    "fieldId": "country",
                    "mapping": [
                        {"when": "nl", "show": ["ams"]},
                        {"when": "de", "show": ["ber"]},
                    ],
                },
            ),
        ]
    )
    found = {(w.code, w.option_id) for w in option_logic_warnings(form)}
    assert found == {("unreachable_option", "bru"), ("source_option_unmapped", "be")}


# --- the edit operations --------------------------------------------------------


def _apply(form, ops, atomic=False):
    return apply_form_ops(form, parse_ops(ops), atomic=atomic)


def _plain_form():
    return _form([_country(), _field("city", choices=CITIES), _field("age", "number")])


def test_set_option_logic_names_the_option_by_label_and_checks_it():
    form, results = _apply(
        _plain_form(),
        [
            {
                "op": "set_option_logic",
                "fieldId": "city",
                "choice": "Amsterdam",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {
                            "fieldId": "country",
                            "comparison": "IS_EQUAL",
                            "value": "Netherlands",
                        }
                    ],
                },
            }
        ],
    )
    assert results[0].ok, results[0].message
    logic = form.fields[0].properties.fields[1].properties.choices[0].logic
    assert logic.action == "SHOW"
    assert logic.conditions[0].field_type == "dropdown"
    # clearing it
    form, results = _apply(
        form,
        [{"op": "set_option_logic", "fieldId": "city", "choice": "ams", "logic": None}],
    )
    assert results[0].ok
    assert form.fields[0].properties.fields[1].properties.choices[0].logic is None


@pytest.mark.parametrize(
    "op, expected",
    [
        (
            {
                "op": "set_option_logic",
                "fieldId": "city",
                "choice": "Nowhere",
                "logic": None,
            },
            "is not an option of 'City'",
        ),
        (
            {"op": "set_option_logic", "fieldId": "age", "choice": "x", "logic": None},
            "not a single or multiple choice",
        ),
        (
            {
                "op": "set_option_logic",
                "fieldId": "country",
                "choice": "Germany",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {"fieldId": "city", "comparison": "IS_EQUAL", "value": "Berlin"}
                    ],
                },
            },
            "can only depend on an earlier question",
        ),
        (
            {
                "op": "set_option_logic",
                "fieldId": "city",
                "choice": "Berlin",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {"fieldId": "city", "comparison": "IS_EQUAL", "value": "Berlin"}
                    ],
                },
            },
            "own question",
        ),
        (
            {
                "op": "set_option_logic",
                "fieldId": "city",
                "choice": "Berlin",
                "logic": {
                    "action": "SHOW",
                    "conditions": [
                        {
                            "fieldId": "country",
                            "comparison": "IS_EQUAL",
                            "value": "Mars",
                        }
                    ],
                },
            },
            "is not a choice of 'Country'",
        ),
    ],
)
def test_set_option_logic_refuses(op, expected):
    form, results = _apply(_plain_form(), [op])
    assert not results[0].ok
    assert expected in results[0].message, results[0].message
    assert not form_has_option_logic(form)


def test_set_option_filter_resolves_labels_and_ids_to_ids():
    form, results = _apply(
        _plain_form(),
        [
            {
                "op": "set_option_filter",
                "fieldId": "city",
                "filter": {
                    "fieldId": "country",
                    "mapping": [
                        {"when": "Netherlands", "show": ["Amsterdam"]},
                        {"when": "de", "show": ["Berlin", "ber"]},
                    ],
                },
            }
        ],
    )
    assert results[0].ok, results[0].message
    flt = form.fields[0].properties.fields[1].properties.option_filter
    assert flt.field_id == "country"
    assert [(e.when, e.show) for e in flt.mapping] == [("nl", ["ams"]), ("de", ["ber"])]


def test_set_option_filter_refuses_a_later_or_text_source():
    _, results = _apply(
        _plain_form(),
        [
            {
                "op": "set_option_filter",
                "fieldId": "country",
                "filter": {
                    "fieldId": "city",
                    "mapping": [{"when": "Berlin", "show": ["Germany"]}],
                },
            },
            {
                "op": "set_option_filter",
                "fieldId": "city",
                "filter": {
                    "fieldId": "age",
                    "mapping": [{"when": "x", "show": ["Berlin"]}],
                },
            },
        ],
    )
    assert "earlier question" in results[0].message
    assert "not a single or multiple choice" in results[1].message


def test_removing_a_question_or_an_option_drops_what_read_it_and_says_so():
    base = _form([_country(), _city()])
    form, results = _apply(base, [{"op": "remove_field", "fieldId": "country"}])
    assert results[0].ok
    assert "option logic piece(s)" in results[0].message
    assert form.fields[0].properties.fields[0].properties.option_filter is None
    form, results = _apply(
        base,
        [
            {
                "op": "update_field",
                "fieldId": "country",
                "patch": {"choices": ["Netherlands", "Belgium"]},
            }
        ],
    )
    assert results[0].ok
    mapping = form.fields[0].properties.fields[1].properties.option_filter.mapping
    assert [e.when for e in mapping] == ["nl", "be"]


def test_moving_a_question_away_from_its_source_is_refused():
    base = _form([_country(), _city()])
    form, results = _apply(
        base, [{"op": "move_field", "fieldId": "country", "index": 1}]
    )
    assert not results[0].ok
    assert "would break option logic" in results[0].message
    assert [f.id for f in form.fields[0].properties.fields] == ["country", "city"]
    # moving whole pages likewise
    pages = _form([_country()], [_city()])
    form, results = _apply(pages, [{"op": "move_page", "pageId": "p0", "index": 1}])
    assert not results[0].ok
    assert [p.id for p in form.fields] == ["p0", "p1"]


def test_a_source_of_option_logic_cannot_become_internal():
    _, results = _apply(
        _form([_country(), _city()]),
        [{"op": "update_field", "fieldId": "country", "patch": {"internal": True}}],
    )
    assert not results[0].ok
    assert "conditional logic" in results[0].message


def test_duplicating_a_page_does_not_copy_option_logic():
    form = _form(
        [
            _country(),
            _city(
                choices=[
                    {
                        "id": "ams",
                        "value": "Amsterdam",
                        "logic": _show(_is("country", "Netherlands")),
                    },
                    *CITIES[1:],
                ]
            ),
        ]
    )
    form, results = _apply(form, [{"op": "duplicate_page", "pageId": "p0"}])
    assert results[0].ok
    clone = form.fields[1].properties.fields
    assert clone[1].properties.option_filter is None
    assert all(c.logic is None for c in clone[1].properties.choices)
    # the original keeps its own
    original = form.fields[0].properties.fields[1].properties
    assert original.option_filter is not None and original.choices[0].logic is not None
    assert option_logic_problems(form) == []


def test_an_editor_op_cannot_bring_broken_option_logic():
    base = _form([_country()])
    bad = {
        "id": "city",
        "type": "dropdown",
        "title": "City",
        "properties": {
            "choices": [{"id": "a", "value": "A"}, {"id": "b", "value": "B"}],
            "optionFilter": {
                "fieldId": "gone",
                "mapping": [{"when": "x", "show": ["a"]}],
            },
        },
    }
    _, results = apply_form_ops(
        base,
        parse_ops(
            [{"op": "insert_field", "pageId": "p0", "index": 1, "field": bad}],
            allow_editor_ops=True,
        ),
    )
    assert not results[0].ok
    assert "option filter" in results[0].message


def test_too_many_option_conditions_in_one_payload_are_refused_before_parsing():
    conditions = [{"fieldId": "country", "comparison": "IS_EQUAL", "value": "x"}] * 20
    ops = [
        {
            "op": "set_option_logic",
            "fieldId": "city",
            "choice": f"c{i}",
            "logic": {"action": "SHOW", "conditions": conditions},
        }
        for i in range(FORM_OPTION_CONDITIONS_MAX // 20 + 1)
    ]
    with pytest.raises(ValueError):
        parse_ops(ops)


# --- write paths -----------------------------------------------------------------


async def _published(workspace, *pages):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form(*pages), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)
    return form


async def test_the_server_refuses_a_submission_that_selects_an_unavailable_option(
    workspace,
):
    form = await _published(workspace, [_country(), _city()])
    service = container.workspace_form_service()
    with pytest.raises(HTTPException) as error:
        await service.submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(
                answers={"country": _choice("nl"), "city": _choice("ber")}
            ),
            testUser,
        )
    assert error.value.status_code == 422
    assert error.value.content["code"] == "invalid_answers"
    assert error.value.content["errors"] == [
        {"fieldId": "city", "rule": "hidden_option"}
    ]
    # no value in the error
    assert "ber" not in json.dumps(error.value.content)
    response = await service.submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={"country": _choice("nl"), "city": _choice("ams")}
        ),
        testUser,
    )
    assert response.response_id


async def test_field_rules_values_are_not_filtered(workspace):
    # a rule sets the city to Berlin whatever the country: the form's value
    # stands, as the question is locked
    locked = _city(
        rules=[
            {
                "id": "r1",
                "when": {"expression": True},
                "then": {"setValue": {"const": "ber"}},
            }
        ]
    )
    form = _form([_country(), locked])
    from backend.app.services.field_rules import resolve_field_rules

    answers, states = resolve_field_rules(
        form, StandardFormResponseCamelModel(answers={"country": _choice("nl")}).answers
    )
    assert "city" in states.locked
    assert option_states(form, answers, locked=states.locked).hidden == {}


async def test_a_respondent_edit_reports_a_selection_an_earlier_edit_strands(
    workspace,
):
    service = container.workspace_form_service()
    form = await _published(workspace, [_country(), _city()])
    repo = container.workspace_form_repo()
    workspace_form = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form.form_id)
    )
    workspace_form.settings.require_verified_identity = True
    workspace_form.settings.allow_editing_response = True
    await repo.save(workspace_form)
    submitted = await service.submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={"country": _choice("nl"), "city": _choice("ams")}
        ),
        testUser,
    )

    async def edit(answers):
        await service.patch_response(
            workspace.id,
            form.form_id,
            submitted.response_id,
            None,
            StandardFormResponseCamelModel(answers=answers),
            testUser,
        )

    # the edit changes the country only: the stored city is now unavailable
    with pytest.raises(HTTPException) as error:
        await edit({"country": _choice("de")})
    assert error.value.content["errors"] == [
        {"fieldId": "city", "rule": "hidden_option"}
    ]
    # sending the question again with an available option goes through
    await edit({"country": _choice("de"), "city": _choice("ber")})


async def test_a_builder_save_repairs_broken_option_logic_without_refusing(workspace):
    service = container.workspace_form_service()
    form = await service.create_form(
        workspace.id, _form([_country(), _city()]), testUser
    )
    # the source question is removed: the filter goes, the save does not fail
    await service.update_form(workspace.id, form.form_id, _form([_city()]), testUser)
    saved = await container.form_service().get_form_document_by_id(str(form.form_id))
    assert saved.fields[0].properties.fields[0].properties.option_filter is None
    # the builder sends the same thing again and the save still goes through
    await service.update_form(workspace.id, form.form_id, _form([_city()]), testUser)


async def test_persist_form_is_the_last_gate_and_repairs_what_a_writer_left(workspace):
    service = container.workspace_form_service()
    created = await service.create_form(
        workspace.id, _form([_country(), _city()]), testUser
    )
    repo = container.form_repo()
    document = await repo.get_form_document_by_id(str(created.form_id))
    # a writer that dropped the source question but kept the filter
    broken = _form([_city()])
    await persist_form(repo, document, broken, parts=["fields"])
    saved = await repo.get_form_document_by_id(str(created.form_id))
    assert saved.fields[0].properties.fields[0].properties.option_filter is None


def test_a_crafted_answer_is_read_as_the_options_it_selects():
    # the same option five thousand times, and one it does not have: read once / not at all
    form = _form(
        [
            _country(),
            _field(
                "city",
                choices=[
                    {
                        "id": "ams",
                        "value": "Amsterdam",
                        "logic": _show(_is("country", "Netherlands")),
                    },
                    {
                        "id": "ber",
                        "value": "Berlin",
                        "logic": _show(_is("country", "Germany")),
                    },
                ],
            ),
        ]
    )
    answers = {
        "country": {"type": "choices", "choices": {"values": ["nl"] * 5000 + ["ghost"]}}
    }
    states = option_states(form, answers)
    assert states.hidden_options("city") == frozenset({"ber"})


def _heavy_form(options=1000, conditions=30):
    """A source with many options read by many conditions: over the budget
    when every option is chosen (not a form a save accepts)."""
    countries = [{"id": f"c{i}", "value": f"Country {i}"} for i in range(options)]
    pick = [
        {
            "id": f"o{i}",
            "value": f"Option {i}",
            "logic": _show(*[_is("country", "Country 0", "multiple_choice")] * 20),
        }
        for i in range(conditions)
    ]
    return (
        _unchecked_form(
            [
                _field(
                    "country",
                    "multiple_choice",
                    choices=countries,
                    allowMultipleSelection=True,
                ),
                _field("pick", choices=pick),
            ]
        ),
        countries,
    )


def test_option_logic_over_its_budget_is_refused_not_half_checked():
    from backend.app.services.option_logic import OptionLogicTooCostly

    form, countries = _heavy_form()
    everything = {
        "country": {
            "type": "choices",
            "choices": {"values": [c["id"] for c in countries]},
        }
    }
    with pytest.raises(OptionLogicTooCostly):
        option_states(form, everything)
    # one chosen option costs next to nothing
    one = {"country": {"type": "choices", "choices": {"values": ["c0"]}}}
    assert option_states(form, one).hidden == {}


def test_a_form_whose_worst_case_is_over_the_budget_cannot_be_saved():
    form, _ = _heavy_form()
    assert any("too costly to check" in m for m in _messages(form))
    with pytest.raises(HTTPException) as error:
        ensure_valid_option_logic(form, drop=True)
    assert error.value.content["code"] == "invalid_option_logic"
    # a form within the caps is not held up
    fine, _ = _heavy_form(options=200, conditions=5)
    assert not any("too costly" in m for m in _messages(fine))


def test_honest_responses_to_a_form_a_save_accepts_never_meet_the_budget():
    # 4 options x 20 group conditions (every response on this form used to be
    # refused), COUNT conditions cost 1, and the real work is charged
    group = _field(
        "g",
        "group",
        fields=[_field("inner", choices=CITIES)],
        repeat={"minItems": 0, "maxItems": 50},
    )
    pick = [
        {
            "id": f"o{i}",
            "value": f"Option {i}",
            "logic": _show(
                *[
                    {
                        "fieldId": "g",
                        "fieldType": "group",
                        "comparison": "IS_EQUAL",
                        "value": "Berlin",
                        "groupMode": "ANY",
                        "childFieldId": "inner",
                        "childFieldType": "dropdown",
                    }
                ]
                * 20
            ),
        }
        for i in range(4)
    ]
    form = _form([group, _field("pick", choices=pick)])
    assert option_logic_problems(form) == []
    items = [{"inner": {"type": "choice", "choice": {"value": "ber"}}}] * 50
    states = option_states(form, {"g": {"type": "group", "items": items}})
    assert states.hidden == {}
    count = [
        {
            "id": f"c{i}",
            "value": f"Count {i}",
            "logic": _show(
                *[
                    {
                        "fieldId": "g",
                        "fieldType": "group",
                        "comparison": "GREATER_THAN_EQUAL",
                        "value": 1,
                        "groupMode": "COUNT",
                    }
                ]
                * 20
            ),
        }
        for i in range(40)
    ]
    form = _form([group, _field("pick", choices=count)])
    assert option_logic_problems(form) == []
    option_states(form, {"g": {"type": "group", "items": items}})


def test_a_source_with_many_chosen_options_costs_what_is_chosen():
    countries = [{"id": f"c{i}", "value": f"Country {i}"} for i in range(250)]
    pick = [
        {
            "id": f"o{i}",
            "value": f"Option {i}",
            "logic": _show(_is("country", "Country 1", "multiple_choice")),
        }
        for i in range(40)
    ]
    form = _form(
        [
            _field(
                "country",
                "multiple_choice",
                choices=countries,
                allowMultipleSelection=True,
            ),
            _field("pick", choices=pick),
        ]
    )
    assert option_logic_problems(form) == []
    everything = {
        "country": {
            "type": "choices",
            "choices": {"values": [c["id"] for c in countries]},
        }
    }
    assert option_states(form, everything).hidden == {}


def test_the_server_answers_422_when_the_option_logic_is_too_costly():
    from backend.app.services.answer_validation import check_answers

    form, countries = _heavy_form()
    with pytest.raises(HTTPException) as error:
        check_answers(
            form,
            StandardFormResponseCamelModel(
                answers={
                    "country": {
                        "type": "choices",
                        "choices": {"values": [c["id"] for c in countries]},
                    }
                }
            ).answers,
            "form-1",
            enforce=True,
        )
    assert error.value.status_code == 422
    assert error.value.content["code"] == "option_logic_too_costly"


def test_a_repair_counts_each_dropped_piece_once():
    # two conditions, one broken: 1; both broken: 2 (the logic that goes with
    # the last of them is not counted again)
    def logic_with(*conditions):
        return _form(
            [
                _country(),
                _field(
                    "city",
                    choices=[
                        {
                            "id": "ams",
                            "value": "Amsterdam",
                            "logic": _show(*conditions),
                        },
                        CITIES[1],
                    ],
                ),
            ]
        )

    assert prune_option_logic(logic_with(_is("country", "x"), _is("gone", "x"))) == 1
    assert prune_option_logic(logic_with(_is("gone", "x"), _is("gone2", "x"))) == 2
    form = logic_with(_is("gone", "x"), _is("gone2", "x"))
    assert len(ensure_valid_option_logic(form, drop=True)) == 2


def test_a_question_with_too_many_options_is_refused_not_wiped():
    many = [{"id": f"o{i}", "value": str(i)} for i in range(201)]
    many[0]["logic"] = _show(_is("country", "Netherlands"))
    form = _form([_country(), _field("city", choices=many)])
    with pytest.raises(HTTPException) as error:
        ensure_valid_option_logic(form, drop=True)
    assert error.value.status_code == 422
    assert "more than 200 options" in error.value.content["message"]
    # nothing was wiped
    assert form.fields[0].properties.fields[1].properties.choices[0].logic is not None
    assert {w.code for w in option_logic_warnings(form)} == {"too_many_options"}


def test_a_group_condition_is_charged_for_merging_each_item_over_the_answers():
    from backend.app.services.option_logic import _Reading, option_states

    group = _field(
        "g",
        "group",
        fields=[_field("inner", choices=CITIES)],
        repeat={"minItems": 0, "maxItems": 50},
    )
    pick = [
        {
            "id": "o1",
            "value": "One",
            "logic": _show(
                {
                    "fieldId": "g",
                    "fieldType": "group",
                    "comparison": "IS_EQUAL",
                    "value": "Berlin",
                    "groupMode": "ANY",
                    "childFieldId": "inner",
                    "childFieldType": "dropdown",
                }
            ),
        },
        CITIES[1],
    ]
    form = _form([group, _country(), _field("pick", choices=pick)])
    from backend.app.services.repeating_groups import logic_sources

    sources = logic_sources(form.fields)
    items = [{"inner": {"type": "choice", "choice": {"value": "ber"}}}] * 10
    answers = {
        "g": {"type": "group", "items": items},
        "country": {"type": "choice", "choice": {"value": "nl"}},
        "junk1": {"type": "text", "text": "x"},
    }
    reading = _Reading(answers, sources)
    condition = form.fields[0].properties.fields[2].properties.choices[0].logic.conditions[0]
    # known keys only (the group and the country), never the crafted ones
    assert reading.known == 2
    assert reading.cost([condition]) >= 1 + 10 * (1 + 2)
    assert option_states(form, answers).hidden == {}


def test_an_option_condition_reads_no_text_over_ten_thousand_characters():
    form = _form(
        [
            _field("n", "short_text"),
            _field(
                "pick",
                choices=[
                    {
                        "id": "a",
                        "value": "A",
                        "logic": _show(
                            {
                                "fieldId": "n",
                                "fieldType": "short_text",
                                "comparison": "IS_NOT_EMPTY",
                            }
                        ),
                    },
                    CITIES[1],
                ],
            ),
        ]
    )
    long = {"n": {"type": "text", "text": "a" * 10_001}}
    assert option_states(form, long).hidden_options("pick") == frozenset({"a"})
    assert (
        option_states(form, {"n": {"type": "text", "text": "a" * 10_000}}).hidden == {}
    )
