"""Calculated fields: model, save checks (paths, unknown/internal fields,
cycles), server recompute on submit and edit, logic on calculated values,
AI ops and the form spec."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from common.form_spec import form_to_spec_dict
from common.models.standard_form import StandardForm

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import (
    StandardFormCamelModel,
    StandardFormResponseCamelModel,
)
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.answer_validation import validate_answers
from backend.app.services.calculated_fields import (
    apply_calculated_fields,
    calculated_answer,
    calculated_field_problems,
    compute_calculated_values,
    evaluation_order,
    calculated_fields,
)
from backend.app.services.form_spec.checks import check_spec_document
from tests.app.controllers.data import testUser

V = lambda key: {"var": key}  # noqa: E731

QTY = {"id": "qty", "type": "number", "title": "Quantity"}
PRICE = {"id": "price", "type": "number", "title": "Price"}
NOTE = {"id": "note", "type": "short_text", "title": "Office note", "internal": True}
ITEMS = {
    "id": "items",
    "type": "group",
    "title": "Items",
    "properties": {
        "repeat": {"minItems": 0, "maxItems": 5},
        "fields": [{"id": "amount", "type": "number", "title": "Amount"}],
    },
}


def _calc(field_id, expression, title=None, **properties):
    return {
        "id": field_id,
        "type": "calculated",
        "title": title or field_id.title(),
        "properties": {"expression": expression, **properties},
    }


SUBTOTAL = _calc("subtotal", {"*": [V("qty"), V("price")]}, "Subtotal")
TOTAL = _calc(
    "total",
    {"round": [{"*": [V("subtotal"), 1.21]}, 2]},
    "Total",
    format={"style": "currency", "decimals": 2, "currency": "EUR"},
)


def _form(*pages, hidden_fields=None):
    return StandardForm.model_validate(
        {
            "builder_version": "v2",
            "title": "Order",
            "hidden_fields": hidden_fields,
            "fields": [
                {
                    "id": f"p{i}",
                    "type": "slide",
                    "index": i,
                    "properties": {"fields": fields},
                }
                for i, fields in enumerate(pages)
            ],
        }
    )


def _num(value):
    return {"type": "number", "number": value}


# --- model -------------------------------------------------------------------


def test_the_model_keeps_expression_format_and_visibility():
    form = _form(
        [
            QTY,
            _calc(
                "c",
                {"+": [V("qty"), 1]},
                format={"style": "percent"},
                hiddenFromRespondents=True,
            ),
        ]
    )
    calc = form.fields[0].properties.fields[1]
    assert calc.properties.expression == {"+": [{"var": "qty"}, 1]}
    assert calc.properties.format.style == "percent"
    assert calc.properties.hidden_from_respondents is True
    # the builder's camelCase payload reads the same
    camel = StandardFormCamelModel.model_validate(
        {
            "fields": [
                {
                    "id": "p",
                    "type": "slide",
                    "properties": {
                        "fields": [
                            {
                                "id": "c",
                                "type": "calculated",
                                "properties": {
                                    "expression": {"date_diff_days": [V("a"), V("b")]},
                                    "hiddenFromRespondents": True,
                                },
                            }
                        ]
                    },
                }
            ]
        }
    )
    props = camel.fields[0].properties.fields[0].properties
    assert props.expression == {"date_diff_days": [{"var": "a"}, {"var": "b"}]}


@pytest.mark.parametrize(
    "bad", [{"style": "money"}, {"decimals": 9}, {"currency": "eur"}]
)
def test_bad_formats_are_refused(bad):
    with pytest.raises(ValueError):
        _form([_calc("c", 1, format=bad)])


# --- save checks -------------------------------------------------------------


def test_a_valid_form_has_no_problems():
    form = _form(
        [
            QTY,
            PRICE,
            ITEMS,
            SUBTOTAL,
            TOTAL,
            _calc("n", {"sum": [V("items.amount"), V("ref")]}),
        ],
        hidden_fields=["ref"],
    )
    assert calculated_field_problems(form) == []


def test_a_malformed_ast_is_reported_with_its_path():
    form = _form([QTY, _calc("c", {"+": [V("qty"), {"pow": [2, 3]}]})])
    [problem] = calculated_field_problems(form)
    assert (problem.field_id, problem.path) == ("c", "/+/1/pow")
    assert "Unknown operator" in problem.message


def test_unknown_and_internal_variables_are_reported():
    form = _form([QTY, NOTE, _calc("c", {"+": [V("qty"), V("nope"), V("note")]})])
    problems = calculated_field_problems(form)
    assert [p.path for p in problems] == ["/+/1/var", "/+/2/var"]
    assert "unknown field" in problems[0].message
    assert "internal field" in problems[1].message


def test_a_group_question_is_only_read_through_its_group_key():
    form = _form([ITEMS, _calc("c", {"sum": [V("amount")]})])
    assert [p.path for p in calculated_field_problems(form)] == ["/sum/0/var"]


def test_cycles_are_refused_naming_the_fields():
    a = _calc("a", {"+": [V("b"), 1]}, "Alpha")
    b = _calc("b", {"+": [V("a"), 1]}, "Beta")
    problems = calculated_field_problems(_form([a, b]))
    assert len(problems) == 1
    assert "circle" in problems[0].message
    assert "'Alpha'" in problems[0].message and "'Beta'" in problems[0].message
    selfish = _calc("s", {"+": [V("s"), 1]}, "Self")
    assert (
        "circle ('Self' → 'Self')"
        in calculated_field_problems(_form([selfish]))[0].message
    )


def test_a_calculation_cannot_be_internal():
    calc = {**_calc("c", 1), "internal": True}
    assert "internal" in calculated_field_problems(_form([calc]))[0].message


def test_no_formula_yet_is_fine():
    assert calculated_field_problems(_form([_calc("c", None)])) == []


async def test_saving_a_bad_calculation_is_422_with_the_path(workspace):
    service = container.workspace_form_service()
    with pytest.raises(HTTPException) as error:
        await service.create_form(
            workspace.id, _form([QTY, _calc("c", {"+": [V("qty"), V("x")]})]), testUser
        )
    assert error.value.status_code == 422
    assert error.value.content["code"] == "invalid_calculation"
    assert error.value.content["errors"][0] == {
        "fieldId": "c",
        "path": "/+/1/var",
        "message": error.value.content["errors"][0]["message"],
    }
    form = await service.create_form(
        workspace.id, _form([QTY, PRICE, SUBTOTAL]), testUser
    )
    a = _calc("a", {"+": [V("b"), 1]})
    b = _calc("b", {"+": [V("a"), 1]})
    with pytest.raises(HTTPException) as error:
        await service.update_form(workspace.id, form.form_id, _form([a, b]), testUser)
    assert "circle" in error.value.content["message"]


# --- evaluation --------------------------------------------------------------


def test_values_follow_dependencies_whatever_the_order():
    form = _form([TOTAL], [QTY, PRICE, SUBTOTAL])
    assert [f.id for f in evaluation_order(calculated_fields(form))] == [
        "subtotal",
        "total",
    ]
    values = compute_calculated_values(form, {"qty": _num(3), "price": _num(19.99)})
    assert values == {"subtotal": Decimal("59.97"), "total": Decimal("72.56")}


def test_group_lists_hidden_fields_and_today():
    form = _form(
        [
            ITEMS,
            _calc("sum", {"sum": [V("items.amount")]}),
            _calc("src", {"concat": [V("utm"), "-", {"today": []}]}),
        ],
        hidden_fields=["utm"],
    )
    answers = {
        "items": {
            "type": "group",
            "items": [{"amount": _num(2)}, {}, {"amount": _num(0.5)}],
        }
    }
    values = compute_calculated_values(
        form, answers, {"utm": "mail", "other": "x"}, "2026-10-17"
    )
    assert values == {"sum": Decimal("2.5"), "src": "mail-2026-10-17"}


def test_over_cap_input_counts_as_empty():
    form = _form(
        [
            {"id": "t", "type": "long_text"},
            _calc("n", {"length": [V("t")]}, unansweredAsZero=False),
        ]
    )
    values = compute_calculated_values(
        form, {"t": {"type": "text", "text": "x" * 10001}}
    )
    assert values == {"n": None}


def test_stored_answer_shapes():
    assert calculated_answer("c", Decimal("12")) == {
        "field": {"id": "c"},
        "type": "number",
        "number": 12,
    }
    assert calculated_answer("c", Decimal("0.3"))["number"] == 0.3
    assert calculated_answer("c", True)["boolean"] is True
    assert calculated_answer("c", "adult")["text"] == "adult"
    assert calculated_answer("c", None) == {"field": {"id": "c"}, "type": "text"}


def test_client_values_are_replaced_and_empty_results_dropped():
    form = _form([QTY, PRICE, SUBTOTAL])
    sent = {"qty": _num(2), "price": _num(5), "subtotal": _num(1_000_000)}
    out = apply_calculated_fields(form, sent)
    assert out["subtotal"]["number"] == 10
    # unanswered counts as 0 by default
    out = apply_calculated_fields(form, {"qty": _num(2), "subtotal": _num(9)})
    assert out["subtotal"]["number"] == 0
    strict = _form(
        [
            QTY,
            PRICE,
            {
                **SUBTOTAL,
                "properties": {**SUBTOTAL["properties"], "unansweredAsZero": False},
            },
        ]
    )
    assert "subtotal" not in apply_calculated_fields(
        strict, {"qty": _num(2), "subtotal": _num(9)}
    )


def test_logic_and_jumps_use_the_server_value():
    score = _calc("score", {"*": [V("qty"), 10]})
    vip = {
        "id": "vip",
        "type": "short_text",
        "title": "VIP code",
        "validations": {"required": True},
        "properties": {
            "logic": {
                "action": "SHOW",
                "conditions": [
                    {
                        "fieldId": "score",
                        "fieldType": "calculated",
                        "comparison": "GREATER_THAN",
                        "value": 50,
                    }
                ],
            }
        },
    }
    form = _form([QTY, score], [vip])
    # the client claims a low score to skip the required question: ignored
    answers = apply_calculated_fields(form, {"qty": _num(9), "score": _num(1)})
    assert [(p.field_id, p.rule) for p in validate_answers(form, answers)] == [
        ("vip", "required")
    ]
    answers = apply_calculated_fields(form, {"qty": _num(2), "score": _num(100)})
    assert validate_answers(form, answers) == []


def test_jumps_on_a_calculated_value():
    score = _calc("score", {"if": [{">=": [V("qty"), 3]}, "big", "small"]})
    page1 = {
        "id": "p0",
        "type": "slide",
        "index": 0,
        "properties": {
            "fields": [QTY, score],
            "jumps": [
                {
                    "conditions": [
                        {
                            "fieldId": "score",
                            "fieldType": "calculated",
                            "comparison": "IS_EQUAL",
                            "value": "big",
                        }
                    ],
                    "target": "__SUBMIT__",
                }
            ],
        },
    }
    required = {"id": "more", "type": "short_text", "validations": {"required": True}}
    form = StandardForm.model_validate(
        {
            "builder_version": "v2",
            "fields": [
                page1,
                {
                    "id": "p1",
                    "type": "slide",
                    "index": 1,
                    "properties": {"fields": [required]},
                },
            ],
        }
    )
    assert validate_answers(form, apply_calculated_fields(form, {"qty": _num(5)})) == []
    assert validate_answers(
        form,
        apply_calculated_fields(
            form, {"qty": _num(1), "score": {"type": "text", "text": "big"}}
        ),
    )


# --- submission and edit -----------------------------------------------------


async def _published(workspace, fields, settings=None):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form(fields), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)
    return form


def _stored_answers(workspace, response):
    return (
        container.form_response_service()
        .decrypt_form_response(workspace_id=workspace.id, response=response)
        .answers
    )


async def test_submission_stores_the_server_value(workspace):
    form = await _published(workspace, [QTY, PRICE, SUBTOTAL, TOTAL])
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(
            answers={
                "qty": _num(2),
                "price": _num(10),
                "subtotal": _num(1),
                "total": {"type": "text", "text": "free"},
            }
        ),
        testUser,
    )
    stored = await container.form_response_repo().get_response(response.response_id)
    answers = _stored_answers(workspace, stored)
    assert answers["subtotal"]["number"] == 20
    assert answers["total"]["number"] == 24.2
    assert "text" not in answers["total"]


async def test_an_edit_recomputes_and_ignores_the_client_value(workspace):
    strict = {
        **SUBTOTAL,
        "properties": {**SUBTOTAL["properties"], "unansweredAsZero": False},
    }
    form = await _published(workspace, [QTY, PRICE, strict])
    repo = container.workspace_form_repo()
    workspace_form = await repo.get_workspace_form_in_workspace(
        workspace_id=workspace.id, query=str(form.form_id)
    )
    workspace_form.settings.require_verified_identity = True
    workspace_form.settings.allow_editing_response = True
    await repo.save(workspace_form)
    service = container.workspace_form_service()
    submitted = await service.submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers={"qty": _num(2), "price": _num(3)}),
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
        stored = await container.form_response_repo().get_response(
            submitted.response_id
        )
        return _stored_answers(workspace, stored)

    answers = await edit({"qty": _num(5), "subtotal": _num(1)})
    assert answers["subtotal"]["number"] == 15
    # an empty result overwrites the stored value
    answers = await edit({"price": {"type": "number"}})
    assert "number" not in answers["subtotal"]


# --- AI ops ------------------------------------------------------------------


def _apply(form, payload):
    return apply_form_ops(form, parse_ops(payload))


def test_ops_add_and_update_a_calculation():
    form = _form([QTY, PRICE])
    new, results = _apply(
        form,
        [
            {
                "op": "add_field",
                "pageId": "p0",
                "ref": "sub",
                "field": {
                    "title": "Subtotal",
                    "type": "calculated",
                    "expression": {"*": [V("qty"), V("price")]},
                    "format": {"style": "currency", "decimals": 2},
                },
            },
            {
                "op": "add_field",
                "pageId": "p0",
                "field": {
                    "title": "Total",
                    "type": "calculated",
                    "expression": {"*": [V("$ref:sub"), 1.21]},
                    "hiddenFromRespondents": True,
                },
            },
        ],
    )
    assert all(r.ok for r in results), results
    sub, total = new.fields[0].properties.fields[2:]
    assert (
        sub.properties.format.currency is None
        and sub.properties.format.style == "currency"
    )
    assert total.properties.expression == {"*": [{"var": sub.id}, 1.21]}
    assert total.properties.hidden_from_respondents is True
    new, results = _apply(
        new,
        [
            {
                "op": "update_field",
                "fieldId": sub.id,
                "patch": {"expression": {"+": [V("qty"), V("price")]}},
            }
        ],
    )
    assert results[0].ok and "formula" in results[0].message
    assert new.fields[0].properties.fields[2].properties.expression == {
        "+": [V("qty"), V("price")]
    }


@pytest.mark.parametrize(
    "op, message",
    [
        (
            {
                "op": "add_field",
                "pageId": "p0",
                "field": {
                    "title": "X",
                    "type": "calculated",
                    "expression": {"pow": [1]},
                },
            },
            "'/pow'",
        ),
        (
            {
                "op": "add_field",
                "pageId": "p0",
                "field": {"title": "X", "type": "calculated", "expression": V("ghost")},
            },
            "unknown field",
        ),
        (
            {
                "op": "add_field",
                "pageId": "p0",
                "field": {"title": "X", "type": "number", "expression": 1},
            },
            "only calculated",
        ),
        (
            {
                "op": "update_field",
                "fieldId": "subtotal",
                "patch": {"expression": V("subtotal")},
            },
            "circle",
        ),
        ({"op": "remove_field", "fieldId": "qty"}, "unknown field"),
        (
            {"op": "update_field", "fieldId": "qty", "patch": {"internal": True}},
            "internal field",
        ),
    ],
)
def test_ops_refuse_what_a_save_would_refuse(op, message):
    form = _form([QTY, PRICE, SUBTOTAL])
    new, results = _apply(form, [op])
    assert not results[0].ok
    assert message in results[0].message, results[0].message
    assert calculated_field_problems(new) == []
    assert [f.id for f in new.fields[0].properties.fields] == [
        "qty",
        "price",
        "subtotal",
    ]


# --- form spec ---------------------------------------------------------------


def test_the_spec_round_trips_and_checks_calculations():
    document = form_to_spec_dict(_form([QTY, PRICE, SUBTOTAL, TOTAL]))
    total = document["pages"][0]["fields"][3]
    assert total["type"] == "calculated"
    assert total["format"] == {"style": "currency", "decimals": 2, "currency": "EUR"}
    assert check_spec_document(document)["valid"] is True
    total["expression"] = {"*": [V("subtotal"), V("missing")]}
    result = check_spec_document(document)
    assert result["errors"] == [
        {
            "path": "/pages/0/fields/3/expression/*/1/var",
            "message": "'Total' uses an unknown field or hidden field.",
        }
    ]
    # not a legacy type any more
    assert not any("legacy" in w["message"] for w in result["warnings"])


# --- shared cases with the webapp (docs/spec/calculated-fields.cases.json) ---

CASES = json.loads(
    (
        Path(__file__).resolve().parents[4]
        / "docs"
        / "spec"
        / "calculated-fields.cases.json"
    ).read_text()
)["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_case(case):
    form = StandardForm.model_validate(
        {
            "builder_version": "v2",
            "hidden_fields": case.get("hiddenFields"),
            "fields": [
                {"id": "p", "type": "slide", "properties": {"fields": case["fields"]}}
            ],
        }
    )
    values = compute_calculated_values(form, case["answers"], case.get("hidden") or {})
    plain = {
        key: (float(value) if isinstance(value, Decimal) else value)
        for key, value in values.items()
    }
    assert plain == case["expected"]


def test_unanswered_as_zero_defaults():
    from backend.app.services.calculated_fields import unanswered_as_zero

    form = _form(
        [
            _calc("a", 1),
            _calc("b", 1, format={"style": "text"}),
            _calc("c", 1, format={"style": "text"}, unansweredAsZero=True),
            _calc("d", 1, format={"style": "percent"}, unansweredAsZero=False),
        ]
    )
    fields = form.fields[0].properties.fields
    assert [unanswered_as_zero(f) for f in fields] == [True, False, True, False]


def test_ops_set_unanswered_as_zero():
    form = _form([QTY, PRICE, SUBTOTAL])
    new, results = _apply(
        form,
        [
            {
                "op": "update_field",
                "fieldId": "subtotal",
                "patch": {"unansweredAsZero": False},
            }
        ],
    )
    assert results[0].ok and "unanswered as 0" in results[0].message
    assert new.fields[0].properties.fields[2].properties.unanswered_as_zero is False
