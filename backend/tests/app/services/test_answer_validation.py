"""Server-side answer validation (services/answer_validation.py): the shared
cases with the webapp (docs/spec/answer-validation.cases.json), the JavaScript
twins, RE2 patterns, the service paths (submission, respondent edit), the
"log only" switch, and that no answer value reaches an error or a log."""

import json
import math
import time
from pathlib import Path

import pytest
from loguru import logger

from backend.app.container import container
from backend.app.controllers.workspace_forms import _parse_form_body
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services import answer_validation
from backend.app.services.answer_validation import (
    answer_ids,
    check_answers,
    compile_pattern,
    js_number,
    js_string,
    to_re2_syntax,
    validate_answers,
)
from tests.app.controllers.data import testUser

CASES_FILE = (
    Path(__file__).resolve().parents[4] / "docs/spec/answer-validation.cases.json"
)
CASES = json.loads(CASES_FILE.read_text("utf-8"))["cases"]


def _form(pages):
    return _parse_form_body(
        json.dumps({"title": "Answers", "builderVersion": "v2", "fields": pages})
    )


def _answers(answers):
    """Answers as the submit endpoint parses them."""
    return StandardFormResponseCamelModel(answers=answers).answers


def _key(problem):
    return (problem["fieldId"], problem["rule"], problem.get("item"))


def _problems(pages, answers, **kwargs):
    form = _form(pages)
    found = validate_answers(
        form, _answers(answers), known_ids=answer_ids(form), **kwargs
    )
    return sorted((_key(p.as_json()) for p in found), key=str)


# ---------------------------------------------------------------------------
# Shared cases
# ---------------------------------------------------------------------------


def test_the_shared_cases_are_uniquely_named():
    names = [case["name"] for case in CASES]
    assert len(names) >= 60
    assert len(set(names)) == len(names)


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_shared_case(case):
    expected = sorted((_key(e) for e in case["errors"]), key=str)
    assert _problems(case["form"], case["answers"]) == expected


# ---------------------------------------------------------------------------
# JavaScript twins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        (1, "1"),
        (-4, "-4"),
        (1.5, "1.5"),
        (2.0, "2"),
        (0.1 + 0.2, "0.30000000000000004"),
        (1e21, "1e+21"),
        (123456789012345680000.0, "123456789012345680000"),
        (1e-7, "1e-7"),
        (0.000001, "0.000001"),
        (1.5e-10, "1.5e-10"),
        (-0.0, "0"),
        (True, "true"),
        ("12", "12"),
    ],
)
def test_js_string(value, expected):
    assert js_string(value) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("12", 12.0),
        (" 12 ", 12.0),
        ("", 0.0),
        ("1e3", 1000.0),
        (".5", 0.5),
        ("5.", 5.0),
        ("-1.25", -1.25),
        ("0x1F", 31.0),
        ("Infinity", math.inf),
        ("1_000", math.nan),
        ("nan", math.nan),
        ("inf", math.nan),
        ("12abc", math.nan),
        ("-0x1F", math.nan),
    ],
)
def test_js_number(text, expected):
    value = js_number(text)
    assert (math.isnan(value) and math.isnan(expected)) or value == expected


def test_javascript_escapes_are_rewritten_for_re2():
    assert to_re2_syntax("^caf\\u00e9$") == "^caf\\x{00e9}$"
    assert to_re2_syntax("\\u{1F600}") == "\\x{1F600}"
    # an escaped backslash followed by "u" stays as written
    assert to_re2_syntax("\\\\u0041") == "\\\\u0041"
    assert compile_pattern("^\\s$").search("\u00a0".encode())
    assert compile_pattern("^[\\s-]$").search("\u3000".encode())
    assert not compile_pattern("^\\S$").search("\u00a0".encode())


def test_the_pattern_cap_is_the_form_spec_cap():
    from common.form_spec.models import PATTERN_MAX_LENGTH, checked_pattern

    assert answer_validation.PATTERN_MAX_LENGTH == PATTERN_MAX_LENGTH == 200
    # what the spec accepts is enforced here, what it refuses is not
    assert compile_pattern(checked_pattern("a" * 200)) is not None
    with pytest.raises(ValueError):
        checked_pattern("a" * 201)
    assert compile_pattern("a" * 201) is None


def test_unsupported_patterns_are_not_compiled():
    assert compile_pattern("(?=a)b") is None
    assert compile_pattern("(a)\\1") is None
    assert compile_pattern("a" * 201) is None
    assert compile_pattern("a" * 200) is not None


