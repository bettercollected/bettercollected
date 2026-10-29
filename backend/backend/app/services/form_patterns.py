"""The answer patterns on a form, checked when a person saves it.

A question's pattern (``validations.regex``) is matched on the server with
RE2 (linear time), but the respondent's browser matches it with a
backtracking engine: ``^(a+)+$`` can freeze a tab on one unlucky answer. So a
save refuses a pattern whose shape can do that (``common.form_spec.
pattern_safety``, the rule the form spec, the AI ops and the importer apply
through ``checked_pattern``; the webapp builder shows the same message).

- A pattern the stored draft already holds exactly is kept, so a form saved
  before this check still saves and can be edited; the respondent form never
  hands such a pattern to the browser's engine
  (``webapp/src/utils/answer-rules.ts``), and the server still checks it.
- A copy (a template) drops the pattern instead of refusing: nobody can fix
  it by hand there.
- A pattern that does not compile is no hazard (as before: it is stored, the
  builder says it is not checked).
- Otherwise 422 ``unsafe_pattern`` with the question ids, never the pattern.
"""

import re
from http import HTTPStatus
from typing import Dict, Iterable, List, Optional, Set

from common.form_spec.pattern_safety import HAZARD_MESSAGES, UNPARSEABLE, pattern_hazard
from common.models.standard_form import StandardForm, StandardFormField

from backend.app.exceptions import HTTPException

ERROR_CODE = "unsafe_pattern"


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


def _no_engine_runs(pattern: str, hazard: str) -> bool:
    """A pattern that is no pattern at all (the builder saves one while it is
    being typed, ``(a+``): it does not compile, so nothing evaluates it."""
    if hazard != UNPARSEABLE:
        return False
    try:
        re.compile(pattern)
    except re.error:
        return True
    return False


def check_form_patterns(
    form: StandardForm,
    stored: Optional[StandardForm] = None,
    drop: bool = False,
) -> None:
    """Refuse (422) or, with ``drop``, remove every pattern of ``form`` that
    can freeze a browser, except the ones ``stored`` already holds."""
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
        hazard = pattern_hazard(pattern.strip())
        if hazard is None or _no_engine_runs(pattern.strip(), hazard):
            continue
        if drop:
            field.validations.regex = None
        else:
            refused.append({"fieldId": str(field.id), "hazard": hazard})
    if refused:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": HAZARD_MESSAGES[refused[0]["hazard"]],
                "errors": refused,
            },
        )
