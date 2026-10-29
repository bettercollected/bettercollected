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

- **Endings exist:** a page jump that names an ending names one of the
  form's endings (respondents would otherwise see the default ending
  instead of the one the creator chose).
- **Readable colours:** the form theme's own colours meet WCAG 2.2 AA
  contrast where the respondent form shows them (text 4.5:1, controls 3:1;
  ``services/theme_contrast.py``, the port of the builder's contrast guard).
  Every preset passes; a custom palette may not. A theme without its four
  colours (an old form on the defaults) isn't checked, and text over an
  image background can't be measured, so it never blocks.

- **Imports are looked over first:** a draft made by an import from another
  product (``WorkspaceFormSettings.needs_review``) is not published until a
  person clears the mark on its import report (``review_problem``; the
  problem carries only the report's id, ``importId``).

- **The workspace has a title:** respondents see the workspace's title as
  who receives their answers (the privacy strip), so a form is not published
  while its workspace has none (``workspace_title_problem``; the problem
  carries nothing of the workspace, ``fieldId`` is empty). A title needs a
  visible character (spaces, zero-width and filler characters show nothing)
  and is not "untitled", which onboarding also treats as no title; the
  handle never stands in for one (the default workspace's handle is its
  owner's id). Only a new publish or republish is
  held up: a form that is already live stays live. Like "why we ask", the
  rule is held to forms created under check version 2 or later
  (``requires_workspace_title``): a form made before it publishes and
  republishes as it always did, whatever its workspace's title.

Internal ("for office use") fields are not respondent-facing and are skipped.

"Why we ask this" is required only of forms created under these checks
(``WorkspaceFormSettings.publish_checks_version`` set at creation): forms made
before them were published without it and must stay publishable. For those the
builder shows the missing reasons as a recommendation. The other rules hold
for every form.
"""

import copy
import re
import unicodedata
from http import HTTPStatus
from typing import Any, Dict, List, Optional

from common.models.standard_form import with_ending_ids

from backend.app.exceptions import HTTPException
from backend.app.services.internal_fields import (
    _get,
    _type_value,
    is_internal,
    iter_question_fields,
)
from backend.app.services.theme_contrast import (
    display_ratio,
    has_guarded_colours,
    theme_contrast_guard,
)

FORM_NOT_PUBLISHABLE = "form_not_publishable"

# The version of these checks a new form is created under. A form without one
# (created earlier) is not required to say why it asks; a form created under
# version 1 is not held to the workspace-title rule (version 2).
PUBLISH_CHECKS_VERSION = 2
WHY_WE_ASK_FROM_VERSION = 1
WORKSPACE_TITLE_FROM_VERSION = 2

MISSING_WHY_WE_ASK = "missing_why_we_ask"
REQUIRED_UNANSWERABLE = "required_unanswerable"
PRESET_ANSWER = "preset_answer"
MISSING_ENDING = "missing_ending"
THEME_CONTRAST = "theme_contrast"
NEEDS_REVIEW = "needs_review"
WORKSPACE_TITLE_MISSING = "workspace_title_missing"
# The ``fieldId`` of the theme's problem: it belongs to no question (the
# webapp's THEME_PROBLEM_ID).
THEME_PROBLEM_ID = "theme"

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
    problems += _missing_ending_problems(form)
    problems += theme_contrast_problems(_get(form, "theme"))
    return problems


# What each failing pairing is, in the builder's words (publish-checks.ts).
_CONTRAST_WORDS = {
    "text": "questions and text on the page",
    "answer": "answers in the input boxes",
    "button": "white text on buttons",
    "border": "input borders",
    "action": "chosen answers and progress",
}
_FIX_ORDER = ("primary", "secondary", "tertiary", "accent")


def _and_list(words: List[str]) -> str:
    return f"{', '.join(words[:-1])} and {words[-1]}" if len(words) > 1 else words[0]


def theme_contrast_problems(theme: Any) -> List[Dict[str, Optional[str]]]:
    """The form theme, when its own colours fail WCAG AA contrast where the
    respondent form shows them. The message names each failing pairing with
    its lowest ratio (rounded down) and the nearest colours that pass."""
    if not has_guarded_colours(theme):
        return []
    guard = theme_contrast_guard(theme)
    if not guard.issues:
        return []
    pairs = _and_list(
        [
            f"{_CONTRAST_WORDS[issue.key]} ({display_ratio(issue.ratio)}:1, "
            f"needs {display_ratio(issue.minimum)}:1)"
            for issue in guard.issues
        ]
    )
    message = f"The theme's colours are hard to read: {pairs}."
    if guard.fix:
        colours = [
            f"{role} {guard.fix[role]}" for role in _FIX_ORDER if role in guard.fix
        ]
        background = guard.fix.get("background")
        if background:
            colours.append(
                f"background gradient {background['gradientFrom']} to "
                f"{background['gradientTo']}"
            )
        message += (
            f" The nearest colours that pass: {_and_list(colours)}. Use them "
            "(the builder's Design tab offers them in one click), or pick others."
        )
    return [{"code": THEME_CONTRAST, "fieldId": THEME_PROBLEM_ID, "message": message}]


def _missing_ending_problems(form: Any) -> List[Dict[str, Optional[str]]]:
    """A jump to an ending the form does not have. ``fieldId`` is the page."""
    # ids as read (an ending stored without one gets its derived id)
    endings = with_ending_ids(copy.deepcopy(list(_get(form, "thankyou_page") or [])))
    ids = {_get(ending, "id") for ending in endings}
    problems = []
    for number, page in enumerate(_get(form, "fields") or [], start=1):
        jumps = _get(_get(page, "properties"), "jumps") or []
        for jump in jumps:
            ending_id = _get(jump, "ending_id") or _get(jump, "endingId")
            if ending_id and ending_id not in ids:
                problems.append(
                    {
                        "code": MISSING_ENDING,
                        "fieldId": _get(page, "id"),
                        "message": f"A jump on page {number} goes to an ending "
                        "that no longer exists. Choose another ending for it.",
                    }
                )
    return problems


def review_problem(import_id: Optional[str]) -> Dict[str, Optional[str]]:
    """The problem of a form whose import is still marked "needs review".
    ``importId`` is the id of the import report (no report content): the
    webapp links to it. ``fieldId`` is empty: it belongs to no question."""
    return {
        "code": NEEDS_REVIEW,
        "fieldId": None,
        "importId": import_id,
        "message": "It was imported and still needs review. Look through the "
        "import report and mark it as reviewed; then it can be published.",
    }


# Characters that show nothing: format, space, line/paragraph separator and
# control characters (zero-width space, word joiner, BOM, NBSP, ...), plus
# the fillers and blanks Unicode files elsewhere (Hangul and Braille blanks,
# soft hyphen, Mongolian vowel separator).
_INVISIBLE_CATEGORIES = {"Cf", "Zs", "Zl", "Zp", "Cc"}
_INVISIBLE_EXTRA = {
    "\u115f", "\u1160", "\u3164", "\uffa0", "\u2800", "\u00ad", "\u180e",
}  # fmt: skip
# What onboarding also treats as "no title" (webapp onboarding page, login).
_PLACEHOLDER_TITLE = "untitled"


def visible_title(title: Optional[str]) -> str:
    """The characters of ``title`` that can be seen; "" when there are none.
    Mirrored by the webapp's ``visibleTitle`` (utils/publish-checks.ts)."""
    if not isinstance(title, str):
        return ""
    return "".join(
        char
        for char in title
        if char not in _INVISIBLE_EXTRA
        and unicodedata.category(char) not in _INVISIBLE_CATEGORIES
    )


def has_workspace_title(title: Optional[str]) -> bool:
    """A title needs at least one visible character, and "untitled" (any
    case, as onboarding treats it) is the placeholder, not a title."""
    visible = visible_title(title)
    return bool(visible) and visible.casefold() != _PLACEHOLDER_TITLE


def workspace_title_problem(title: Optional[str]) -> Optional[Dict[str, Optional[str]]]:
    """The problem of a workspace without a title, or None when it has one.
    ``title``: the workspace's ``title`` (None when the workspace could not be
    read: that is no title either, so it never fails open). The problem names
    nothing of the workspace; the webapp links to the workspace settings."""
    if has_workspace_title(title):
        return None
    return {
        "code": WORKSPACE_TITLE_MISSING,
        "fieldId": None,
        "message": "Your workspace has no title yet. Respondents see it as "
        "who receives their answers, so give it a title in the workspace "
        "settings (a workspace admin can do this); then the form can be "
        "published.",
    }


def ensure_templatable(review: Optional[Dict[str, Optional[str]]]) -> None:
    """422 ``needs_review`` (the problem shape of a refused publish, with the
    same ``importId``) while the source form's import still needs review: no
    template is made from it until a person clears the mark. ``review``: the
    form's ``review_problem``, or None."""
    if not review:
        return
    message = (
        "It was imported and still needs review. Look through the import "
        "report and mark it as reviewed; then a template can be made from it."
    )
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={
            "code": NEEDS_REVIEW,
            "message": "This form can't be made into a template yet. " + message,
            "problems": [{**review, "message": message}],
        },
    )


def requires_why_we_ask(checks_version: Optional[int]) -> bool:
    """Is a form created under ``checks_version`` held to the reason rule?"""
    return bool(checks_version) and checks_version >= WHY_WE_ASK_FROM_VERSION


def requires_workspace_title(checks_version: Optional[int]) -> bool:
    """Is a form created under ``checks_version`` held to the workspace-title
    rule? Only forms created under version 2 or later: earlier ones (and forms
    with no version) publish and republish as before."""
    return bool(checks_version) and checks_version >= WORKSPACE_TITLE_FROM_VERSION


def ensure_publishable(
    form: Any,
    checks_version: Optional[int] = None,
    review: Optional[Dict[str, Optional[str]]] = None,
    workspace_problem: Optional[Dict[str, Optional[str]]] = None,
) -> None:
    """422 ``form_not_publishable`` listing every problem that blocks this
    form, or nothing. ``checks_version``: the form's
    ``publish_checks_version`` (None for a form created before the checks).
    ``review``: the form's ``review_problem`` while its import still needs
    review (listed first). ``workspace_problem``: the workspace's
    ``workspace_title_problem`` (listed next: it belongs to no question; held
    only against forms created under ``requires_workspace_title``)."""
    problems = [review] if review else []
    if workspace_problem and requires_workspace_title(checks_version):
        problems.append(workspace_problem)
    problems += [
        problem
        for problem in publish_problems(form)
        if problem["code"] != MISSING_WHY_WE_ASK
        or requires_why_we_ask(checks_version)
    ]
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
