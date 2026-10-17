"""Answer validation: server-side checks of submitted answers.

The respondent form checks answers in the browser (webapp
``utils/vvalidation-utils.ts`` ``validateSlide`` for Required,
``utils/answer-rules.ts`` for the answer rules, ``utils/conditional-logic.ts``
for visibility and page jumps). Anyone can POST a response directly, so the
same checks run here on every path that stores respondent answers (the
submission and the respondent's edit of it). Shared cases with the webapp:
``docs/spec/answer-validation.cases.json``.

- **Which questions count:** the pages the respondent goes through, replayed
  from the first page with the submitted answers and the same jump resolution
  as the form (the first matching jump wins; a jump to a page that no longer
  exists falls through to the next page). On those pages, questions hidden by
  their visibility rule, internal (staff-only) questions and content blocks
  are left out. Hidden fields (URL parameters) are not questions.
- **Required:** a counted required question needs an answer with a value. A
  required matrix needs every row answered. In a repeating group, every
  displayed item (at least the group's minimum) is checked like the form does.
- **Answer rules,** only on a counted question that has an answer: length and
  format (pattern) on short and long text, lowest/highest value and pattern on
  numbers, number of options on multiple choice with multiple selection.
  Patterns are matched with RE2 (linear time). A pattern RE2 cannot compile
  (lookarounds, backreferences), or longer than ``PATTERN_MAX_LENGTH``, is not
  enforced here; only the field id is logged. Text longer than
  ``PATTERN_INPUT_MAX_LENGTH`` never matches a pattern.
- **Types,** for every answer whatever its page: the value must sit in the
  slot of the question's type and have its type (a number for a number
  question, the ids of existing options for a choice question). Answers to
  ids that are not questions of the form are refused.

Problems carry a field id and a rule code, never a value. ``check_answers``
raises 422 ``{"code": "invalid_answers", "errors": [{"fieldId", "rule"}]}``,
or only logs when ``RESPONSE_VALIDATION_ENFORCE`` is off. Validation is
linear in the number of fields and answers.
"""

import functools
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Optional, Set

import re2
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.repeating_groups import (
    evaluate_conditions,
    group_items,
    has_answer_value,
    is_hidden_by_logic,
)

# Rule codes (the webapp's AnswerRuleProblem / Invalidations, lower case).
REQUIRED = "required"
TOO_SHORT = "too_short"
TOO_LONG = "too_long"
PATTERN = "pattern"
TOO_SMALL = "too_small"
TOO_LARGE = "too_large"
NOT_INTEGER = "not_integer"
TOO_FEW_CHOICES = "too_few_choices"
TOO_MANY_CHOICES = "too_many_choices"
TYPE = "type"
CHOICE = "choice"
UNKNOWN_FIELD = "unknown_field"

ERROR_CODE = "invalid_answers"
ERROR_MESSAGE = "Some answers are missing or not valid."

# "Whole numbers only" on a number question (webapp INTEGER_PATTERN).
INTEGER_PATTERN = r"^-?\d+$"
# Patterns longer than this are not enforced on the server.
PATTERN_MAX_LENGTH = 200
# A pattern is never matched against more characters than this.
PATTERN_INPUT_MAX_LENGTH = 10_000
JUMP_TARGET_SUBMIT = "__SUBMIT__"

SLIDE = "slide"
GROUP = "group"
MATRIX = "matrix"
MULTIPLE_CHOICE = "multiple_choice"
DROPDOWN = "dropdown"
TEXT_TYPES = {"short_text", "long_text"}
NUMBER_TYPES = {"number", "rating", "linear_rating", "opinion_scale"}
# Field types that are content, not questions: never required.
NOT_QUESTIONS = {
    SLIDE,
    "text",
    "statement",
    "page_break",
    "hidden",
    "calculated",
    "conditional",
    "VIDEO_CONTENT",
    "IMAGE_CONTENT",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "p",
    "strong",
    "divider",
    "markdown",
}
# Field type -> the answer slots its value may use. Types not listed here
# (matrix, payment, ranking, ...) are not type-checked.
VALUE_SLOTS = {
    "short_text": {"text"},
    "long_text": {"text"},
    "email": {"email", "text"},
    "url": {"url", "text"},
    "phone_number": {"phone_number"},
    "date": {"date"},
    "yes_no": {"boolean"},
    "file_upload": {"file_metadata", "file_url"},
    "tabular_input": {"tabular_value"},
    **{number_type: {"number"} for number_type in NUMBER_TYPES},
}
STRING_SLOTS = {"text", "email", "url", "phone_number", "date"}
_NOT_VALUE_KEYS = {"field", "type"}

