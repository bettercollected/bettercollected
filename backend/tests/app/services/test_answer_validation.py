"""Server-side answer validation (services/answer_validation.py): the shared
cases with the webapp (docs/spec/answer-validation.cases.json), the JavaScript
twins, RE2 patterns, the service paths (submission, respondent edit), the
"log only" switch, and that no answer value reaches an error or a log."""

import json
import math
import time
import types
from pathlib import Path

import pytest
import re2
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


def test_text_over_the_input_cap_is_left_to_the_browser():
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
    assert _problems(pages, {"q1": {"type": "text", "text": "b" * 10_000}}) == [
        ("q1", "pattern", None)
    ]
    # over the cap: not matched here (the browser matches it)
    assert _problems(pages, {"q1": {"type": "text", "text": "b" * 10_001}}) == []


def test_an_unenforced_pattern_logs_the_field_id_only():
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


def test_a_2000_field_form_with_big_answers_validates_quickly(monkeypatch):
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
    compiled = _spy_compiles(monkeypatch)
    start = time.perf_counter()
    problems = validate_answers(form, parsed, known_ids=known)
    elapsed = time.perf_counter() - start
    assert problems == []
    # the form's two patterns come from the cache: nothing is compiled again
    assert compiled == []
    # smoke check only, far above the expected time (shared CI runners vary)
    assert elapsed < 5, f"{elapsed:.1f} s"


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


# ---------------------------------------------------------------------------
# Pattern cost: compile memory, per-response budget, cache bounds
# ---------------------------------------------------------------------------

PRESETS = [
    "^[1-9][0-9]{3} ?[A-Za-z]{2}$",
    "^[A-Za-z]{2}[0-9]{2}(?: ?[A-Za-z0-9]){11,30}$",
    "^\\+?[0-9][0-9 ()-]{5,19}$",
    "^[\\p{L} '-]+$",
    "^-?\\d+$",
]


def _pattern_pages(patterns):
    fields = [
        {"id": f"q{i}", "type": "short_text", "validations": {"regex": pattern}}
        for i, pattern in enumerate(patterns)
    ]
    return [{"id": "p1", "type": "slide", "properties": {"fields": fields}}]


def _spy_compiles(monkeypatch):
    """Record every pattern compiled for RE2 (cache misses only)."""
    compiled = []
    real = answer_validation._compile
    monkeypatch.setattr(
        answer_validation,
        "_compile",
        lambda pattern: compiled.append(pattern) or real(pattern),
    )
    return compiled


def _fake_clock(monkeypatch, tick=0.0):
    """Replace the clock the module reads: each reading moves it ``tick``
    seconds forward, so every timed compile or match costs exactly ``tick``
    (0: time stands still and only the compile budget acts)."""
    now = [0.0]

    def perf_counter():
        now[0] += tick
        return now[0]

    monkeypatch.setattr(
        answer_validation, "time", types.SimpleNamespace(perf_counter=perf_counter)
    )


HEAVY = "^\\p{L}{0,300}$"


def test_presets_compile_within_the_memory_and_program_limits():
    answer_validation._CACHE.clear()
    for pattern in PRESETS:
        compiled = compile_pattern(pattern)
        assert compiled is not None
        assert compiled.programsize <= answer_validation.PATTERN_MAX_PROGRAM


def test_a_heavy_pattern_is_refused_by_the_memory_limit_and_not_checked():
    source = answer_validation.to_re2_syntax(HEAVY).encode("utf-8")
    # RE2 compiles it without a memory limit; the module's options refuse it
    unlimited = re2.Options()
    unlimited.log_errors = False
    unlimited.never_capture = True
    assert re2.compile(source, unlimited).programsize > 0
    assert answer_validation._RE2_OPTIONS.max_mem == answer_validation.PATTERN_MAX_MEM
    with pytest.raises(re2.error):
        re2.compile(source, answer_validation._RE2_OPTIONS)
    answer_validation._CACHE.clear()
    assert compile_pattern(HEAVY) is None
    pages = _pattern_pages([HEAVY])
    assert _problems(pages, {"q0": {"type": "text", "text": "123"}}) == []


def _heavy_patterns(count):
    return [f"^\\p{{L}}{{0,{300 + i}}}$" for i in range(count)]


def test_many_distinct_heavy_patterns_compile_at_most_the_budget(monkeypatch):
    answer_validation._CACHE.clear()
    _fake_clock(monkeypatch)
    compiled = _spy_compiles(monkeypatch)
    patterns = _heavy_patterns(600)
    pages = _pattern_pages(patterns)
    answers = {f"q{i}": {"type": "text", "text": SECRET} for i in range(600)}
    logged, sink = _capture()
    try:
        assert _problems(pages, answers) == []
    finally:
        logger.remove(sink)
    assert len(compiled) == answer_validation.PATTERN_COMPILES_PER_RESPONSE == 50
    assert compiled == patterns[:50]
    # every field is unchecked (50 unusable, 550 past the budget); only the
    # field ids are logged, never a pattern or an answer
    text = "".join(logged)
    assert "600 field(s) not checked" in text and "q599" in text
    assert "p{L}" not in text and SECRET not in text


