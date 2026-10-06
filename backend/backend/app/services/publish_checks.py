"""Honest defaults a form must meet before it is published.

Checked on every publish (``WorkspaceFormService.publish_form``, which the
builder, the API and the MCP server all go through); the webapp runs the same
checks before it calls publish (``webapp/src/utils/publish-checks.ts`` — keep
the two in step).

- **Why we ask this:** a question that collects an email address, a phone
  number or an ID number carries a short reason (``properties.why_we_ask``)
  that respondents see under it. ID-number questions are recognised from the
  title with a deliberately narrow pattern, so an ordinary question is never
  held up by a guess.
- **No dead ends:** a required question respondents cannot answer (a
  statement, image, video or plain group marked required; a choice question
  without options; a grid without columns) would stop everyone on that page.
  Required questions hidden by logic or on pages a jump skips are not dead
  ends: respondents are only ever asked for the questions they are shown.
- **No pre-ticked answers:** a respondent-facing question never starts with an
  answer of the creator's choosing: a choice or yes/no question whose
  ``value`` names one of its options would read as already ticked (older
  form formats used ``value`` as a default answer; today it only ever holds a
  legacy title, which names no option), so nobody's agreement is given for
  them.

Internal ("for office use") fields are not respondent-facing and are skipped.
"""

import re
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from backend.app.exceptions import HTTPException
from backend.app.services.internal_fields import (
    _get,
    _type_value,
    is_internal,
    iter_question_fields,
)

FORM_NOT_PUBLISHABLE = "form_not_publishable"

MISSING_WHY_WE_ASK = "missing_why_we_ask"
REQUIRED_UNANSWERABLE = "required_unanswerable"
PRESET_ANSWER = "preset_answer"

# Questions whose answer identifies the respondent by type alone.
IDENTIFYING_TYPES = {"email", "phone_number"}
# Text questions that may ask for an ID number; decided by the title.
ID_NUMBER_CANDIDATE_TYPES = {"short_text", "long_text", "number"}
# Kept narrow on purpose: whole words, and "ID"/"passport" only together with
# "number". "Order ID" or "passport photo" are not ID numbers.
ID_NUMBER_TITLE = re.compile(
    r"\b("
    r"bsn|burgerservicenummer|sofinummer|sofi-nummer"
    r"|passport\s*(?:number|no\.?|nr\.?)|paspoortnummer|paspoort\s*(?:nummer|nr\.?)"
    r"|id[\s-]?(?:number|nummer|nr\.?|no\.?)"
    r"|identification\s+number|identity\s+(?:card\s+)?number"
    r"|identiteitsnummer|identiteitskaartnummer"
    r"|national\s+(?:id|identity|insurance)\s+number"
    r"|social\s+security\s+number|ssn"
    r")(?![\w-])",
    re.IGNORECASE,
)