def test_text_over_the_input_cap_never_matches_a_pattern():
    pages = [
        {
            "id": "p1",
            "type": "slide",
            "properties": {
                "fields": [
                    {"id": "q1", "type": "long_text", "validations": {"regex": "^a+$"}}
                ]
            },
        }
    ]
    assert _problems(pages, {"q1": {"type": "text", "text": "a" * 10_000}}) == []
    assert _problems(pages, {"q1": {"type": "text", "text": "a" * 10_001}}) == [
        ("q1", "pattern", None)
    ]


def test_an_unenforced_pattern_logs_the_field_id_only():
    answer_validation._note_unenforced.cache_clear()
    logged = []
    sink = logger.add(lambda message: logged.append(str(message)), level="DEBUG")
    try:
        pages = [
            {
                "id": "p1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": "q1",
                            "type": "short_text",
                            "validations": {"regex": "^(?=SECRETPATTERN)"},
                        }
                    ]
                },
            }
        ]
        _problems(pages, {"q1": {"type": "text", "text": "private answer"}})
    finally:
        logger.remove(sink)
    text = "".join(logged)
    assert "q1" in text
    assert "SECRETPATTERN" not in text and "private answer" not in text


def test_forms_without_pages_are_not_validated():
    from common.models.standard_form import StandardForm

    flat = StandardForm(
        fields=[{"id": "q1", "type": "short_text", "validations": {"required": True}}]
    )
    assert validate_answers(flat, {"x": {"text": "1"}}, known_ids=set()) == []


def test_an_edit_reports_only_what_it_changes():
    pages = [
        {
            "id": "p1",
            "type": "slide",
            "properties": {
                "fields": [
                    {
                        "id": "q1",
                        "type": "short_text",
                        "validations": {"required": True},
                    },
                    {"id": "q2", "type": "short_text", "validations": {"minLength": 3}},
                ]
            },
        }
    ]
    answers = {"q2": {"type": "text", "text": "ab"}}
    assert _problems(pages, answers, only=["q2"]) == [("q2", "too_short", None)]
    assert _problems(pages, answers, only=["q1"]) == [("q1", "required", None)]
    assert _problems(pages, answers, only=[]) == []


# ---------------------------------------------------------------------------
# check_answers: 422 shape, log only, nothing of the answers in logs or errors
# ---------------------------------------------------------------------------

SECRET = "Secret-Answer-4711"
RULED = [
    {
        "id": "p1",
        "type": "slide",
        "properties": {
            "fields": [
                {"id": "name", "type": "short_text", "validations": {"required": True}},
                {
                    "id": "code",
                    "type": "short_text",
                    "validations": {"maxLength": 4, "regex": "^[0-9]+$"},
                },
            ]
        },
    }
]


def _capture():
    logged = []
    sink = logger.add(lambda message: logged.append(str(message)), level="DEBUG")
    return logged, sink


def test_problems_answer_422_with_ids_and_rule_codes_only():
    form = _form(RULED)
    logged, sink = _capture()
    try:
        with pytest.raises(HTTPException) as error:
            check_answers(
                form,
                _answers({"code": {"type": "text", "text": SECRET}}),
                "form-1",
                known_ids=answer_ids(form),
                enforce=True,
            )
    finally:
        logger.remove(sink)
    assert error.value.status_code == 422
    content = error.value.content
    assert content["code"] == "invalid_answers"
    assert sorted(content["errors"], key=str) == sorted(
        [
            {"fieldId": "name", "rule": "required"},
            {"fieldId": "code", "rule": "too_long"},
            {"fieldId": "code", "rule": "pattern"},
        ],
        key=str,
    )
    assert SECRET not in json.dumps(content)
    text = "".join(logged)
    assert "form-1" in text and "3 answer problem" in text
    assert SECRET not in text


def test_log_only_mode_stores_and_logs_counts_and_codes():
    form = _form(RULED)
    logged, sink = _capture()
    try:
        check_answers(
            form,
            _answers({"code": {"type": "text", "text": SECRET}}),
            "form-2",
            enforce=False,
        )
    finally:
        logger.remove(sink)
    text = "".join(logged)
    assert "form-2" in text and "log only" in text
    assert "pattern" in text and "required" in text and "too_long" in text
    assert SECRET not in text


