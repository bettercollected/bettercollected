"""The signature question's rules around the answer: what a stored signature
may hold, what logic, rules, calculations and groups may do with the question,
what the export, the AI insights and the email/webhook mappings make of it. The
shape and name cases are also in the shared cases
(docs/spec/answer-validation.cases.json); the image is services/signatures.py."""

import json

import pytest

from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.services.ai.insights import _answer_text
from backend.app.services.answer_validation import validate_answers
from backend.app.services.calculated_fields import calculated_field_problems
from backend.app.services.field_rules import field_rule_problems
from backend.app.services.registration import body as body_builder
from backend.app.services.repeating_groups import evaluate_condition
from backend.app.services.response_export.table import answer_value
from common.signature import (
    SIGNATURE_NAME_MAX,
    is_plain_image_id,
    is_signature_name,
    normalised_name,
)


def _form(*fields):
    return _parse_form_body(
        json.dumps(
            {
                "title": "Signed",
                "builderVersion": "v2",
                "fields": [{"id": "p1", "type": "slide", "properties": {"fields": list(fields)}}],
            }
        )
    )


SIGN = {"id": "sig", "type": "signature", "title": "Sign"}
NAME = {"id": "name", "type": "short_text", "title": "Name"}
REQUIRED = {**SIGN, "validations": {"required": True}}


def _rules(form, answers):
    return sorted((p.field_id, p.rule) for p in validate_answers(form, answers))


def _typed(name):
    return {"sig": {"type": "signature", "signature": {"method": "typed", "name": name}}}


def _drawn(file_id="img-1"):
    return {"sig": {"type": "signature", "signature": {"method": "drawn", "file_id": file_id}}}


# --- the answer ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "answers,expected",
    [
        (_typed("Fatima El Idrissi"), []),
        (_typed("李小龙"), []),
        (_typed("x" * SIGNATURE_NAME_MAX), []),
        (_typed("x" * (SIGNATURE_NAME_MAX + 1)), [("sig", "too_long")]),
        (_typed(""), [("sig", "format")]),
        (_typed(" padded"), [("sig", "format")]),
        (_typed("a​b"), [("sig", "format")]),  # zero width
        (_typed("a‮b"), [("sig", "format")]),  # right-to-left override
        (_typed("a\nb"), [("sig", "format")]),
        (_typed("é"), [("sig", "format")]),  # not in Unicode form C
        (_drawn(), []),
        (_drawn("../x"), [("sig", "signature_image")]),
        (_drawn(""), [("sig", "signature_image")]),
        ({"sig": {"type": "signature", "signature": {"method": "typed", "name": "A", "file_id": "x"}}}, [("sig", "format")]),
        ({"sig": {"type": "signature", "signature": {"method": "drawn", "file_id": "x", "name": "A"}}}, [("sig", "format")]),
        ({"sig": {"type": "signature", "signature": {"method": "scribble", "name": "A"}}}, [("sig", "format")]),
        ({"sig": {"type": "signature", "signature": {"method": "typed", "name": "A", "extra": 1}}}, [("sig", "type")]),
        ({"sig": {"type": "signature", "signature": "Fatima"}}, [("sig", "type")]),
        ({"sig": {"type": "signature", "text": "Fatima"}}, [("sig", "type")]),
        ({"sig": {"type": "signature", "signature": {"method": "typed", "name": "A"}, "text": "x"}}, [("sig", "type")]),
    ],
)
def test_what_a_stored_signature_may_hold(answers, expected):
    assert _rules(_form(SIGN), answers) == expected


def test_a_signature_in_another_question_s_slot_is_refused():
    form = _form(SIGN, NAME)
    answers = {"name": {"type": "text", "signature": {"method": "typed", "name": "A"}}}
    assert _rules(form, answers) == [("name", "type")]


def test_required_counts_a_typed_name_or_a_drawn_image_and_nothing_else():
    form = _form(REQUIRED)
    assert _rules(form, {}) == [("sig", "required")]
    assert _rules(form, {"sig": {"type": "signature"}}) == [("sig", "required")]
    assert _rules(form, _typed("Ada")) == []
    assert _rules(form, _drawn()) == []
    # an optional one may be left empty
    assert _rules(_form(SIGN), {}) == []


