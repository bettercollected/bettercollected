"""Field rules: the model, the server's replay (required, read-only, set
values, precedence, calculated fields, repeating groups, unknown
references), the save checks, the submit and edit paths, the form spec and
the edit operations. The shared cases are in
docs/spec/answer-validation.cases.json (checks ``fieldRules``)."""

import pytest
from common.form_spec import FormSpec, form_to_spec_dict, spec_to_form
from common.models.standard_form import (
    FIELD_RULES_MAX,
    FieldRule,
    StandardForm,
    StandardFormField,
)
from pydantic import ValidationError

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.ai.ops import apply_form_ops, finished_form, parse_ops
from backend.app.services.answer_validation import validate_answers
from backend.app.services.field_rules import (
    ensure_valid_field_rules,
    field_rule_problems,
    resolve_field_rules,
    rule_keys_reading,
    server_value_ids,
)
from backend.app.services.form_spec.checks import check_spec_document
from tests.app.controllers.data import testUser

V = lambda key: {"var": key}  # noqa: E731


def _q(field_id, field_type="short_text", required=None, rules=None, **properties):
    field = {"id": field_id, "type": field_type, "title": field_id.title()}
    if required is not None:
        field["validations"] = {"required": required}
    if rules is not None:
        properties["rules"] = rules
    if properties:
        field["properties"] = properties
    return field


def _rule(rule_id, then, conditions=None, expression=None, operator=None):
    when = {}
    if operator:
        when["operator"] = operator
    if conditions is not None:
        when["conditions"] = conditions
    if expression is not None:
        when["expression"] = expression
    return {"id": rule_id, "when": when, "then": then}


def _is(field_id, value, field_type="short_text", comparison="IS_EQUAL"):
    return {
        "fieldId": field_id,
        "fieldType": field_type,
        "comparison": comparison,
        "value": value,
    }


def _form(*pages, hidden_fields=None):
    return StandardForm.model_validate(
        {
            "builder_version": "v2",
            "title": "Rules",
            "hidden_fields": hidden_fields,
            "fields": [
                {
                    "id": f"p{i}",
                    "type": "slide",
                    "index": i,
                    "properties": {"fields": f},
                }
                for i, f in enumerate(pages)
            ],
        }
    )


def _text(value):
    return {"type": "text", "text": value}


def _num(value):
    return {"type": "number", "number": value}


def _yes(value=True):
    return {"type": "boolean", "boolean": value}


def _answers(answers):
    return StandardFormResponseCamelModel(answers=answers).answers


def _errors(form, answers):
    resolved, states = resolve_field_rules(form, _answers(answers))
    return sorted(
        (p.field_id, p.rule, p.item)
        for p in validate_answers(form, resolved, rule_states=states)
    )


def _plain(answers):
    return {
        k: v.model_dump(exclude_none=True) if hasattr(v, "model_dump") else v
        for k, v in answers.items()
    }


COUNTRY = {
    "id": "country",
    "type": "dropdown",
    "title": "Country",
    "properties": {
        "choices": [
            {"id": "nl", "value": "Netherlands"},
            {"id": "be", "value": "Belgium"},
        ]
    },
}
REQUIRED_IN_NL = [
    _rule("r1", {"required": True}, [_is("country", "Netherlands", "dropdown")])
]


# --- model -------------------------------------------------------------------


def test_the_model_reads_and_writes_rules_in_both_spellings():
    field = StandardFormField.model_validate(
        _q(
            "total",
            "number",
            rules=[
                _rule(
                    "r1",
                    {"readOnly": True, "setValue": {"expression": {"*": [V("q"), 2]}}},
                    expression=True,
                )
            ],
        )
    )
    rule = field.properties.rules[0]
    assert rule.then.read_only is True
    assert rule.then.set_value.expression == {"*": [V("q"), 2]}
    dumped = field.model_dump(by_alias=True)["properties"]["rules"][0]
    assert dumped["then"]["setValue"]["expression"] == {"*": [V("q"), 2]}
    # stored (snake case) and read back
    again = StandardFormField.model_validate(field.model_dump())
    assert again.properties.rules == field.properties.rules


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"id": "r", "when": {}, "then": {"required": True}}, "either conditions"),
        (
            {
                "id": "r",
                "when": {"expression": True, "conditions": [_is("a", "x")]},
                "then": {"required": True},
            },
            "either conditions",
        ),
        (
            {"id": "r", "when": {"conditions": []}, "then": {"required": True}},
            "at least one",
        ),
        (
            {
                "id": "r",
                "when": {"expression": True, "operator": "AND"},
                "then": {"required": True},
            },
            "operator",
        ),
        (
            {
                "id": "r",
                "when": {"expression": {"nope": []}},
                "then": {"required": True},
            },
            "nope",
        ),
        ({"id": "r", "when": {"expression": True}, "then": {}}, "at least one of"),
        (
            {"id": "r", "when": {"expression": True}, "then": {"hidden": True}},
            "Extra inputs",
        ),
        (
            {"id": "r", "when": {"expression": True}, "then": {"readOnly": False}},
            "True",
        ),
        ({"id": "r", "when": {"expression": True}, "then": {"title": " "}}, "empty"),
        (
            {"id": "r", "when": {"expression": True}, "then": {"title": "x" * 301}},
            "300",
        ),
        (
            {
                "id": "r",
                "when": {"expression": True},
                "then": {"description": "x" * 1001},
            },
            "1000",
        ),
        (
            {"id": "r", "when": {"expression": True}, "then": {"setValue": {}}},
            "'const' or 'expression'",
        ),
        (
            {
                "id": "r",
                "when": {"expression": True},
                "then": {"setValue": {"const": 1, "expression": 2}},
            },
            "'const' or 'expression'",
        ),
        (
            {
                "id": "r",
                "when": {"expression": True},
                "then": {"setValue": {"const": "x" * 1001}},
            },
            "1000",
        ),
        (
            {"id": "bad id!", "when": {"expression": True}, "then": {"required": True}},
            "pattern",
        ),
        (
            {
                "id": "r",
                "when": {"expression": True},
                "then": {"required": True},
                "x": 1,
            },
            "Extra",
        ),
    ],
)
def test_bad_rules_are_refused_by_the_model(bad, message):
    with pytest.raises(ValidationError) as error:
        FieldRule.model_validate(bad)
    assert message in str(error.value)


