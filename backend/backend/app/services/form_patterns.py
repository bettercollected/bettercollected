"""The answer patterns on a form, checked when a person saves it.

A question's pattern (``validations.regex``) is matched on the server with
RE2, in linear time (``services/answer_validation.py``); the respondent's
browser never runs it. A pattern RE2 cannot use (a lookaround, a
backreference, a mistake) would be skipped there, so a save refuses it with
the rule the spec, the ops and the import apply through ``checked_pattern``.

- A pattern the stored draft already holds exactly is kept, so a form saved
  before this check still saves and can be edited.
- A copy (a template) drops the pattern instead of refusing: nobody can fix
  it by hand there.
- Otherwise 422 ``invalid_pattern`` with the reason and the question ids.
"""

from http import HTTPStatus
from typing import Dict, Iterable, List, Optional, Set

from common.form_spec.models import PATTERN_MAX_LENGTH, checked_pattern
from common.form_spec.re2_patterns import re2_problem
from common.models.standard_form import StandardForm, StandardFormField

from backend.app.exceptions import HTTPException

ERROR_CODE = "invalid_pattern"


def _walk(fields: Optional[Iterable[StandardFormField]]):
    for field in fields or []:
        if field is None:
            continue
        yield field
        if field.properties is not None:
            yield from _walk(field.properties.fields)


def _pattern(field: StandardFormField) -> Optional[str]:
    rules = field.validations
    regex = rules.regex if rules is not None else None
    return regex if isinstance(regex, str) and regex.strip() else None


def pattern_problem(pattern: str) -> Optional[str]:
    """Why a pattern cannot be saved, or None."""
    try:
        checked_pattern(pattern)
    except ValueError as error:
        return str(error)
    return None


def pattern_reason(pattern: str) -> Optional[str]:
    """The short reason a pattern cannot be saved (RE2's own words, or the
    length rule), or None."""
    pattern = pattern.strip()
    if len(pattern) > PATTERN_MAX_LENGTH:
        return f"A pattern can be at most {PATTERN_MAX_LENGTH} characters."
    return re2_problem(pattern)


def check_form_patterns(
    form: StandardForm,
    stored: Optional[StandardForm] = None,
    drop: bool = False,
) -> None:
    """Refuse (422) or, with ``drop``, remove every pattern of ``form`` that
    cannot be saved, except the ones ``stored`` already holds."""
    keep: Set[str] = {
        pattern
        for pattern in (
            _pattern(field) for field in _walk(stored.fields if stored else None)
        )
        if pattern
    }
    refused: List[Dict[str, str]] = []
    for field in _walk(form.fields):
        pattern = _pattern(field)
        if pattern is None or pattern in keep:
            continue
        problem = pattern_problem(pattern)
        if problem is None:
            continue
        if drop:
            field.validations.regex = None
        else:
            refused.append({"fieldId": str(field.id), "message": problem})
    if refused:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": refused[0]["message"],
                "errors": refused,
            },
        )