# Display-only types: nothing for a respondent to answer.
DISPLAY_ONLY_TYPES = {
    "text",
    "statement",
    "IMAGE_CONTENT",
    "VIDEO_CONTENT",
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
CHOICE_TYPES = {"multiple_choice", "dropdown", "ranking"}
PRESET_ANSWER_TYPES = CHOICE_TYPES | {"yes_no"}
YES_NO_DEFAULT_CHOICES = {"yes", "no"}


def question_text(field: Any) -> str:
    """The question's title as plain text (TipTap documents included)."""
    title = _get(field, "title")
    if isinstance(title, str):
        text = title
    else:
        text = " ".join(_text_nodes(title))
    return " ".join(text.split())


def _text_nodes(node: Any) -> List[str]:
    if isinstance(node, dict):
        if node.get("type") == "text":
            return [str(node.get("text") or "")]
        if node.get("type") == "answerPipe":
            return [str((node.get("attrs") or {}).get("label") or "")]
        return [t for child in node.get("content") or [] for t in _text_nodes(child)]
    return []


def asks_for_identity(field: Any) -> bool:
    """Does this question collect an email, a phone number or an ID number?"""
    field_type = _type_value(field)
    if field_type in IDENTIFYING_TYPES:
        return True
    if field_type in ID_NUMBER_CANDIDATE_TYPES:
        return bool(ID_NUMBER_TITLE.search(question_text(field)))
    return False


def _label(field: Any) -> str:
    text = question_text(field)
    if len(text) > 60:
        text = text[:57].rstrip() + "..."
    return f'"{text}"' if text else "A question"


def _is_required(field: Any) -> bool:
    return bool(_get(_get(field, "validations"), "required"))


def _unanswerable_reason(field: Any) -> Optional[str]:
    """Why respondents could never answer this required question, if so."""
    field_type = _type_value(field)
    properties = _get(field, "properties")
    if field_type in DISPLAY_ONLY_TYPES:
        return "it only shows content"
    if field_type == "group" and not _get(properties, "repeat"):
        return "it is only a group heading"
    if field_type in CHOICE_TYPES:
        choices = _get(properties, "choices") or []
        if not any(_choice_text(choice) for choice in choices):
            return "it has no options to choose from"
    if field_type == "matrix":
        rows = _get(properties, "fields") or []
        if rows and not any(
            _choice_text(choice)
            for row in rows
            for choice in (_get(_get(row, "properties"), "choices") or [])
        ):
            return "its grid has no columns to choose from"
    return None


def _choice_text(choice: Any) -> str:
    return str(_get(choice, "value") or _get(choice, "label") or "").strip()


def _has_preset_answer(field: Any) -> bool:
    """Does the field's ``value`` pick one of its own options?"""
    field_type = _type_value(field)
    if field_type not in PRESET_ANSWER_TYPES:
        return False
    value = str(_get(field, "value") or "").strip().lower()
    if not value:
        return False
    options = {
        _choice_text(choice).lower()
        for choice in (_get(_get(field, "properties"), "choices") or [])
    }
    if field_type == "yes_no":
        options |= YES_NO_DEFAULT_CHOICES
    return value in options


def publish_problems(form: Any) -> List[Dict[str, Optional[str]]]:
    """Everything that keeps this form from being published, in form order.

    Each problem: ``{"code", "fieldId", "message"}``; the message says what is
    wrong and how to fix it."""
    problems: List[Dict[str, Optional[str]]] = []
    for field in iter_question_fields(form):
        if is_internal(field):
            continue
        field_id = _get(field, "id")
        label = _label(field)
        if _has_preset_answer(field):
            problems.append(
                {
                    "code": PRESET_ANSWER,
                    "fieldId": field_id,
                    "message": f"{label} starts with an answer already chosen. "
                    "Respondents must choose for themselves: clear the "
                    "preset answer.",
                }
            )
        if _is_required(field):
            reason = _unanswerable_reason(field)
            if reason:
                problems.append(
                    {
                        "code": REQUIRED_UNANSWERABLE,
                        "fieldId": field_id,
                        "message": f"{label} is required, but {reason}, so "
                        "nobody could get past it. Turn off Required or "
                        "complete the question.",
                    }
                )
        if asks_for_identity(field):
            reason = _get(_get(field, "properties"), "why_we_ask")
            if not (isinstance(reason, str) and reason.strip()):
                problems.append(
                    {
                        "code": MISSING_WHY_WE_ASK,
                        "fieldId": field_id,
                        "message": f"{label} asks for personal details. Add a "
                        "short \"Why we ask this\" line to the question so "
                        "respondents know why you need it.",
                    }
                )
    return problems


def ensure_publishable(form: Any) -> None:
    """422 ``form_not_publishable`` listing every problem, or nothing."""
    problems = publish_problems(form)
    if problems:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": FORM_NOT_PUBLISHABLE,
                "message": "This form can't be published yet: "
                + " ".join(problem["message"] for problem in problems),
                "problems": problems,
            },
        )