def test_at_most_eight_rules_per_field():
    rules = [_rule(f"r{i}", {"required": True}, expression=True) for i in range(9)]
    with pytest.raises(ValidationError):
        StandardFormField.model_validate(_q("a", rules=rules))
    StandardFormField.model_validate(_q("a", rules=rules[:FIELD_RULES_MAX]))


def test_the_builder_payload_keeps_rules():
    form = _parse_form_body(
        '{"title": "x", "builderVersion": "v2", "fields": [{"id": "p", "type": "slide",'
        ' "properties": {"fields": [{"id": "a", "type": "short_text", "properties":'
        ' {"rules": [{"id": "r1", "when": {"expression": true}, "then":'
        ' {"required": true, "readOnly": true}}]}}]}}]}'
    )
    rule = form.fields[0].properties.fields[0].properties.rules[0]
    assert rule.then.required is True and rule.then.read_only is True


# --- replay: required --------------------------------------------------------


def test_required_while_the_condition_holds():
    form = _form([COUNTRY, _q("postcode", rules=REQUIRED_IN_NL)])
    assert _errors(
        form, {"country": {"type": "choice", "choice": {"value": "nl"}}}
    ) == [("postcode", "required", None)]
    assert (
        _errors(form, {"country": {"type": "choice", "choice": {"value": "be"}}}) == []
    )
    assert _errors(form, {}) == []


def test_optional_when_and_last_active_rule_wins():
    rules = [
        _rule("r1", {"required": False}, [_is("a", None, comparison="IS_NOT_EMPTY")]),
        _rule("r2", {"required": True}, [_is("a", "strict")]),
    ]
    form = _form([_q("a"), _q("b", required=True, rules=rules)])
    assert _errors(form, {}) == [("b", "required", None)]  # static flag
    assert _errors(form, {"a": _text("easy")}) == []  # r1
    assert _errors(form, {"a": _text("strict")}) == [("b", "required", None)]  # r2 last


def test_expression_trigger_and_hidden_fields():
    form = _form(
        [
            _q("qty", "number"),
            _q(
                "reason",
                rules=[
                    _rule(
                        "r1",
                        {"required": True},
                        expression={">": [V("qty"), V("limit")]},
                    )
                ],
            ),
        ],
        hidden_fields=["limit"],
    )
    resolved, states = resolve_field_rules(
        form, _answers({"qty": _num(12)}), {"limit": "10"}
    )
    assert [p.rule for p in validate_answers(form, resolved, rule_states=states)] == [
        "required"
    ]
    resolved, states = resolve_field_rules(
        form, _answers({"qty": _num(12)}), {"limit": "20"}
    )
    assert validate_answers(form, resolved, rule_states=states) == []


def test_title_and_description_are_presentation_only():
    rules = [
        _rule(
            "r1",
            {"title": "Your NL postcode", "description": "Four digits"},
            REQUIRED_IN_NL[0]["when"]["conditions"],
        )
    ]
    form = _form([COUNTRY, _q("postcode", rules=rules)])
    _, states = resolve_field_rules(
        form, _answers({"country": {"type": "choice", "choice": {"value": "nl"}}})
    )
    assert states.texts[("postcode", None, None)] == {
        "title": "Your NL postcode",
        "description": "Four digits",
    }
    assert states.required == {}


# --- replay: read-only and set values ---------------------------------------