# JavaScript's whitespace (String.prototype.trim, Number()).
_JS_WHITESPACE = (
    "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006"
    "\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)
_JS_SPACE_CLASS = (
    r"\s\x{a0}\x{1680}\x{2000}-\x{200a}\x{2028}\x{2029}\x{202f}\x{205f}"
    r"\x{3000}\x{feff}"
)
_JS_DECIMAL = re.compile(r"[+-]?(?:Infinity|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")
_JS_RADIX = {"x": 16, "o": 8, "b": 2}


@dataclass(frozen=True)
class AnswerProblem:
    """One broken rule: the question's id, the rule code and, inside a
    repeating group, the item's position (from 0). ``key`` is the answers key
    the problem belongs to (the group's id for an item's question)."""

    field_id: str
    rule: str
    item: Optional[int] = None
    key: Optional[str] = None

    def as_json(self) -> Dict[str, Any]:
        problem: Dict[str, Any] = {"fieldId": self.field_id, "rule": self.rule}
        if self.item is not None:
            problem["item"] = self.item
        return problem


# ---------------------------------------------------------------------------
# JavaScript twins (the respondent form's semantics)
# ---------------------------------------------------------------------------


def js_trim(text: str) -> str:
    return text.strip(_JS_WHITESPACE)


def js_number(text: str) -> float:
    """``Number(text)`` for a string: NaN when JavaScript gives NaN."""
    text = js_trim(text)
    if text == "":
        return 0.0
    if _JS_DECIMAL.fullmatch(text):
        return float(text.replace("Infinity", "inf"))
    if len(text) > 2 and text[0] == "0" and text[1].lower() in _JS_RADIX:
        if not text[2:].isalnum() or not text[2:].isascii():
            return math.nan
        try:
            return float(int(text[2:], _JS_RADIX[text[1].lower()]))
        except ValueError:
            return math.nan
    return math.nan


def js_string(value: Any) -> str:
    """``String(value)`` for the JSON values an answer can hold."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value) if abs(value) < 10**21 else _js_float(float(value))
    if isinstance(value, float):
        return _js_float(value)
    return value if isinstance(value, str) else str(value)


def _js_float(value: float) -> str:
    """Number.prototype.toString() of a float (shortest round-trip digits)."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Infinity" if value > 0 else "-Infinity"
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    _, digit_tuple, exponent = Decimal(repr(abs(value))).as_tuple()
    digits = "".join(map(str, digit_tuple))
    # where the decimal point sits relative to the first digit
    point = len(digits) + exponent
    stripped = digits.lstrip("0")
    point -= len(digits) - len(stripped)
    digits = stripped.rstrip("0")
    size = len(digits)
    if size <= point <= 21:
        text = digits + "0" * (point - size)
    elif 0 < point <= 21:
        text = digits[:point] + "." + digits[point:]
    elif -6 < point <= 0:
        text = "0." + "0" * (-point) + digits
    else:
        power = point - 1
        text = digits[0] + ("." + digits[1:] if size > 1 else "")
        text += ("e+" if power >= 0 else "e-") + str(abs(power))
    return sign + text


def _is_set(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def to_re2_syntax(pattern: str) -> str:
    """Rewrite the JavaScript-only bits of a pattern RE2 reads differently:
    ``\\uXXXX`` / ``\\u{...}`` escapes, and ``\\s`` (Unicode spaces in
    JavaScript, ASCII in RE2). Everything else is passed on as written."""
    out: List[str] = []
    in_class = False
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\" and i + 1 < len(pattern):
            escaped = pattern[i + 1]
            if escaped == "u":
                if pattern.startswith("{", i + 2) and "}" in pattern[i + 3 :]:
                    end = pattern.index("}", i + 3)
                    out.append(r"\x{" + pattern[i + 3 : end] + "}")
                    i = end + 1
                    continue
                code = pattern[i + 2 : i + 6]
                if len(code) == 4 and all(c in "0123456789abcdefABCDEF" for c in code):
                    out.append(r"\x{" + code + "}")
                    i += 6
                    continue
            if escaped == "s":
                out.append(_JS_SPACE_CLASS if in_class else f"[{_JS_SPACE_CLASS}]")
            elif escaped == "S" and not in_class:
                out.append(f"[^{_JS_SPACE_CLASS}]")
            else:
                out.append(pattern[i : i + 2])
            i += 2
            continue
        if char == "[" and not in_class:
            in_class = True
        elif char == "]" and in_class:
            in_class = False
        out.append(char)
        i += 1
    return "".join(out)


_RE2_OPTIONS = re2.Options()
# RE2 would print the pattern to stderr when it does not compile.
_RE2_OPTIONS.log_errors = False
_RE2_OPTIONS.never_capture = True


@functools.lru_cache(maxsize=512)
def compile_pattern(pattern: str) -> Optional[Any]:
    """The pattern compiled for RE2, or None when it is not enforced here
    (too long, or a construct RE2 does not support)."""
    if not pattern or len(pattern) > PATTERN_MAX_LENGTH:
        return None
    try:
        # Compiled and matched as UTF-8 bytes: RE2 reads them as text all the
        # same, and the wrapper skips mapping byte offsets back to characters.
        return re2.compile(to_re2_syntax(pattern).encode("utf-8"), _RE2_OPTIONS)
    except Exception:  # re2.error and its subclasses
        return None


@functools.lru_cache(maxsize=1024)
def _note_unenforced(field_id: str, pattern: str) -> None:
    """Log once per field and pattern that a pattern is not enforced."""
    logger.info("Answer pattern of field {} is not enforced on the server.", field_id)


def _pattern_for(field_id: str, pattern: Optional[str]) -> Optional[Any]:
    if not pattern:
        return None
    compiled = compile_pattern(pattern)
    if compiled is None:
        _note_unenforced(field_id, pattern)
    return compiled


def _breaks_pattern(compiled: Any, subject: str) -> bool:
    if len(subject) > PATTERN_INPUT_MAX_LENGTH:
        return True
    return compiled.search(subject.encode("utf-8", "surrogatepass")) is None


# ---------------------------------------------------------------------------
# Form structure
# ---------------------------------------------------------------------------


def _type(field: Any) -> Optional[str]:
    field_type = getattr(field, "type", None)
    return getattr(field_type, "value", field_type)


def _props(field: Any) -> Any:
    return getattr(field, "properties", None)


def _children(field: Any) -> List[Any]:
    properties = _props(field)
    return list(getattr(properties, "fields", None) or []) if properties else []


def _rules(field: Any) -> Any:
    return getattr(field, "validations", None)


def _required(field: Any) -> bool:
    rules = _rules(field)
    return bool(rules and rules.required)


def is_repeating_group(field: Any) -> bool:
    properties = _props(field)
    return _type(field) == GROUP and getattr(properties, "repeat", None) is not None


def _slides(form: Any) -> Optional[List[Any]]:
    """The pages of a v2 form, or None for a form without pages (v1 and
    imported forms are not validated: their respondents use other checks)."""
    fields = list(getattr(form, "fields", None) or [])
    if not fields or any(_type(field) != SLIDE for field in fields):
        return None
    return fields


def answer_ids(*forms: Any) -> Set[str]:
    """Ids an answer may be keyed by: every question of the given forms
    (page questions, matrix rows, children of groups), pages excluded."""
    ids: Set[str] = set()

    def walk(fields: Iterable[Any]) -> None:
        for field in fields:
            if getattr(field, "id", None) and _type(field) != SLIDE:
                ids.add(str(field.id))
            walk(_children(field))

    for form in forms:
        if form is not None:
            walk(getattr(form, "fields", None) or [])
    return ids


def resolve_jump_target(slide: Any, answers: Dict[str, Any]) -> Optional[str]:
    """Twin of the webapp's ``resolveJumpTargetId``: the first jump whose
    conditions hold decides, even when its target is gone."""
    for jump in getattr(_props(slide), "jumps", None) or []:
        if jump.conditions and evaluate_conditions(
            jump.operator, jump.conditions, answers
        ):
            return jump.target or None
    return None


def visited_slides(slides: List[Any], answers: Dict[str, Any]) -> List[Any]:
    """The pages a respondent goes through with these answers, in order."""
    index_by_id = {str(slide.id): i for i, slide in enumerate(slides)}
    visited: List[Any] = []
    seen: Set[int] = set()
    index = 0
    for _ in range(2 * len(slides) + 2):
        if not 0 <= index < len(slides) or index in seen:
            break
        seen.add(index)
        slide = slides[index]
        visited.append(slide)
        target = resolve_jump_target(slide, answers)
        if target == JUMP_TARGET_SUBMIT:
            break
        index = index_by_id.get(target, index + 1) if target else index + 1
    return visited


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------


def _filled(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, (list, dict)):
        values = value.values() if isinstance(value, dict) else value
        return any(_filled(v) for v in values) if value else False
    return True


def _given_slots(answer: Dict[str, Any]) -> Set[str]:
    return {k for k, v in answer.items() if k not in _NOT_VALUE_KEYS and _filled(v)}


def _number_value(raw: Any) -> Optional[float]:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if math.isfinite(raw) else None
    if isinstance(raw, str):
        value = js_number(raw)
        return value if math.isfinite(value) else None
    return None


def type_problem(
    field: Any, answer: Any, matrix: Optional[Any] = None
) -> Optional[str]:
    """Does the answer's shape fit the question's type? A rule code when not.
    ``matrix``: the matrix a row belongs to (it decides multiple selection)."""
    if not isinstance(answer, dict):
        return TYPE
    field_type = _type(field)
    given = _given_slots(answer)
    if not given:
        return None
    if is_repeating_group(field):
        return None if given <= {"items"} else TYPE
    if "items" in given:
        return TYPE
    if matrix is not None:
        multiple = bool(getattr(_props(matrix), "allow_multiple_selection", None))
        return _choice_problem(field, answer, given, multiple, allow_other=False)
    if field_type in (MULTIPLE_CHOICE, DROPDOWN):
        properties = _props(field)
        multiple = field_type == MULTIPLE_CHOICE and bool(
            getattr(properties, "allow_multiple_selection", None)
        )
        allow_other = bool(getattr(properties, "allow_other_choice", None))
        return _choice_problem(field, answer, given, multiple, allow_other)
    slots = VALUE_SLOTS.get(field_type)
    if slots is None:
        return None
    if not given <= slots:
        return TYPE
    for slot in given:
        value = answer[slot]
        if slot in STRING_SLOTS and not isinstance(value, str):
            return TYPE
        if slot == "number" and _number_value(value) is None:
            return TYPE
        if slot == "boolean" and not isinstance(value, bool):
            return TYPE
        if slot in ("file_metadata",) and not isinstance(value, dict):
            return TYPE
    return None


def _choice_problem(
    field: Any,
    answer: Dict[str, Any],
    given: Set[str],
    multiple: bool,
    allow_other: bool,
) -> Optional[str]:
    properties = _props(field)
    slot = "choices" if multiple else "choice"
    if given != {slot} or not isinstance(answer[slot], dict):
        return TYPE
    value = answer[slot]
    if not set(value) <= {"value", "values", "other"}:
        return TYPE
    options = {
        str(choice.id)
        for choice in (getattr(properties, "choices", None) or [])
        if getattr(choice, "id", None)
    }
    other = value.get("other")
    if other is not None and not isinstance(other, str):
        return TYPE
    if other and not allow_other:
        return CHOICE
    if multiple:
        if value.get("value") not in (None, ""):
            return TYPE
        picked = value.get("values")
        if picked is None:
            return None
        if not isinstance(picked, list) or not all(isinstance(v, str) for v in picked):
            return TYPE
        return None if set(picked) <= options else CHOICE
    if value.get("values") not in (None, []):
        return TYPE
    picked = value.get("value")
    if picked in (None, ""):
        return None
    if not isinstance(picked, str):
        return TYPE
    return None if picked in options else CHOICE


def answer_rule_problems(field: Any, answer: Any) -> List[str]:
    """Twin of the webapp's ``checkAnswerRules``: the rules a given answer
    breaks (none for an empty answer: that is Required's to say)."""
    if not isinstance(answer, dict):
        return []
    rules = _rules(field)
    if rules is None:
        return []
    field_type = _type(field)
    field_id = str(getattr(field, "id", ""))
    problems: List[str] = []
    if field_type in TEXT_TYPES:
        text = answer.get("text")
        if not isinstance(text, str) or not text:
            return []
        length = len(text)
        if _is_set(rules.min_length) and length < rules.min_length:
            problems.append(TOO_SHORT)
        if _is_set(rules.max_length) and length > rules.max_length:
            problems.append(TOO_LONG)
        compiled = _pattern_for(field_id, rules.regex)
        if compiled is not None and _breaks_pattern(compiled, js_trim(text)):
            problems.append(PATTERN)
    elif field_type == "number":
        raw = answer.get("number")
        if raw is None or raw == "":
            return []
        typed = js_trim(js_string(raw))
        value = js_number(typed)
        if not math.isfinite(value):
            return []
        if _is_set(rules.min_value) and value < rules.min_value:
            problems.append(TOO_SMALL)
        if _is_set(rules.max_value) and value > rules.max_value:
            problems.append(TOO_LARGE)
        compiled = _pattern_for(field_id, rules.regex)
        if compiled is not None and _breaks_pattern(compiled, typed):
            problems.append(NOT_INTEGER if rules.regex == INTEGER_PATTERN else PATTERN)
    elif field_type == MULTIPLE_CHOICE and getattr(
        _props(field), "allow_multiple_selection", None
    ):
        choices = answer.get("choices")
        if not isinstance(choices, dict):
            return []
        values = choices.get("values")
        other = choices.get("other")
        count = (len(values) if isinstance(values, list) else 0) + (
            1 if isinstance(other, str) and js_trim(other) else 0
        )
        if count == 0:
            return []
        if _is_set(rules.min_choices) and count < rules.min_choices:
            problems.append(TOO_FEW_CHOICES)
        if _is_set(rules.max_choices) and count > rules.max_choices:
            problems.append(TOO_MANY_CHOICES)
    return problems


def _matrix_unanswered(field: Any, answers: Dict[str, Any]) -> bool:
    """Twin of ``validateSlide`` for a required matrix: every row answered."""
    multiple = bool(getattr(_props(field), "allow_multiple_selection", None))
    for row in _children(field):
        answer = answers.get(str(row.id))
        if multiple:
            choices = answer.get("choices") if isinstance(answer, dict) else None
            values = choices.get("values") if isinstance(choices, dict) else None
            if not values:
                return True
        elif not has_answer_value(answer):
            return True
    return False


def _counts(field: Any) -> bool:
    """Is the field a question a respondent answers?"""
    if getattr(field, "internal", None):
        return False
    if getattr(_props(field), "hidden", None):
        return False
    field_type = _type(field)
    if field_type in NOT_QUESTIONS:
        return False
    return field_type != GROUP or is_repeating_group(field)


def _check_question(
    field: Any,
    answer: Any,
    scope: Dict[str, Any],
    out: List[AnswerProblem],
    key: str,
    item: Optional[int] = None,
) -> None:
    field_id = str(field.id)
    if _type(field) == MATRIX:
        if _required(field) and _matrix_unanswered(field, scope):
            out.append(AnswerProblem(field_id, REQUIRED, item, key))
        return
    if not has_answer_value(answer):
        if _required(field):
            out.append(AnswerProblem(field_id, REQUIRED, item, key))
        return
    for rule in answer_rule_problems(field, answer):
        out.append(AnswerProblem(field_id, rule, item, key))


def _check_group(group: Any, answers: Dict[str, Any], out: List[AnswerProblem]) -> None:
    """Required and answer rules per displayed item (limits and structure
    are ``repeating_groups.validate_group_answers``'s)."""
    repeat = _props(group).repeat
    items = group_items(answers.get(str(group.id)))
    count = min(repeat.effective_max, max(repeat.effective_min, len(items)))
    children = [child for child in _children(group) if _counts(child)]
    for index in range(count):
        item = items[index] if index < len(items) else {}
        scope = {**answers, **item}
        for child in children:
            if is_hidden_by_logic(child, scope):
                continue
            _check_question(
                child, item.get(str(child.id)), scope, out, str(group.id), index
            )


def _check_types(
    by_id: Dict[str, Any],
    matrix_of: Dict[str, Any],
    answers: Dict[str, Any],
    known_ids: Optional[Set[str]],
    out: List[AnswerProblem],
) -> None:
    for key, answer in answers.items():
        field = by_id.get(key)
        if field is None:
            if known_ids is not None and key not in known_ids:
                out.append(AnswerProblem(key, UNKNOWN_FIELD, None, key))
            continue
        rule = type_problem(field, answer, matrix_of.get(key))
        if rule:
            out.append(AnswerProblem(key, rule, None, key))
        if is_repeating_group(field) and rule is None:
            children = {str(child.id): child for child in _children(field)}
            for index, item in enumerate(group_items(answer)):
                for child_id, child_answer in item.items():
                    child = children.get(child_id)
                    child_rule = child and type_problem(child, child_answer)
                    if child_rule:
                        out.append(AnswerProblem(child_id, child_rule, index, key))


def _plain(answers: Any) -> Dict[str, Any]:
    if not isinstance(answers, dict):
        return {}
    return {
        str(key): (
            value.model_dump(exclude_none=True)
            if hasattr(value, "model_dump")
            else value
        )
        for key, value in answers.items()
    }


def validate_answers(
    form: Any,
    answers: Any,
    known_ids: Optional[Set[str]] = None,
    only: Optional[Iterable[str]] = None,
) -> List[AnswerProblem]:
    """Every problem with ``answers`` against ``form`` (the version the
    respondent filled). ``known_ids``: the ids answers may use, others are
    refused (None: not checked). ``only``: report only problems of these
    answer keys (a respondent's edit checks what it changes)."""
    slides = _slides(form)
    if slides is None:
        return []
    answers = _plain(answers)
    by_id: Dict[str, Any] = {}
    matrix_of: Dict[str, Any] = {}
    for slide in slides:
        for field in _children(slide):
            by_id[str(field.id)] = field
            if is_repeating_group(field):
                continue
            for child in _children(field):
                by_id.setdefault(str(child.id), child)
                if _type(field) == MATRIX:
                    matrix_of.setdefault(str(child.id), field)

    problems: List[AnswerProblem] = []
    _check_types(by_id, matrix_of, answers, known_ids, problems)
    for slide in visited_slides(slides, answers):
        for field in _children(slide):
            if not _counts(field) or is_hidden_by_logic(field, answers):
                continue
            if is_repeating_group(field):
                _check_group(field, answers, problems)
            else:
                _check_question(
                    field, answers.get(str(field.id)), answers, problems, str(field.id)
                )
    if only is not None:
        keys = set(only)
        problems = [problem for problem in problems if problem.key in keys]
    return problems


def check_answers(
    form: Any,
    answers: Any,
    form_id: str,
    known_ids: Optional[Set[str]] = None,
    only: Optional[Iterable[str]] = None,
    enforce: Optional[bool] = None,
) -> None:
    """Validate and refuse (422) a response with problems, or only log them
    when ``RESPONSE_VALIDATION_ENFORCE`` is off. Logs carry the form id, the
    number of problems and their rule codes, never a value."""
    if form is None:
        return
    problems = validate_answers(form, answers, known_ids=known_ids, only=only)
    if not problems:
        return
    if enforce is None:
        from backend.config import settings

        enforce = settings.RESPONSE_VALIDATION_ENFORCE
    rules = sorted({problem.rule for problem in problems})
    if not enforce:
        logger.warning(
            "Form {}: {} answer problem(s) not enforced (log only): {}",
            form_id,
            len(problems),
            ",".join(rules),
        )
        return
    logger.info(
        "Form {}: refused a response with {} answer problem(s): {}",
        form_id,
        len(problems),
        ",".join(rules),
    )
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={
            "code": ERROR_CODE,
            "message": ERROR_MESSAGE,
            "errors": [problem.as_json() for problem in problems],
        },
    )