def test_the_hard_rules_hold_for_a_hidden_question_too():
    hidden = {
        **SIGN,
        "properties": {"logic": {"action": "HIDE", "operator": "AND", "conditions": [{"fieldId": "name", "fieldType": "short_text", "comparison": "IS_EQUAL", "value": "skip"}]}},
    }
    answers = {"name": {"type": "text", "text": "skip"}, **_typed("a​b")}
    assert _rules(_form(NAME, hidden), answers) == [("sig", "format")]


# --- name helpers ----------------------------------------------------------------------


def test_the_name_helpers():
    assert is_signature_name("Ada Lovelace") and not is_signature_name("") and not is_signature_name(" Ada")
    assert not is_signature_name(None) and not is_signature_name(7)
    assert normalised_name("  Ada ́ ") is not None
    assert normalised_name("   ") is None and normalised_name("a​b") is None
    assert is_plain_image_id("abc-1_2.png") and not is_plain_image_id("a/b") and not is_plain_image_id("..")


@pytest.mark.parametrize(
    "name",
    [
        "ㅤ",  # Hangul filler
        "ᅟᅠ",  # Hangul choseong / jungseong fillers
        "ﾠﾠ",  # halfwidth Hangul filler
        "⠀⠀⠀",  # blank braille pattern
        "Adaㅤ",  # a filler inside a name
        "-- .",  # punctuation only: no letter or digit
        "Ada",  # private use (Co)
        "Ada͸",  # unassigned (Cn)
        "x́́́́́",  # five combining marks in a row
    ],
)
def test_a_name_draws_something_and_holds_a_letter_or_digit(name):
    assert not is_signature_name(name)
    assert normalised_name(name) is None


@pytest.mark.parametrize(
    "name", ["Zoë", "李小龍", "7", "O'Brien-Smith", "x́́́́"]
)
def test_ordinary_names_still_pass(name):
    import unicodedata

    assert normalised_name(name) == unicodedata.normalize("NFC", name)


# --- logic ------------------------------------------------------------------------------


def _condition(comparison, value=None):
    return {"field_id": "sig", "field_type": "signature", "comparison": comparison, "value": value}


def test_a_condition_on_a_signature_asks_only_signed_or_not():
    typed, drawn, empty = _typed("Ada"), _drawn(), {}
    assert evaluate_condition(typed, _condition("IS_NOT_EMPTY"))
    assert evaluate_condition(drawn, _condition("IS_NOT_EMPTY"))
    assert evaluate_condition(empty, _condition("IS_EMPTY"))
    assert not evaluate_condition(typed, _condition("IS_EMPTY"))
    # nothing else holds, whatever the value: the name never leaks into logic
    for comparison in ("IS_EQUAL", "IS_NOT_EQUAL", "CONTAINS", "STARTS_WITH", "GREATER_THAN"):
        assert not evaluate_condition(typed, _condition(comparison, "Ada"))
        assert not evaluate_condition(typed, _condition(comparison, "signed"))


def _spec(*fields, **extra):
    return {
        "specVersion": "1",
        "title": "Signed",
        "pages": [{"id": "page-1", "fields": list(fields)}],
        "endings": [{"title": "Thanks"}],
        **extra,
    }


def test_the_spec_check_refuses_other_comparisons_on_a_signature():
    from backend.app.services.form_spec.checks import check_spec_document

    def check(comparison):
        shown = {
            "id": "next",
            "type": "short_text",
            "title": "Next",
            "logic": {
                "action": "SHOW",
                "operator": "AND",
                "conditions": [{"fieldId": "sig", "comparison": comparison, "value": "x"}],
            },
        }
        return check_spec_document(_spec(SIGN, shown))

    assert check("IS_NOT_EMPTY")["valid"] and check("IS_EMPTY")["valid"]
    refused = check("IS_EQUAL")
    assert not refused["valid"]
    assert "IS_EMPTY, IS_NOT_EMPTY" in refused["errors"][0]["message"]


def test_a_signature_question_is_valid_in_a_spec_and_needs_no_settings():
    from backend.app.services.form_spec.checks import check_spec_document

    checked = check_spec_document(_spec({**SIGN, "validations": {"required": True}}))
    assert checked["valid"], checked["errors"]


# --- calculations, rules, groups, internal ---------------------------------------------


def test_a_formula_cannot_read_a_signature():
    calc = {"id": "calc", "type": "calculated", "title": "Calc", "properties": {"expression": {"var": "sig"}}}
    problems = calculated_field_problems(_form(SIGN, calc))
    assert [(p.field_id, p.path) for p in problems] == [("calc", "/var")]