def test_read_only_discards_the_submitted_value_and_is_never_required():
    form = _form(
        [
            _q(
                "locked",
                required=True,
                rules=[_rule("r1", {"readOnly": True}, expression=True)],
            )
        ]
    )
    resolved, states = resolve_field_rules(form, _answers({"locked": _text("mine")}))
    assert "locked" not in resolved
    assert validate_answers(form, resolved, rule_states=states) == []
    # an edit stores an empty answer, so the stored value is overwritten
    resolved, _ = resolve_field_rules(
        form, _answers({"locked": _text("mine")}), keep_empty=True
    )
    assert resolved["locked"] == {"field": {"id": "locked"}, "type": "text"}


def test_read_only_keeps_an_active_set_value():
    form = _form(
        [
            _q("a", "number"),
            _q(
                "b",
                "number",
                rules=[
                    _rule("r1", {"setValue": {"const": 5}}, expression=True),
                    _rule("r2", {"readOnly": True}, expression=True),
                ],
            ),
        ]
    )
    resolved, _ = resolve_field_rules(form, _answers({"b": _num(1)}))
    assert resolved["b"]["number"] == 5


def test_set_value_overwrites_the_client_and_an_empty_result_removes_it():
    form = _form(
        [
            _q("qty", "number"),
            _q(
                "total",
                "number",
                rules=[
                    _rule(
                        "r1",
                        {"setValue": {"expression": {"*": [V("qty"), 3]}}},
                        expression=True,
                    )
                ],
            ),
        ]
    )
    resolved, states = resolve_field_rules(
        form, _answers({"qty": _num(2), "total": _num(1)})
    )
    assert resolved["total"] == {
        "field": {"id": "total"},
        "type": "number",
        "number": 6,
    }
    assert "total" in states.locked
    resolved, _ = resolve_field_rules(form, _answers({"total": _num(1)}))
    assert "total" not in resolved


def test_the_last_active_set_value_wins_and_inactive_rules_leave_the_answer():
    rules = [
        _rule("r1", {"setValue": {"const": "first"}}, [_is("a", "x")]),
        _rule("r2", {"setValue": {"const": "second"}}, [_is("b", "y")]),
    ]
    form = _form([_q("a"), _q("b"), _q("c", rules=rules)])
    both = _answers({"a": _text("x"), "b": _text("y"), "c": _text("own")})
    assert resolve_field_rules(form, both)[0]["c"]["text"] == "second"
    one = _answers({"a": _text("x"), "c": _text("own")})
    assert resolve_field_rules(form, one)[0]["c"]["text"] == "first"
    none = _answers({"c": _text("own")})
    assert _plain(resolve_field_rules(form, none)[0])["c"]["text"] == "own"


@pytest.mark.parametrize(
    "field, const, stored",
    [
        (_q("t"), "fixed", {"type": "text", "text": "fixed"}),
        (_q("t", "long_text"), 12, {"type": "text", "text": "12"}),
        (_q("t", "number"), 2.5, {"type": "number", "number": 2.5}),
        (_q("t", "date"), "2026-01-31", {"type": "date", "date": "2026-01-31"}),
        (_q("t", "yes_no"), False, {"type": "boolean", "boolean": False}),
        ({**COUNTRY, "id": "t"}, "be", {"type": "choice", "choice": {"value": "be"}}),
    ],
)
def test_set_value_shapes(field, const, stored):
    field = {
        **field,
        "properties": {
            **field.get("properties", {}),
            "rules": [_rule("r1", {"setValue": {"const": const}}, expression=True)],
        },
    }
    form = _form([field])
    assert field_rule_problems(form) == []
    resolved, _ = resolve_field_rules(form, {})
    assert resolved["t"] == {"field": {"id": "t"}, **stored}


def test_expression_results_that_do_not_fit_are_empty():
    form = _form(
        [
            _q(
                "n",
                "number",
                rules=[
                    _rule("r1", {"setValue": {"expression": "abc"}}, expression=True)
                ],
            ),
            _q(
                "d",
                "date",
                rules=[
                    _rule(
                        "r2",
                        {"setValue": {"expression": "31-01-2026"}},
                        expression=True,
                    )
                ],
            ),
            _q(
                "y",
                "yes_no",
                rules=[
                    _rule(
                        "r3",
                        {"setValue": {"expression": {"==": [1, 1]}}},
                        expression=True,
                    )
                ],
            ),
        ]
    )
    resolved, _ = resolve_field_rules(
        form, _answers({"n": _num(1), "d": {"type": "date", "date": "2026-02-02"}})
    )
    assert "n" not in resolved and "d" not in resolved
    assert resolved["y"]["boolean"] is True


def test_set_value_with_today():
    form = _form(
        [
            _q(
                "d",
                "date",
                rules=[
                    _rule(
                        "r1",
                        {"setValue": {"expression": {"today": []}}},
                        expression=True,
                    )
                ],
            )
        ]
    )
    resolved, _ = resolve_field_rules(form, {}, today="2026-10-30")
    assert resolved["d"]["date"] == "2026-10-30"


