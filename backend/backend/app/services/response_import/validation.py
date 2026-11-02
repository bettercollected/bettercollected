"""The respondent checks, for one imported row.

``check_submission`` runs the building blocks the submission path runs
(``WorkspaceFormService.submit_response``), in the same order, on answers
read from a CSV file: repeating-group structure, calculated values and field
rules, Required, types, answer rules and choice logic
(``calculate_and_check``), the ending the answers reach, and date rules. It
returns the problems instead of raising. The shape (``form, answers ->
answers, ending, problems``) is deliberately small: a server-side caller that
stores one submission (the submissions API) can call it as it is, and a later
change can make ``submit_response`` call it too. ``tests/app/response_import/
test_parity.py`` holds one fixture set both paths must agree on.

An import always enforces: ``RESPONSE_VALIDATION_ENFORCE`` softens the rollout
of respondent validation and never applies here. Signatures are not part of it
(a typed one is checked as a shape by ``check_answers``; a drawn one cannot be
imported), nor are files. Questions whose options come from a list or another
question (option sources) are not importable in 4.3 (``targets.py`` leaves them
out of the mapping): the submit path's ``OptionSourceService.apply`` step, which
checks the chosen option is offered and writes the label snapshot, is not run
here.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Set

from backend.app.exceptions import HTTPException
from backend.app.services.answer_validation import answer_ids, reached_ending_id
from backend.app.services.calculated_fields import (
    calculate_and_check,
    drop_draft_calculations,
    respondent_today,
)
from backend.app.services.date_rules import validate_date_rule_answers
from backend.app.services.repeating_groups import (
    drop_hidden_group_answers,
    validate_group_answers,
)

GROUP_INVALID = "group_invalid"
DATE_RULE = "date_rule"
INVALID = "invalid"


@dataclass(frozen=True)
class Problem:
    """One broken rule: the question (None for the row as a whole), the rule
    code and, inside a repeating group, the item (from 0)."""

    field_id: Optional[str]
    rule: str
    item: Optional[int] = None


@dataclass
class SubmissionCheck:
    answers: Dict[str, Any]
    ending_id: Optional[str]
    problems: List[Problem]

    @property
    def ok(self) -> bool:
        return not self.problems


def _problems_of(refused: HTTPException) -> List[Problem]:
    content = getattr(refused, "content", None)
    if isinstance(content, dict):
        errors = content.get("errors")
        if isinstance(errors, list) and errors:
            return [
                Problem(str(e.get("fieldId")) if e.get("fieldId") is not None else None, str(e.get("rule")), e.get("item"))
                for e in errors
                if isinstance(e, dict)
            ]
        if content.get("code"):
            return [Problem(None, str(content["code"]))]
    return [Problem(None, INVALID)]


def known_ids_of(draft: Any, published: Any) -> Set[str]:
    """The question ids an answer may use: the draft's and the published
    version's, as on the submission path."""
    return answer_ids(draft, published)


def check_submission(
    published: Any,
    draft: Any,
    answers: Mapping[str, Any],
    hidden_values: Optional[Mapping[str, Any]],
    *,
    form_id: str,
    today: Optional[str] = None,
    known_ids: Optional[Set[str]] = None,
) -> SubmissionCheck:
    """Check ``answers`` (plain answer dicts keyed by question id) against the
    published version of a form, as a respondent's submission is checked.
    ``draft``: the working copy, used only to drop calculations that exist only
    there and for the ids answers may use. Never raises for a failed check."""
    work: Dict[str, Any] = dict(answers)
    problems = validate_group_answers(published, work)
    if problems:
        return SubmissionCheck(work, None, [Problem(None, GROUP_INVALID)])
    work = drop_hidden_group_answers(published, work)
    work = drop_draft_calculations(work, draft, published)
    ids = known_ids if known_ids is not None else answer_ids(draft, published)
    try:
        work, locked = calculate_and_check(
            published,
            work,
            form_id,
            hidden_values=dict(hidden_values) if hidden_values else None,
            today=respondent_today(today),
            known_ids=ids,
            with_locked=True,
            enforce=True,
        )
    except HTTPException as refused:
        return SubmissionCheck(work, None, _problems_of(refused))
    ending = reached_ending_id(published, work)
    date_problems = validate_date_rule_answers(published, work, today=None, skip=locked)
    if date_problems:
        return SubmissionCheck(work, ending, [Problem(None, DATE_RULE)])
    return SubmissionCheck(work, ending, [])