def _rule(then, when=None):
    when = when or {"conditions": [{"fieldId": "name", "fieldType": "short_text", "comparison": "IS_NOT_EMPTY"}]}
    return {"rules": [{"id": "r1", "when": when, "then": then}]}


def test_a_rule_may_require_retitle_or_describe_a_signature_but_never_set_or_lock_it():
    ok = _form(NAME, {**SIGN, "properties": _rule({"required": True, "title": "Sign for the whole household", "description": "Read the terms first"})})
    assert field_rule_problems(ok) == []
    for then in ({"readOnly": True}, {"setValue": {"const": "Ada"}}):
        locked = _form(NAME, {**SIGN, "properties": _rule(then)})
        assert field_rule_problems(locked), then


def test_a_rule_can_depend_on_whether_a_question_is_signed_but_not_on_a_formula_of_it():
    reads = _form(SIGN, {"id": "later", "type": "short_text", "title": "Later", "properties": _rule({"required": True}, {"conditions": [{"fieldId": "sig", "fieldType": "signature", "comparison": "IS_NOT_EMPTY"}]})})
    assert field_rule_problems(reads) == []


def test_a_signature_cannot_be_inside_a_repeating_group_or_internal():
    group = {
        "id": "people",
        "type": "group",
        "title": "People",
        "properties": {"repeat": {"minItems": 1, "maxItems": 3}, "fields": [{"id": "sig", "type": "signature", "title": "Sign"}]},
    }
    with pytest.raises(HTTPException) as refused:
        _form(group)
    assert refused.value.status_code == 422
    from backend.app.services.internal_fields import INTERNAL_CAPABLE_TYPES

    assert "signature" not in INTERNAL_CAPABLE_TYPES


# --- what leaves the system -------------------------------------------------------------


def test_the_export_cell_is_the_typed_name_or_a_marker_never_the_image_or_a_link():
    field = {"id": "sig", "type": "signature", "title": "Sign"}
    typed = {"sig": {"signature": {"method": "typed", "name": "=cmd|' /C calc'!A0 Ada", "signed_at": "2026-01-01T00:00:00Z"}}}
    drawn = {"sig": {"signature": {"method": "drawn", "file_id": "img-1", "url": "https://files.example/x?signed"}}}
    assert answer_value(typed, field) == "=cmd|' /C calc'!A0 Ada"  # the writer's formula guard escapes it
    assert answer_value(drawn, field) == "[drawn signature]"
    assert answer_value({}, field) == ""
    assert answer_value({"sig": {"signature": {"method": "other"}}}, field) == ""


async def test_the_csv_guards_a_typed_name_that_looks_like_a_formula():
    import io

    from backend.app.services.response_export.table import ExportResponse, build_plan
    from backend.app.services.response_export.writer import BOM, RowCount, write_export

    form = {
        "form_id": "f",
        "builder_version": "v2",
        "title": "Signed",
        "fields": [{"id": "p1", "index": 0, "type": "slide", "properties": {"fields": [{"id": "sig", "index": 0, "type": "signature", "title": "Sign"}]}}],
    }

    async def source():
        for rid, signature in (
            ("r1", {"method": "typed", "name": "=1+1"}),
            ("r2", {"method": "drawn", "file_id": "img-1"}),
        ):
            yield ExportResponse(response_id=rid, responder="a@example.org", created_at=None, answers={"sig": {"signature": signature}}, internal_answers={}, hidden_fields={})

    out = b""
    async for piece in write_export(build_plan(form), "Signed", source, RowCount()):
        out += piece
    lines = out.decode("utf-8").removeprefix(BOM).split("\r\n")
    assert lines[0].startswith("Responder ID,Sign,")
    assert lines[1].split(",")[1] == "'=1+1"
    assert lines[2].split(",")[1] == "[drawn signature]"


def test_the_ai_insights_never_see_the_name_or_the_image():
    answer = {"type": "signature", "signature": {"method": "typed", "name": "Ada Lovelace"}}
    assert _answer_text(answer, {}) == "[signed]"


def test_a_signature_is_not_a_webhook_registration_or_email_variable():
    form = _form(SIGN, NAME)
    variables = body_builder.variables_of(form)
    assert variables["sig"].supported is False
    assert variables["name"].supported is True