# --- replay: calculated fields and order -------------------------------------


def _calc(field_id, expression):
    return {
        "id": field_id,
        "type": "calculated",
        "title": field_id,
        "properties": {"expression": expression},
    }


def test_calculations_and_set_values_follow_each_other_in_any_order():
    # c1 reads the set value of s, which reads the calculation c0
    form = _form(
        [
            _calc("c1", {"+": [V("s"), 1]}),
            _q(
                "s",
                "number",
                rules=[
                    _rule(
                        "r1",
                        {"setValue": {"expression": {"*": [V("c0"), 10]}}},
                        expression=True,
                    )
                ],
            ),
            _calc("c0", {"+": [V("qty"), 1]}),
            _q("qty", "number"),
            _q(
                "why",
                rules=[
                    _rule("r2", {"required": True}, [_is("c1", "31", "calculated")])
                ],
            ),
        ]
    )
    resolved, states = resolve_field_rules(
        form, _answers({"qty": _num(2), "s": _num(0), "c1": _num(0)})
    )
    assert resolved["c0"]["number"] == 3
    assert resolved["s"]["number"] == 30
    assert resolved["c1"]["number"] == 31
    assert [
        p.field_id for p in validate_answers(form, resolved, rule_states=states)
    ] == ["why"]


def test_a_form_without_rules_computes_calculations_as_before():
    from backend.app.services.calculated_fields import apply_calculated_fields

    form = _form([_q("qty", "number"), _calc("double", {"*": [V("qty"), 2]})])
    answers = _answers({"qty": _num(4), "double": _num(1)})
    assert resolve_field_rules(form, answers)[0] == apply_calculated_fields(
        form, answers
    )


# --- replay: repeating groups -------------------------------------------------


GROUP = {
    "id": "g",
    "type": "group",
    "title": "People",
    "properties": {
        "repeat": {"minItems": 1, "maxItems": 3},
        "fields": [
            _q("role"),
            _q(
                "detail",
                rules=[_rule("rg", {"required": True}, [_is("role", "other")])],
            ),
        ],
    },
}


def test_rules_in_a_group_read_their_own_item():
    form = _form([GROUP])
    answers = {
        "g": {
            "type": "group",
            "items": [
                {"role": _text("other")},
                {"role": _text("staff")},
                {"role": _text("other"), "detail": _text("x")},
            ],
        }
    }
    assert _errors(form, answers) == [("detail", "required", 0)]


def test_group_rules_reach_the_item_check_on_submit_too():
    from backend.app.services.repeating_groups import validate_group_answers

    optional = {
        **GROUP,
        "properties": {
            **GROUP["properties"],
            "fields": [
                _q("role"),
                _q(
                    "detail",
                    required=True,
                    rules=[_rule("r1", {"required": False}, [_is("role", "staff")])],
                ),
            ],
        },
    }
    form = _form([optional])
    answers = {"g": {"type": "group", "items": [{"role": _text("staff")}]}}
    # the structural check leaves a rule-driven Required to answer validation
    assert validate_group_answers(form, answers) == []
    assert _errors(form, answers) == []
    answers = {"g": {"type": "group", "items": [{"role": _text("other")}]}}
    assert _errors(form, answers) == [("detail", "required", 0)]


# --- replay: unknown and invalid references ----------------------------------


@pytest.mark.parametrize(
    "when",
    [
        {"conditions": [_is("gone", None, comparison="IS_EMPTY")]},
        {"expression": {"==": [V("gone"), None]}},
        {"expression": {"==": [V("b"), None]}},  # its own field
        {
            "conditions": [
                {
                    "fieldId": "g",
                    "groupMode": "ANY",
                    "childFieldId": "gone",
                    "comparison": "IS_EMPTY",
                }
            ]
        },
    ],
)
def test_a_rule_reading_what_the_form_lacks_is_not_active(when):
    rule = {"id": "r1", "when": when, "then": {"required": True, "readOnly": True}}
    form = _form([GROUP, _q("b", rules=[rule])])
    resolved, states = resolve_field_rules(form, _answers({"b": _text("kept")}))
    assert _plain(resolved)["b"]["text"] == "kept"
    assert states.required == {} and states.locked == set()


# --- save checks --------------------------------------------------------------


def _messages(form):
    return [p.message for p in field_rule_problems(form)]


def _paths(form):
    return [(p.field_id, p.path) for p in field_rule_problems(form)]


def test_a_valid_form_has_no_problems():
    form = _form(
        [
            COUNTRY,
            _q("postcode", rules=REQUIRED_IN_NL),
            _q("qty", "number"),
            _q(
                "total",
                "number",
                rules=[
                    _rule(
                        "r2",
                        {"setValue": {"expression": {"*": [V("qty"), V("rate")]}}},
                        expression=True,
                    )
                ],
            ),
            GROUP,
            _q(
                "note",
                rules=[
                    _rule(
                        "r3",
                        {"description": "Hi {{field:postcode}} {{hidden:rate}}"},
                        [
                            {
                                "fieldId": "g",
                                "groupMode": "COUNT",
                                "comparison": "GREATER_THAN",
                                "value": 1,
                            }
                        ],
                    )
                ],
            ),
        ],
        hidden_fields=["rate"],
    )
    assert field_rule_problems(form) == []