def test_the_setting_decides_by_default(monkeypatch):
    from backend.config import settings

    form = _form(RULED)
    monkeypatch.setattr(settings, "RESPONSE_VALIDATION_ENFORCE", False)
    check_answers(form, {}, "form-3")
    monkeypatch.setattr(settings, "RESPONSE_VALIDATION_ENFORCE", True)
    with pytest.raises(HTTPException):
        check_answers(form, {}, "form-3")


def test_the_switch_defaults_to_enforce():
    from backend.config.application import Application

    assert Application.model_fields["RESPONSE_VALIDATION_ENFORCE"].default is True


# ---------------------------------------------------------------------------
# Performance: linear in fields and answers
# ---------------------------------------------------------------------------


def test_a_2000_field_form_with_big_answers_validates_quickly():
    pages = []
    answers = {}
    for p in range(100):
        fields = []
        for i in range(20):
            fid = f"f{p}_{i}"
            kind = i % 4
            if kind == 0:
                fields.append(
                    {
                        "id": fid,
                        "type": "long_text",
                        "validations": {
                            "required": True,
                            "maxLength": 20_000,
                            "regex": "^[\\p{L} .,'-]+$",
                        },
                    }
                )
                answers[fid] = {"type": "text", "text": "word " * 1_900}
            elif kind == 1:
                fields.append(
                    {
                        "id": fid,
                        "type": "number",
                        "validations": {"minValue": 0, "regex": "^-?\\d+$"},
                        "properties": {
                            "logic": {
                                "action": "SHOW",
                                "operator": "AND",
                                "conditions": [
                                    {
                                        "fieldId": f"f{p}_{i - 1}",
                                        "fieldType": "long_text",
                                        "comparison": "IS_NOT_EMPTY",
                                    }
                                ],
                            }
                        },
                    }
                )
                answers[fid] = {"type": "number", "number": 42}
            elif kind == 2:
                fields.append(
                    {
                        "id": fid,
                        "type": "multiple_choice",
                        "validations": {"minChoices": 1, "maxChoices": 3},
                        "properties": {
                            "allowMultipleSelection": True,
                            "choices": [{"id": f"{fid}c{c}"} for c in range(8)],
                        },
                    }
                )
                answers[fid] = {
                    "type": "choices",
                    "choices": {"values": [f"{fid}c0", f"{fid}c1"]},
                }
            else:
                fields.append({"id": fid, "type": "yes_no"})
                answers[fid] = {"type": "boolean", "boolean": True}
        jumps = [
            {
                "operator": "AND",
                "conditions": [
                    {
                        "fieldId": f"f{p}_3",
                        "fieldType": "yes_no",
                        "comparison": "IS_EQUAL",
                        "value": "No",
                    }
                ],
                "target": "__SUBMIT__",
            }
        ]
        pages.append(
            {
                "id": f"p{p}",
                "type": "slide",
                "properties": {"fields": fields, "jumps": jumps},
            }
        )
    form = _form(pages)
    parsed = _answers(answers)
    known = answer_ids(form)
    validate_answers(form, parsed, known_ids=known)  # warm the pattern cache
    runs = []
    for _ in range(3):
        start = time.perf_counter()
        problems = validate_answers(form, parsed, known_ids=known)
        runs.append(time.perf_counter() - start)
    assert problems == []
    assert min(runs) < 0.1, f"{min(runs) * 1000:.0f} ms"


# ---------------------------------------------------------------------------
# Service paths: submission and respondent edit
# ---------------------------------------------------------------------------


async def _published(workspace, pages):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form(pages), testUser)
    await service.publish_form(workspace.id, form.form_id, testUser)
    return form


async def _submit(workspace, form, answers):
    return await container.workspace_form_service().submit_response(
        workspace.id,
        form.form_id,
        StandardFormResponseCamelModel(answers=answers),
        testUser,
    )


@pytest.mark.asyncio
async def test_submission_with_problems_is_422(workspace):
    form = await _published(workspace, RULED)
    with pytest.raises(HTTPException) as error:
        await _submit(workspace, form, {"code": {"type": "text", "text": SECRET}})
    assert error.value.status_code == 422
    assert error.value.content["code"] == "invalid_answers"
    assert SECRET not in json.dumps(error.value.content)


@pytest.mark.asyncio
async def test_valid_submission_is_stored(workspace):
    form = await _published(workspace, RULED)
    response = await _submit(
        workspace,
        form,
        {
            "name": {"type": "text", "text": "Ann"},
            "code": {"type": "text", "text": "12"},
        },
    )
    assert response.response_id