def test_many_distinct_heavy_patterns_smoke(monkeypatch):
    """Real clock: whichever budget acts first, a response compiles at most
    the compile budget. The time bound is a generous smoke check only."""
    answer_validation._CACHE.clear()
    compiled = _spy_compiles(monkeypatch)
    pages = _pattern_pages(_heavy_patterns(600))
    answers = {f"q{i}": {"type": "text", "text": "abc"} for i in range(600)}
    start = time.perf_counter()
    assert _problems(pages, answers) == []
    elapsed = time.perf_counter() - start
    assert 1 <= len(compiled) <= answer_validation.PATTERN_COMPILES_PER_RESPONSE
    assert elapsed < 5, f"{elapsed:.1f} s"


def test_the_compile_budget_is_respected(monkeypatch):
    answer_validation._CACHE.clear()
    _fake_clock(monkeypatch)
    compiled = _spy_compiles(monkeypatch)
    patterns = [f"^[0-9]{{{i}}}$" for i in range(1, 121)]
    pages = _pattern_pages(patterns)
    answers = {f"q{i}": {"type": "text", "text": "x"} for i in range(120)}
    logged, sink = _capture()
    try:
        first = _problems(pages, answers)
    finally:
        logger.remove(sink)
    assert len(compiled) == answer_validation.PATTERN_COMPILES_PER_RESPONSE == 50
    assert len(first) == 50  # the 50 compiled patterns are enforced
    text = "".join(logged)
    assert "70 field(s) not checked" in text and "q119" in text
    # the next response finds those in the cache and compiles 50 more
    assert len(_problems(pages, answers)) == 100
    assert len(compiled) == 100


def test_the_time_budget_stops_pattern_checks():
    form = _form(_pattern_pages(["^[0-9]+$"]))
    field = form.fields[0].properties.fields[0]
    answer = {"type": "text", "text": "x"}
    assert answer_validation.answer_rule_problems(field, answer) == ["pattern"]
    spent = answer_validation.PatternBudget(seconds=0.0)
    assert answer_validation.answer_rule_problems(field, answer, spent) == []
    assert spent.unchecked == {"q0"}


def test_the_time_budget_skips_the_remaining_patterns(monkeypatch):
    # each compile and each match costs 0.1 s on the fake clock. Budget
    # 0.25 s: q0 is compiled and matched (0.2 s), q1 compiled (0.3 s) but
    # not matched, q2 to q9 neither compiled nor matched
    assert answer_validation.PATTERN_SECONDS_PER_RESPONSE == 0.25
    answer_validation._CACHE.clear()
    _fake_clock(monkeypatch, tick=0.1)
    compiled = _spy_compiles(monkeypatch)
    patterns = [f"^SECRETPATTERN{i}[0-9]+$" for i in range(10)]
    pages = _pattern_pages(patterns)
    answers = {f"q{i}": {"type": "text", "text": SECRET} for i in range(10)}
    logged, sink = _capture()
    try:
        problems = _problems(pages, answers)
    finally:
        logger.remove(sink)
    assert problems == [("q0", "pattern", None)]
    assert compiled == patterns[:2]
    text = "".join(logged)
    assert "9 field(s) not checked" in text
    assert "q1," in text and "q9" in text
    assert "SECRETPATTERN" not in text and SECRET not in text


def test_presets_are_still_enforced(monkeypatch):
    answer_validation._CACHE.clear()
    _fake_clock(monkeypatch)
    pages = _pattern_pages(PRESETS)
    answers = {f"q{i}": {"type": "text", "text": "!"} for i in range(len(PRESETS))}
    assert len(_problems(pages, answers)) == len(PRESETS)


def test_the_cache_is_bounded_by_entries_and_program_size():
    cache = answer_validation._PatternCache(entries=3, program=100)
    for name in "abcd":
        cache.put(name, name, 10)
    assert cache.get("a") is None and cache.get("d") == "d"
    cache.put("big", "big", 95)
    assert cache.get("big") == "big"
    assert cache.get("b") is None and cache.get("c") is None


def test_a_program_over_the_size_cap_is_not_checked():
    answer_validation._CACHE.clear()
    assert compile_pattern("^.{0,1000}$") is None  # program of about 9000
    assert compile_pattern("^.{0,100}$") is not None


# ---------------------------------------------------------------------------
# Huge numbers behave like JavaScript's Infinity, never a server error
# ---------------------------------------------------------------------------


def test_huge_numbers_are_infinity():
    huge = 10**400
    assert answer_validation.to_float(huge) == math.inf
    assert answer_validation.to_float(-huge) == -math.inf
    assert js_string(huge) == "Infinity"
    assert js_number("0x" + "f" * 300) == math.inf


def test_a_huge_number_answer_is_a_type_problem_not_an_error():
    pages = [
        {
            "id": "p1",
            "type": "slide",
            "properties": {
                "fields": [
                    {"id": "n", "type": "number", "validations": {"maxValue": 10}},
                    {
                        "id": "q",
                        "type": "short_text",
                        "validations": {"required": True},
                        "properties": {
                            "logic": {
                                "action": "SHOW",
                                "operator": "AND",
                                "conditions": [
                                    {
                                        "fieldId": "n",
                                        "fieldType": "number",
                                        "comparison": "GREATER_THAN",
                                        "value": "5",
                                    }
                                ],
                            }
                        },
                    },
                ]
            },
        }
    ]
    problems = _problems(pages, {"n": {"type": "number", "number": 10**400}})
    # Infinity is not a number answer; it is still greater than 5
    assert problems == sorted([("n", "type", None), ("q", "required", None)], key=str)