@pytest.mark.parametrize(
    "fields, path, message",
    [
        (
            [_q("b", rules=[_rule("r1", {"required": True}, [_is("gone", "x")])])],
            "/0/when/conditions/0/fieldId",
            "no question",
        ),
        (
            [_q("b", rules=[_rule("r1", {"required": True}, [_is("b", "x")])])],
            "/0/when/conditions/0/fieldId",
            "own answer",
        ),
        (
            [
                _q("a", internal=None),
                {**_q("i"), "internal": True},
                _q("b", rules=[_rule("r1", {"required": True}, [_is("i", "x")])]),
            ],
            "/0/when/conditions/0/fieldId",
            "internal",
        ),
        (
            [
                GROUP,
                _q("b", rules=[_rule("r1", {"required": True}, [_is("role", "x")])]),
            ],
            "/0/when/conditions/0/fieldId",
            "once per item",
        ),
        (
            [GROUP, _q("b", rules=[_rule("r1", {"required": True}, [_is("g", "x")])])],
            "/0/when/conditions/0/groupMode",
            "groupMode",
        ),
        (
            [_q("b", rules=[_rule("r1", {"required": True}, [_is("p0", "x")])])],
            "/0/when/conditions/0/fieldId",
            "a page",
        ),
        (
            [
                _q(
                    "b",
                    rules=[
                        _rule(
                            "r1",
                            {"required": True},
                            [{"fieldId": "a", "comparison": "NEAR"}],
                        )
                    ],
                ),
                _q("a"),
            ],
            "/0/when/conditions/0/comparison",
            "comparison",
        ),
        (
            [
                _q(
                    "b",
                    rules=[
                        _rule("r1", {"required": True}, expression={"+": [V("x"), 1]})
                    ],
                )
            ],
            "/0/when/expression/+/0/var",
            "'x'",
        ),
        (
            [
                _q(
                    "b",
                    rules=[
                        _rule("r1", {"required": True}, expression={"not": [V("b")]})
                    ],
                )
            ],
            "/0/when/expression/not/0/var",
            "own value",
        ),
        (
            [
                _q(
                    "b",
                    "email",
                    rules=[_rule("r1", {"readOnly": True}, expression=True)],
                )
            ],
            "/0/then/readOnly",
            "not 'B'",
        ),
        (
            [
                {
                    **COUNTRY,
                    "type": "multiple_choice",
                    "properties": {
                        **COUNTRY["properties"],
                        "allowMultipleSelection": True,
                        "rules": [
                            _rule("r1", {"setValue": {"const": "nl"}}, expression=True)
                        ],
                    },
                }
            ],
            "/0/then/setValue",
            "several choices",
        ),
        (
            [
                _q(
                    "b",
                    "number",
                    rules=[
                        _rule("r1", {"setValue": {"const": "ten"}}, expression=True)
                    ],
                )
            ],
            "/0/then/setValue/const",
            "a number",
        ),
        (
            [
                _q(
                    "b",
                    "date",
                    rules=[
                        _rule(
                            "r1", {"setValue": {"const": "tomorrow"}}, expression=True
                        )
                    ],
                )
            ],
            "/0/then/setValue/const",
            "YYYY-MM-DD",
        ),
        (
            [
                {
                    **COUNTRY,
                    "properties": {
                        **COUNTRY["properties"],
                        "rules": [
                            _rule("r1", {"setValue": {"const": "de"}}, expression=True)
                        ],
                    },
                }
            ],
            "/0/then/setValue/const",
            "options",
        ),
        (
            [
                {
                    **COUNTRY,
                    "properties": {
                        **COUNTRY["properties"],
                        "rules": [
                            _rule(
                                "r1",
                                {"setValue": {"expression": "nl"}},
                                expression=True,
                            )
                        ],
                    },
                }
            ],
            "/0/then/setValue/expression",
            "const",
        ),
        (
            [
                {
                    **GROUP,
                    "properties": {
                        **GROUP["properties"],
                        "fields": [
                            _q(
                                "role",
                                rules=[
                                    _rule(
                                        "r1",
                                        {"setValue": {"const": "x"}},
                                        expression=True,
                                    )
                                ],
                            )
                        ],
                    },
                }
            ],
            "/0/then/setValue",
            "repeating group",
        ),
        (
            [
                _q(
                    "b",
                    rules=[
                        _rule("r1", {"title": "Hi {{field:gone}}"}, expression=True)
                    ],
                )
            ],
            "/0/then/title",
            "pipes 'gone'",
        ),
        (
            [
                _q(
                    "b",
                    rules=[
                        _rule("r1", {"description": "{{hidden:nope}}"}, expression=True)
                    ],
                )
            ],
            "/0/then/description",
            "pipes 'nope'",
        ),
        (
            [
                {
                    "id": "t",
                    "type": "text",
                    "title": "Read me",
                    "properties": {
                        "rules": [_rule("r1", {"required": True}, expression=True)]
                    },
                }
            ],
            "",
            "cannot have rules",
        ),
        (
            [
                _calc("c", 1)
                | {
                    "properties": {
                        "expression": 1,
                        "rules": [_rule("r1", {"title": "x"}, expression=True)],
                    }
                }
            ],
            "",
            "cannot have rules",
        ),
        (
            [
                {
                    **_q("b"),
                    "internal": True,
                    "properties": {
                        "rules": [_rule("r1", {"title": "x"}, expression=True)]
                    },
                }
            ],
            "",
            "internal",
        ),
    ],
)
def test_save_problems(fields, path, message):
    problems = field_rule_problems(_form(fields))
    assert problems, "expected a problem"
    assert any(p.path == path and message in p.message for p in problems), [
        (p.path, p.message) for p in problems
    ]


