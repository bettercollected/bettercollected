"""Pure helpers and AI ops for internal fields (no database)."""

import json

from common.models.standard_form import StandardForm, StandardFormResponse

from backend.app.services.ai.ops import (
    AddFieldOp,
    FieldLogicSpec,
    FieldPatch,
    LogicConditionSpec,
    NewFieldSpec,
    PageJumpSpec,
    SetFieldLogicOp,
    SetPageJumpsOp,
    UpdateFieldOp,
    apply_form_ops,
)
from backend.app.services.internal_fields import (
    internal_field_ids,
    internal_logic_violations,
    strip_internal_answers,
    strip_internal_fields,
)
from tests.app.services.test_internal_fields import (
    NAME,
    REFERENCE,
    REVIEWER,
    STATUS,
    _field,
    _form_payload,
)

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_strip_removes_internal_fields_and_pages_left_empty():
    form = StandardForm(**_form_payload())
    assert internal_field_ids(form) == {REFERENCE, STATUS, REVIEWER}

    stripped = strip_internal_fields(form)
    assert [slide.id for slide in stripped.fields] == ["page-1"]
    assert [f.id for f in stripped.fields[0].properties.fields] == [NAME]


def test_strip_works_on_raw_dicts_and_keeps_originally_empty_pages():
    payload = _form_payload()
    payload["fields"].append(
        {"id": "page-3", "index": 2, "type": "slide", "properties": {"fields": []}}
    )
    stripped = strip_internal_fields(payload)
    assert [slide["id"] for slide in stripped["fields"]] == ["page-1", "page-3"]
    assert REFERENCE not in json.dumps(stripped)


def test_strip_handles_flat_forms():
    flat = {
        "fields": [_field(NAME, 0, "Name"), _field(REFERENCE, 1, "Ref", internal=True)]
    }
    assert [f["id"] for f in strip_internal_fields(flat)["fields"]] == [NAME]


def test_strip_internal_answers_from_models_and_dicts():
    model = StandardFormResponse(internal_answers={"x": {"text": "1"}})
    assert strip_internal_answers(model).internal_answers is None
    camel = {"internalAnswers": {"x": {}}, "internalAnswersMeta": {}, "answers": {}}
    assert strip_internal_answers(camel) == {"answers": {}}


def test_logic_depending_on_internal_fields_is_reported():
    payload = _form_payload()
    payload["fields"][0]["properties"]["fields"][0]["properties"]["logic"] = {
        "action": "SHOW",
        "operator": "AND",
        "conditions": [{"fieldId": REFERENCE, "comparison": "is_not_empty"}],
    }
    payload["fields"][0]["properties"]["jumps"] = [
        {
            "operator": "AND",
            "target": "__SUBMIT__",
            "conditions": [{"fieldId": STATUS, "comparison": "is_empty"}],
        }
    ]
    problems = internal_logic_violations(StandardForm(**payload))
    assert len(problems) == 2
    assert internal_logic_violations(StandardForm(**_form_payload())) == []


def test_ai_ops_support_the_internal_flag_and_refuse_internal_logic():
    form = StandardForm(**_form_payload())

    new_form, results = apply_form_ops(
        form,
        [
            AddFieldOp(
                page_id="page-1",
                field=NewFieldSpec(
                    title="Case owner", type="short_text", internal=True
                ),
            ),
            UpdateFieldOp(field_id=REVIEWER, patch=FieldPatch(internal=False)),
        ],
    )
    assert all(r.ok for r in results), results
    added = [f for f in new_form.fields[0].properties.fields if f.title == "Case owner"]
    assert added[0].internal is True
    assert REVIEWER not in internal_field_ids(new_form)

    _, results = apply_form_ops(
        form,
        [
            SetFieldLogicOp(
                field_id=NAME,
                logic=FieldLogicSpec(
                    action="SHOW",
                    operator="AND",
                    conditions=[
                        LogicConditionSpec(
                            field_id=REFERENCE, comparison="IS_NOT_EMPTY"
                        )
                    ],
                ),
            ),
            SetPageJumpsOp(
                page_id="page-1",
                jumps=[
                    PageJumpSpec(
                        operator="AND",
                        target="__SUBMIT__",
                        conditions=[
                            LogicConditionSpec(field_id=STATUS, comparison="IS_EMPTY")
                        ],
                    )
                ],
            ),
        ],
    )
    assert [r.ok for r in results] == [False, False]
    assert "internal" in results[0].message


def test_ai_ops_refuse_to_make_a_logic_source_internal():
    payload = _form_payload()
    payload["fields"][0]["properties"]["fields"].append(
        _field(
            "field-follow-up",
            2,
            "Follow-up",
            properties={
                "logic": {
                    "action": "SHOW",
                    "operator": "AND",
                    "conditions": [{"fieldId": NAME, "comparison": "IS_NOT_EMPTY"}],
                }
            },
        )
    )
    new_form, results = apply_form_ops(
        StandardForm(**payload),
        [UpdateFieldOp(field_id=NAME, patch=FieldPatch(internal=True))],
    )
    assert not results[0].ok
    assert NAME not in internal_field_ids(new_form)
