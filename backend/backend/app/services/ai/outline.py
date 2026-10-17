"""The form outline: step one of AI form creation.

The model first answers with an outline (title, language, pages with section
titles, the questions each page asks, and show/hide and jump rules in plain
terms) instead of a finished form. The outline is validated here, can be
reviewed and edited by the person, and is then compiled deterministically
into one atomic batch of form ops (``outline_compile.py``).

Two levels of checking:

- ``outline_problems(outline, from_model=True)``: what a model reply must
  get right (choices on choice questions, a reason on every identity
  question, rules that point at earlier questions and later pages). A reply
  with problems gets one corrective retry (``structured.py``), then fails
  with ``ai_unusable_reply``.
- ``prune_outline``: an outline the person edited is authoritative. Rules
  that no longer make sense (their question was deleted or moved after the
  target) are left out with a note instead of refusing the build.

Notes and problems name keys and positions, never the outline's text.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

from common.models.standard_form import SECTION_TITLE_MAX_LENGTH, WHY_WE_ASK_MAX_LENGTH
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pydantic.alias_generators import to_camel

from backend.app.services.publish_checks import asks_for_identity

# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

OUTLINE_QUESTION_TYPES = (
    "short_text",
    "long_text",
    "email",
    "phone_number",
    "number",
    "url",
    "date",
    "yes_no",
    "multiple_choice",
    "dropdown",
    "rating",
    "linear_rating",
    "file_upload",
    "statement",
)
CHOICE_TYPES = frozenset({"multiple_choice", "dropdown"})
NUMERIC_TYPES = frozenset({"number", "rating", "linear_rating"})
TEXT_TYPES = frozenset({"short_text", "long_text"})
# Display-only: nothing to answer, so no rule can depend on it.
DISPLAY_TYPES = frozenset({"statement"})

COMPARISONS = (
    "equals",
    "not_equals",
    "contains",
    "not_contains",
    "is_answered",
    "is_not_answered",
    "greater_than",
    "less_than",
    "at_least",
    "at_most",
)
VALUELESS = frozenset({"is_answered", "is_not_answered"})
ORDERED = frozenset({"greater_than", "less_than", "at_least", "at_most"})
END = "end"

MAX_PAGES = 20
MAX_QUESTIONS_PER_PAGE = 15
MAX_QUESTIONS = 100
MAX_CHOICES = 50
MAX_RULES = 50
MAX_CONDITIONS = 5
MAX_OMITTED = 20
TITLE_MAX = 200
LABEL_MAX = 500
TEXT_MAX = 1000
CHOICE_MAX = 300
KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$"
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$"

Key = Annotated[str, StringConstraints(pattern=KEY_PATTERN)]
ChoiceText = Annotated[str, StringConstraints(min_length=1, max_length=CHOICE_MAX)]


class _Camel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, alias_generator=to_camel, extra="ignore"
    )


class OutlineValidation(_Camel):
    """Answer limits: lengths on text, values on numbers, a named pattern
    on short text."""

    min_length: Optional[int] = Field(None, ge=0, le=10000)
    max_length: Optional[int] = Field(None, ge=1, le=10000)
    min_value: Optional[float] = Field(None, ge=-1e12, le=1e12)
    max_value: Optional[float] = Field(None, ge=-1e12, le=1e12)
    preset: Optional[Literal["digits", "letters", "alphanumeric"]] = None


class OutlineQuestion(_Camel):
    key: Key
    label: str = Field(..., min_length=1, max_length=LABEL_MAX)
    type: Literal[OUTLINE_QUESTION_TYPES]  # type: ignore[valid-type]
    required: bool = False
    description: Optional[str] = Field(None, max_length=TEXT_MAX)
    why_we_ask: Optional[str] = Field(None, max_length=WHY_WE_ASK_MAX_LENGTH)
    choices: Optional[List[ChoiceText]] = Field(None, max_length=MAX_CHOICES)
    allow_multiple: Optional[bool] = None
    validation: Optional[OutlineValidation] = None


class OutlinePage(_Camel):
    key: Key
    section_title: Optional[str] = Field(None, max_length=SECTION_TITLE_MAX_LENGTH)
    questions: List[OutlineQuestion] = Field(
        default_factory=list, max_length=MAX_QUESTIONS_PER_PAGE
    )


class OutlineCondition(_Camel):
    question: Key
    comparison: Literal[COMPARISONS]  # type: ignore[valid-type]
    value: Optional[str] = Field(None, max_length=CHOICE_MAX)


class OutlineLogic(_Camel):
    """Show or hide ``target`` when the conditions match."""

    target: Key
    action: Literal["show", "hide"] = "show"
    match: Literal["all", "any"] = "all"
    conditions: List[OutlineCondition] = Field(
        ..., min_length=1, max_length=MAX_CONDITIONS
    )


class OutlineJump(_Camel):
    """After page ``from_page``, go to page ``to`` (or ``"end"``: submit)
    when the conditions match. The first matching jump of a page wins."""

    from_page: Key
    to: Key
    match: Literal["all", "any"] = "all"
    conditions: List[OutlineCondition] = Field(
        ..., min_length=1, max_length=MAX_CONDITIONS
    )


class OutlineOmission(_Camel):
    """A question the model chose not to ask, and why (data minimisation)."""

    label: str = Field(..., min_length=1, max_length=LABEL_MAX)
    reason: str = Field(..., min_length=1, max_length=TEXT_MAX)


class FormOutline(_Camel):
    title: str = Field(..., min_length=1, max_length=TITLE_MAX)
    description: Optional[str] = Field(None, max_length=TEXT_MAX)
    language: Annotated[str, StringConstraints(pattern=LANGUAGE_PATTERN)] = "en"
    # a theme preset by name; none = Leaflet, the default for new forms
    theme: Optional[str] = Field(None, max_length=60)
    pages: List[OutlinePage] = Field(..., min_length=1, max_length=MAX_PAGES)
    logic: List[OutlineLogic] = Field(default_factory=list, max_length=MAX_RULES)
    jumps: List[OutlineJump] = Field(default_factory=list, max_length=MAX_RULES)
    omitted: List[OutlineOmission] = Field(default_factory=list, max_length=MAX_OMITTED)

    def questions(self) -> List[Tuple[int, OutlineQuestion]]:
        """(page position, question) in form order."""
        return [
            (number, question)
            for number, page in enumerate(self.pages)
            for question in page.questions
        ]

    def dump(self) -> Dict[str, Any]:
        """As the API returns it: camelCase, absent values left out."""
        return self.model_dump(by_alias=True, exclude_none=True, mode="json")


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _distinct(choices: Optional[List[str]]) -> List[str]:
    seen, out = set(), []
    for choice in choices or []:
        text = " ".join(choice.split())
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out


def needs_choices(question: OutlineQuestion) -> bool:
    return question.type in CHOICE_TYPES and len(_distinct(question.choices)) < 2


def needs_why_we_ask(question: OutlineQuestion) -> bool:
    return not (question.why_we_ask or "").strip() and asks_for_identity(
        {"type": question.type, "title": question.label}
    )


def _yes_no_value(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip().lower()
    return {"yes": "Yes", "no": "No", "true": "Yes", "false": "No"}.get(text)


def _number(value: Optional[str]) -> Optional[float]:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) < 1e15 else None


def condition_problem(
    condition: OutlineCondition,
    source: Optional[OutlineQuestion],
) -> Optional[str]:
    """Why a condition cannot be built on ``source``, or None."""
    if source is None:
        return "names a question that is not in the outline"
    if source.type in DISPLAY_TYPES:
        return "depends on a statement, which has no answer"
    if condition.comparison in VALUELESS:
        return None
    if condition.value is None or not condition.value.strip():
        return f"'{condition.comparison}' needs a value"
    if source.type == "yes_no":
        if condition.comparison not in ("equals", "not_equals"):
            return "a yes/no question can only be compared with equals or not_equals"
        if _yes_no_value(condition.value) is None:
            return "a yes/no question is compared with 'Yes' or 'No'"
        return None
    if source.type in CHOICE_TYPES:
        if condition.comparison in ORDERED:
            return "a choice question cannot be compared as a number"
        labels = {c.lower() for c in _distinct(source.choices)}
        if " ".join(condition.value.split()).lower() not in labels:
            return "the value is not one of the question's choices"
        return None
    if condition.comparison in ORDERED:
        if source.type not in NUMERIC_TYPES:
            return "only number and rating questions can be compared as numbers"
        if _number(condition.value) is None:
            return "the value must be a number"
    return None


def _rule_problems(outline: FormOutline) -> List[Tuple[str, int, str]]:
    """(``logic`` | ``jumps``, rule index, problem) for each rule that cannot
    be built: unknown keys, conditions on later answers, backward jumps."""
    position: Dict[str, Tuple[int, int]] = {}
    by_key: Dict[str, OutlineQuestion] = {}
    for page_number, page in enumerate(outline.pages):
        for question_number, question in enumerate(page.questions):
            position.setdefault(question.key, (page_number, question_number))
            by_key.setdefault(question.key, question)
    pages = {page.key: number for number, page in enumerate(outline.pages)}
    problems: List[Tuple[str, int, str]] = []

    targets = set()
    for index, rule in enumerate(outline.logic):
        where = position.get(rule.target)
        if where is None:
            problems.append(
                ("logic", index, "its target is not a question of the outline")
            )
            continue
        if rule.target in targets:
            problems.append(("logic", index, "its target already has a show/hide rule"))
            continue
        for condition in rule.conditions:
            problem = condition_problem(condition, by_key.get(condition.question))
            if problem is None and condition.question == rule.target:
                problem = "depends on its own answer"
            if problem is None and position[condition.question] >= where:
                problem = "depends on a question asked after its target"
            if problem:
                problems.append(("logic", index, f"a condition {problem}"))
                break
        else:
            targets.add(rule.target)

    for index, jump in enumerate(outline.jumps):
        start = pages.get(jump.from_page)
        if start is None:
            problems.append(("jumps", index, "its page is not in the outline"))
            continue
        if jump.to != END:
            goal = pages.get(jump.to)
            if goal is None:
                problems.append(
                    (
                        "jumps",
                        index,
                        f"it goes to a page that is not in the outline (use '{END}' to submit)",
                    )
                )
                continue
            if goal <= start:
                problems.append(
                    (
                        "jumps",
                        index,
                        "it goes back or to its own page; jumps only go forward",
                    )
                )
                continue
        for condition in jump.conditions:
            problem = condition_problem(condition, by_key.get(condition.question))
            if problem is None and position[condition.question][0] > start:
                problem = "depends on a question asked after its page"
            if problem:
                problems.append(("jumps", index, f"a condition {problem}"))
                break
    return problems


def outline_problems(outline: FormOutline, from_model: bool = True) -> List[str]:
    """What is wrong with an outline, as locations and messages without
    its text. ``from_model``: also what a model reply must get right."""
    problems: List[str] = []
    page_keys = [page.key for page in outline.pages]
    if len(set(page_keys)) != len(page_keys):
        problems.append("pages: every page needs its own key")
    question_keys = [q.key for _, q in outline.questions()]
    if len(set(question_keys)) != len(question_keys):
        problems.append("pages: every question needs its own key")
    if len(question_keys) > MAX_QUESTIONS:
        problems.append(f"pages: at most {MAX_QUESTIONS} questions in all")
    if END in page_keys:
        problems.append(f"pages: '{END}' is reserved for jumps to the end")
    if from_model:
        if not any(q.type not in DISPLAY_TYPES for _, q in outline.questions()):
            problems.append("pages: the outline asks no question")
        for page_number, page in enumerate(outline.pages):
            if not page.questions:
                problems.append(
                    f"pages.{page_number}: a page needs at least one question"
                )
            for question_number, question in enumerate(page.questions):
                where = f"pages.{page_number}.questions.{question_number}"
                if needs_choices(question):
                    problems.append(
                        f"{where}: a {question.type} question needs at least 2 distinct choices"
                    )
                if needs_why_we_ask(question):
                    problems.append(
                        f"{where}: this question asks for identifying data; give whyWeAsk "
                        "(one plain sentence), or leave the question out and list it under omitted"
                    )
        for kind, index, problem in _rule_problems(outline):
            problems.append(f"{kind}.{index}: {problem}")
    return problems


def prune_outline(outline: FormOutline) -> Tuple[FormOutline, List[str]]:
    """An edited outline as it can be built: empty pages left out, rules
    that can no longer work dropped, each with a note."""
    notes: List[str] = []
    pruned = outline.model_copy(deep=True)
    empty = [page.key for page in pruned.pages if not page.questions]
    if empty:
        pruned.pages = [page for page in pruned.pages if page.questions]
        notes.append(f"{len(empty)} page(s) without questions were left out.")
    # Rules are judged one by one against the questions and pages, so
    # dropping one never makes another invalid: one pass is enough.
    drop = {(kind, index) for kind, index, _ in _rule_problems(pruned)}
    if drop:
        pruned.logic = [
            r for i, r in enumerate(pruned.logic) if ("logic", i) not in drop
        ]
        pruned.jumps = [
            r for i, r in enumerate(pruned.jumps) if ("jumps", i) not in drop
        ]
        logic = sum(1 for kind, _ in drop if kind == "logic")
        jumps = len(drop) - logic
        if logic:
            notes.append(
                f"{logic} show/hide rule(s) were left out: they no longer match the questions."
            )
        if jumps:
            notes.append(
                f"{jumps} page jump(s) were left out: they no longer match the pages or questions."
            )
    return pruned, notes


def gaps(outline: FormOutline) -> Dict[str, List[str]]:
    """Page key -> keys of its questions with something missing that the
    model may fill (choices of a choice question, the reason of an identity
    question)."""
    found: Dict[str, List[str]] = {}
    for page in outline.pages:
        keys = [
            q.key for q in page.questions if needs_choices(q) or needs_why_we_ask(q)
        ]
        if keys:
            found[page.key] = keys
    return found


# ---------------------------------------------------------------------------
# Strict JSON schema (OpenAI structured output)
# ---------------------------------------------------------------------------


def _strict(properties: Dict[str, Any]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _nullable(kind: str, **extra) -> dict:
    return {"type": [kind, "null"], **extra}


def _condition_schema() -> dict:
    return _strict(
        {
            "question": {"type": "string"},
            "comparison": {"type": "string", "enum": list(COMPARISONS)},
            "value": _nullable("string"),
        }
    )


def outline_schema() -> dict:
    """The outline as a strict JSON schema: every key listed, optional
    values nullable (null means absent), no length or pattern keywords
    (strict mode refuses them; the Pydantic models check them)."""
    validation = _strict(
        {
            "minLength": _nullable("integer"),
            "maxLength": _nullable("integer"),
            "minValue": _nullable("number"),
            "maxValue": _nullable("number"),
            "preset": {
                "type": ["string", "null"],
                "enum": ["digits", "letters", "alphanumeric", None],
            },
        }
    )
    question = _strict(
        {
            "key": {"type": "string"},
            "label": {"type": "string"},
            "type": {"type": "string", "enum": list(OUTLINE_QUESTION_TYPES)},
            "required": {"type": "boolean"},
            "description": _nullable("string"),
            "whyWeAsk": _nullable("string"),
            "choices": _nullable("array", items={"type": "string"}),
            "allowMultiple": _nullable("boolean"),
            "validation": {"anyOf": [validation, {"type": "null"}]},
        }
    )
    page = _strict(
        {
            "key": {"type": "string"},
            "sectionTitle": _nullable("string"),
            "questions": {"type": "array", "items": question},
        }
    )
    logic = _strict(
        {
            "target": {"type": "string"},
            "action": {"type": "string", "enum": ["show", "hide"]},
            "match": {"type": "string", "enum": ["all", "any"]},
            "conditions": {"type": "array", "items": _condition_schema()},
        }
    )
    jump = _strict(
        {
            "fromPage": {"type": "string"},
            "to": {"type": "string"},
            "match": {"type": "string", "enum": ["all", "any"]},
            "conditions": {"type": "array", "items": _condition_schema()},
        }
    )
    omission = _strict({"label": {"type": "string"}, "reason": {"type": "string"}})
    return _strict(
        {
            "title": {"type": "string"},
            "description": _nullable("string"),
            "language": {"type": "string"},
            "theme": _nullable("string"),
            "pages": {"type": "array", "items": page},
            "logic": {"type": "array", "items": logic},
            "jumps": {"type": "array", "items": jump},
            "omitted": {"type": "array", "items": omission},
        }
    )


OUTLINE_JSON_SCHEMA = {"name": "form_outline", "schema": outline_schema()}


class GapFillQuestion(_Camel):
    key: Key
    choices: Optional[List[ChoiceText]] = Field(None, max_length=MAX_CHOICES)
    why_we_ask: Optional[str] = Field(None, max_length=WHY_WE_ASK_MAX_LENGTH)


class GapFillReply(_Camel):
    questions: List[GapFillQuestion] = Field(
        default_factory=list, max_length=MAX_QUESTIONS_PER_PAGE
    )


GAP_FILL_JSON_SCHEMA = {
    "name": "outline_gaps",
    "schema": _strict(
        {
            "questions": {
                "type": "array",
                "items": _strict(
                    {
                        "key": {"type": "string"},
                        "choices": _nullable("array", items={"type": "string"}),
                        "whyWeAsk": _nullable("string"),
                    }
                ),
            }
        }
    ),
}


def fill_gaps(
    outline: FormOutline, page_key: str, reply: GapFillReply
) -> Tuple[int, int]:
    """Fill what is missing on one page from the model's reply, and only
    that: a value the person gave is never replaced. (choices filled,
    reasons filled)."""
    page = next((p for p in outline.pages if p.key == page_key), None)
    if page is None:
        return 0, 0
    answers = {q.key: q for q in reply.questions}
    choices = reasons = 0
    for question in page.questions:
        answer = answers.get(question.key)
        if answer is None:
            continue
        if needs_choices(question) and len(_distinct(answer.choices)) >= 2:
            question.choices = _distinct(answer.choices)
            choices += 1
        if needs_why_we_ask(question) and (answer.why_we_ask or "").strip():
            question.why_we_ask = " ".join(answer.why_we_ask.split())
            reasons += 1
    return choices, reasons