def test_rules_on_a_page_or_outside_pages_are_refused():
    form = _form([_q("a")])
    form.fields[0].properties.rules = [
        FieldRule.model_validate(_rule("r1", {"title": "x"}, expression=True))
    ]
    assert any("cannot have rules" in m for m in _messages(form))
    flat = StandardForm.model_validate(
        {"fields": [_q("a", rules=[_rule("r1", {"title": "x"}, expression=True)])]}
    )
    assert any("cannot have rules" in m for m in _messages(flat))


def test_ids_are_unique_and_rules_capped_per_form():
    form = _form(
        [
            _q("a", rules=[_rule("r1", {"title": "x"}, expression=True)]),
            _q("b", rules=[_rule("r1", {"title": "y"}, expression=True)]),
        ]
    )
    assert _paths(form) == [("b", "/0/id")]
    many = _form(
        [
            _q(
                f"q{i}",
                rules=[
                    _rule(f"r{i}-{j}", {"title": "x"}, expression=True)
                    for j in range(8)
                ],
            )
            for i in range(13)
        ]
    )
    assert any("at most 100 rules" in m for m in _messages(many))


def test_circles_through_set_values_and_calculations_are_refused():
    form = _form(
        [
            _q(
                "a",
                "number",
                rules=[
                    _rule(
                        "r1",
                        {"setValue": {"expression": {"+": [V("c"), 1]}}},
                        expression=True,
                    )
                ],
            ),
            _calc("c", {"+": [V("a"), 1]}),
        ]
    )
    assert any("circle" in m for m in _messages(form))
    # a trigger counts as a dependency too
    form = _form(
        [
            _q(
                "a",
                "number",
                rules=[
                    _rule("r1", {"setValue": {"const": 1}}, [_is("b", "1", "number")])
                ],
            ),
            _q(
                "b",
                "number",
                rules=[_rule("r2", {"readOnly": True}, [_is("a", "1", "number")])],
            ),
        ]
    )
    assert any("circle" in m for m in _messages(form))
    # required / title rules never form a circle: nothing reads them back
    form = _form(
        [
            _q("a", rules=[_rule("r1", {"required": True}, [_is("b", "x")])]),
            _q("b", rules=[_rule("r2", {"required": True}, [_is("a", "x")])]),
        ]
    )
    assert field_rule_problems(form) == []


def test_ensure_refuses_with_the_paths():
    form = _form([_q("b", rules=[_rule("r1", {"required": True}, [_is("gone", "x")])])])
    with pytest.raises(HTTPException) as error:
        ensure_valid_field_rules(form)
    assert error.value.status_code == 422
    assert error.value.content["code"] == "invalid_field_rules"
    assert error.value.content["errors"][0]["fieldId"] == "b"
    assert error.value.content["errors"][0]["path"] == "/0/when/conditions/0/fieldId"


def test_a_copy_drops_broken_rules():
    form = _form(
        [
            _q("a"),
            _q(
                "b",
                rules=[
                    _rule("r1", {"required": True}, [_is("gone", "x")]),
                    _rule("r2", {"required": True}, [_is("a", "x")]),
                ],
            ),
        ]
    )
    ensure_valid_field_rules(form, drop=True)
    assert [r.id for r in form.fields[0].properties.fields[1].properties.rules] == [
        "r2"
    ]


def test_an_edit_drops_an_unchanged_rule_it_broke_but_refuses_a_new_broken_one():
    stored = _form(
        [_q("a"), _q("b", rules=[_rule("r1", {"required": True}, [_is("a", "x")])])]
    )
    edited = _form([_q("b", rules=[_rule("r1", {"required": True}, [_is("a", "x")])])])
    ensure_valid_field_rules(edited, existing=stored)
    assert edited.fields[0].properties.fields[0].properties.rules is None
    changed = _form([_q("b", rules=[_rule("r1", {"required": True}, [_is("a", "y")])])])
    with pytest.raises(HTTPException):
        ensure_valid_field_rules(changed, existing=stored)