@pytest.mark.asyncio
async def test_submission_with_an_unknown_id_is_422(workspace):
    form = await _published(workspace, RULED)
    with pytest.raises(HTTPException) as error:
        await _submit(
            workspace,
            form,
            {"name": {"type": "text", "text": "Ann"}, "x": {"text": "1"}},
        )
    assert error.value.content["errors"] == [{"fieldId": "x", "rule": "unknown_field"}]


@pytest.mark.asyncio
async def test_submission_may_answer_a_question_of_the_draft(workspace):
    """A question added to the draft after publishing is not unknown (the
    respondent may have been served the draft's ids)."""
    form = await _published(workspace, RULED)
    service = container.workspace_form_service()
    draft = _form(
        [
            {
                **RULED[0],
                "properties": {
                    "fields": RULED[0]["properties"]["fields"]
                    + [{"id": "later", "type": "short_text"}]
                },
            }
        ]
    )
    await service.update_form(workspace.id, form.form_id, draft, testUser)
    response = await _submit(
        workspace,
        form,
        {
            "name": {"type": "text", "text": "Ann"},
            "later": {"type": "text", "text": "x"},
        },
    )
    assert response.response_id


@pytest.mark.asyncio
async def test_internal_answers_in_a_submission_are_dropped_not_refused(workspace):
    pages = [
        {
            "id": "p1",
            "type": "slide",
            "properties": {
                "fields": [
                    {"id": "q1", "type": "short_text"},
                    {
                        "id": "office",
                        "type": "short_text",
                        "internal": True,
                        "validations": {"required": True},
                    },
                ]
            },
        }
    ]
    form = await _published(workspace, pages)
    response = await _submit(
        workspace, form, {"office": {"type": "text", "text": "staff only"}}
    )
    assert "office" not in (response.answers or {})


@pytest.mark.asyncio
async def test_submission_in_log_only_mode_is_stored(workspace, monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "RESPONSE_VALIDATION_ENFORCE", False)
    form = await _published(workspace, RULED)
    logged, sink = _capture()
    try:
        response = await _submit(
            workspace, form, {"code": {"type": "text", "text": SECRET}}
        )
    finally:
        logger.remove(sink)
    assert response.response_id
    text = "".join(logged)
    assert str(form.form_id) in text and "log only" in text
    assert SECRET not in text


@pytest.mark.asyncio
async def test_response_edit_is_checked_for_what_it_changes(workspace):
    form = await _published(workspace, RULED)
    workspace_form = (
        await container.workspace_form_repo().get_workspace_form_in_workspace(
            workspace_id=workspace.id, query=str(form.form_id)
        )
    )
    workspace_form.settings.require_verified_identity = True
    workspace_form.settings.allow_editing_response = True
    await container.workspace_form_repo().save(workspace_form)
    submitted = await _submit(
        workspace, form, {"name": {"type": "text", "text": "Ann"}}
    )
    service = container.workspace_form_service()

    async def edit(answers):
        return await service.patch_response(
            workspace.id,
            form.form_id,
            submitted.response_id,
            None,
            StandardFormResponseCamelModel(answers=answers),
            testUser,
        )

    with pytest.raises(HTTPException) as error:
        await edit({"code": {"type": "text", "text": "12345"}})
    assert error.value.content["errors"] == [{"fieldId": "code", "rule": "too_long"}]
    with pytest.raises(HTTPException) as error:
        await edit({"name": {"type": "text", "text": ""}})
    assert error.value.content["errors"] == [{"fieldId": "name", "rule": "required"}]
    with pytest.raises(HTTPException) as error:
        await edit({"code": {"type": "number", "number": 12}})
    assert error.value.content["errors"] == [{"fieldId": "code", "rule": "type"}]
    assert await edit({"code": {"type": "text", "text": "1234"}})


@pytest.mark.asyncio
async def test_the_endpoint_answers_422_with_codes_and_no_values(client, workspace):
    form = await _published(workspace, RULED)
    body = {"answers": {"code": {"type": "text", "text": SECRET}}}
    refused = await client.post(
        f"/api/v1/workspaces/{workspace.id}/forms/{form.form_id}/response",
        data={"response": json.dumps(body)},
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "invalid_answers"
    assert {"fieldId": "name", "rule": "required"} in refused.json()["errors"]
    assert SECRET not in refused.text