# --- service paths ------------------------------------------------------------


async def _published(workspace, fields, edit=False):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form(fields), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)
    if edit:
        repo = container.workspace_form_repo()
        workspace_form = await repo.get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form.form_id)
        )
        workspace_form.settings.require_verified_identity = True
        workspace_form.settings.allow_editing_response = True
        await repo.save(workspace_form)
    return form


async def _stored(workspace, response_id):
    stored = await container.form_response_repo().get_response(response_id)
    return (
        container.form_response_service()
        .decrypt_form_response(workspace_id=workspace.id, response=stored)
        .answers
    )


async def test_saving_a_bad_rule_is_422(workspace):
    service = container.workspace_form_service()
    with pytest.raises(HTTPException) as error:
        await service.create_form(
            workspace.id,
            _form(
                [_q("b", rules=[_rule("r1", {"required": True}, [_is("gone", "x")])])]
            ),
            testUser,
        )
    assert error.value.content["code"] == "invalid_field_rules"
    form = await service.create_form(workspace.id, _form([_q("a"), _q("b")]), testUser)
    with pytest.raises(HTTPException) as error:
        await service.update_form(
            workspace.id,
            form.form_id,
            _form(
                [
                    _q("a"),
                    _q(
                        "b",
                        "number",
                        rules=[
                            _rule("r1", {"setValue": {"const": "x"}}, expression=True)
                        ],
                    ),
                ]
            ),
            testUser,
        )
    assert error.value.content["code"] == "invalid_field_rules"


async def test_a_builder_save_that_removes_a_question_drops_the_rules_reading_it(
    workspace,
):
    service = container.workspace_form_service()
    fields = [
        _q("a"),
        _q("b", rules=[_rule("r1", {"required": True}, [_is("a", "x")])]),
    ]
    form = await service.create_form(workspace.id, _form(fields), testUser)
    await service.update_form(workspace.id, form.form_id, _form([fields[1]]), testUser)
    saved = await container.form_service().get_form_document_by_id(str(form.form_id))
    assert saved.fields[0].properties.fields[0].properties.rules is None


async def test_submission_enforces_required_read_only_and_set_values(workspace):
    form = await _published(
        workspace,
        [
            COUNTRY,
            _q("postcode", rules=REQUIRED_IN_NL),
            _q("qty", "number"),
            _q(
                "total",
                "number",
                rules=[
                    _rule(
                        "r2",
                        {"setValue": {"expression": {"*": [V("qty"), 10]}}},
                        expression=True,
                    )
                ],
            ),
            _q("ref", rules=[_rule("r3", {"readOnly": True}, expression=True)]),
        ],
    )
    service = container.workspace_form_service()
    nl = {"type": "choice", "choice": {"value": "nl"}}
    with pytest.raises(HTTPException) as error:
        await service.submit_response(
            workspace.id,
            form.form_id,
            StandardFormResponseCamelModel(answers={"country": nl}),
            testUser,
        )
    assert error.value.status_code == 422
    assert error.value.content["errors"] == [
        {"fieldId": "postcode", "rule": "required"}
    ]
    response = await service.submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={
                "country": nl,
                "postcode": _text("1234 AB"),
                "qty": _num(3),
                "total": _num(1),
                "ref": _text("tampered"),
            }
        ),
        testUser,
    )
    answers = await _stored(workspace, response.response_id)
    assert answers["total"]["number"] == 30
    assert "ref" not in answers
    assert answers["postcode"]["text"] == "1234 AB"


async def test_an_edit_recomputes_set_values_and_reports_newly_required(workspace):
    form = await _published(
        workspace,
        [
            COUNTRY,
            _q("postcode", rules=REQUIRED_IN_NL),
            _q("qty", "number"),
            _q(
                "total",
                "number",
                rules=[
                    _rule(
                        "r2",
                        {"setValue": {"expression": {"*": [V("qty"), 10]}}},
                        expression=True,
                    )
                ],
            ),
        ],
        edit=True,
    )
    service = container.workspace_form_service()
    submitted = await service.submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={
                "country": {"type": "choice", "choice": {"value": "be"}},
                "qty": _num(1),
            }
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
        return await _stored(workspace, submitted.response_id)

    answers = await edit({"qty": _num(4), "total": _num(1)})
    assert answers["total"]["number"] == 40
    # the edit leaves the postcode alone, but its rule now requires it
    with pytest.raises(HTTPException) as error:
        await edit({"country": {"type": "choice", "choice": {"value": "nl"}}})
    assert error.value.content["errors"] == [
        {"fieldId": "postcode", "rule": "required"}
    ]
    # an empty result overwrites the stored value
    answers = await edit({"qty": {"type": "number"}})
    assert "number" not in answers["total"]


def test_edit_helpers():
    form = _form(
        [
            COUNTRY,
            _q("postcode", rules=REQUIRED_IN_NL),
            _q("qty", "number"),
            _q(
                "total",
                "number",
                rules=[
                    _rule(
                        "r2",
                        {"setValue": {"expression": {"*": [V("qty"), 10]}}},
                        expression=True,
                    )
                ],
            ),
            GROUP,
        ]
    )
    assert server_value_ids(form) == ["total"]
    assert rule_keys_reading(form, ["country"]) == {"postcode"}
    assert rule_keys_reading(form, ["qty"]) == {"total"}
    assert rule_keys_reading(form, ["g"]) == {"g"}
    assert rule_keys_reading(form, ["other"]) == set()


# --- form spec ----------------------------------------------------------------


def test_the_spec_round_trips_rules_and_checks_them():
    form = _form(
        [
            COUNTRY,
            _q("postcode", rules=REQUIRED_IN_NL),
            _q("qty", "number"),
            _q(
                "total",
                "number",
                rules=[
                    _rule(
                        "r2",
                        {
                            "readOnly": True,
                            "setValue": {"expression": {"*": [V("qty"), 2]}},
                        },
                        expression=True,
                    )
                ],
            ),
            _q(
                "y",
                "yes_no",
                rules=[
                    _rule(
                        "r3",
                        {"setValue": {"const": False}, "title": "Fixed"},
                        expression=True,
                    )
                ],
            ),
        ]
    )
    document = form_to_spec_dict(form)
    rules = document["pages"][0]["fields"][1]["rules"]
    assert rules == [
        {
            "id": "r1",
            "when": {
                "conditions": [
                    {
                        "fieldId": "country",
                        "fieldType": "dropdown",
                        "comparison": "IS_EQUAL",
                        "value": "Netherlands",
                    }
                ]
            },
            "then": {"required": True},
        }
    ]
    assert document["pages"][0]["fields"][4]["rules"][0]["then"]["setValue"] == {
        "const": False
    }
    back = spec_to_form(FormSpec.model_validate(document))
    assert form_to_spec_dict(back) == document
    assert check_spec_document(document)["valid"] is True

    document["pages"][0]["fields"][1]["rules"][0]["when"]["conditions"][0][
        "fieldId"
    ] = "gone"
    result = check_spec_document(document)
    assert result["valid"] is False
    assert (
        result["errors"][0]["path"]
        == "/pages/0/fields/1/rules/0/when/conditions/0/fieldId"
    )


def test_the_spec_refuses_unknown_rule_keys_and_too_many_rules():
    base = {
        "specVersion": "1",
        "pages": [{"id": "p", "fields": [{"id": "a", "type": "short_text"}]}],
    }
    bad = {
        **base,
        "pages": [
            {
                "id": "p",
                "fields": [
                    {
                        "id": "a",
                        "type": "short_text",
                        "rules": [
                            {
                                "id": "r",
                                "when": {"expression": True},
                                "then": {"hide": True},
                            }
                        ],
                    }
                ],
            }
        ],
    }
    assert check_spec_document(bad)["valid"] is False
    fields = [
        {
            "id": f"q{i}",
            "type": "short_text",
            "rules": [
                {
                    "id": f"r{i}-{j}",
                    "when": {"expression": True},
                    "then": {"title": "x"},
                }
                for j in range(8)
            ],
        }
        for i in range(13)
    ]
    many = {**base, "pages": [{"id": "p", "fields": fields}]}
    result = check_spec_document(many)
    assert result["valid"] is False
    assert "at most 100 rules" in result["errors"][0]["message"]


# --- edit operations -----------------------------------------------------------


def test_removing_a_question_drops_the_rules_reading_it():
    form = _form(
        [_q("a"), _q("b", rules=[_rule("r1", {"required": True}, [_is("a", "x")])])]
    )
    after, results = apply_form_ops(
        form, parse_ops([{"op": "remove_field", "fieldId": "a"}])
    )
    assert after.fields[0].properties.fields[0].properties.rules is None
    assert "field rule" in results[0].message


def test_finished_form_leaves_no_broken_rule():
    form = _form([_q("b", rules=[_rule("r1", {"required": True}, [_is("gone", "x")])])])
    assert finished_form(form).fields[0].properties.fields[0].properties.rules is None


def test_an_editor_op_cannot_bring_a_broken_rule():
    form = _form([_q("a")])
    payload = [
        {
            "op": "insert_field",
            "pageId": "p0",
            "index": 1,
            "field": _q(
                "b", rules=[_rule("r1", {"required": True}, [_is("gone", "x")])]
            ),
        }
    ]
    after, results = apply_form_ops(form, parse_ops(payload, allow_editor_ops=True))
    assert results[0].ok is False
    assert "no question" in results[0].message
    assert [f.id for f in after.fields[0].properties.fields] == ["a"]
