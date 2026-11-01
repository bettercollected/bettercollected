"""Conditions of form actions (a webhook, an email action): the action runs
only when a condition on the submitted answers holds.

The model is the one the form's logic and field rules use
(``FieldLogicCondition``, folded with ``AND`` / ``OR``) and so is the
evaluator (``repeating_groups.evaluate_conditions``): there is one reading of a
comparison on the server, and the webapp's builder writes the same shape.

- **Saved** only when every condition reads a respondent-facing question of the
  form's page (never an internal one, never a file, never a question inside a
  repeating group: use the group itself with ``COUNT`` / ``ANY`` / ``ALL``), with
  a known comparison; at most ``CONDITIONS_MAX``. The question's type is written
  from the form, never taken from the request.
- **Evaluated** by the server when the submission is queued, on the answers the
  submission stored (the submit-normalised ones: calculated values the server
  computed, hidden values never), in memory. The answers are not kept. A
  condition that cannot be read (the question was removed since) does not hold:
  the action does not run (``condition_invalid``), it never runs on a guess.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from backend.app.exceptions import HTTPException
from backend.app.schemas.webhook import ActionCondition
from backend.app.services.registration import body as body_builder
from backend.app.services.repeating_groups import (
    ADDRESS_COMPARISONS,
    DATE_RANGE_COMPARISONS,
    TAGS_COMPARISONS,
    evaluate_conditions,
    logic_sources,
)
from backend.app.services.field_rules import COMPARISONS, GROUP_MODES

CONDITIONS_MAX = 10
VALUE_MAX_BYTES = 2000
# a text a condition reads is cut here, as field rules do
TEXT_MAX = 10_000
NOT_MET = "condition_not_met"
INVALID = "condition_invalid"
ERROR_CODE = "invalid_condition"
# what a condition on these questions may ask (the form's logic and the AI ops
# refuse the rest; one that was saved would never fire)
ALLOWED_COMPARISONS = {
    "tags": TAGS_COMPARISONS,
    "date_range": DATE_RANGE_COMPARISONS,
    "address": ADDRESS_COMPARISONS,
}


def _comparison_fits(question_type: Optional[str], comparison: Any) -> bool:
    allowed = ALLOWED_COMPARISONS.get(question_type or "")
    return allowed is None or comparison in allowed


def _refused(message: str) -> HTTPException:
    return HTTPException(
        HTTPStatus.UNPROCESSABLE_ENTITY,
        content={"code": ERROR_CODE, "message": message},
    )


def checked_condition(form: Any, condition: Optional[ActionCondition]) -> Optional[ActionCondition]:
    """``condition`` as stored (types written from the form), ``None`` for no
    condition; raises 422 ``invalid_condition`` for one that cannot be kept."""
    if condition is None or not condition.conditions:
        return None
    if len(condition.conditions) > CONDITIONS_MAX:
        raise _refused(f"At most {CONDITIONS_MAX} conditions.")
    index = body_builder.variables_of(form)
    kept = []
    for item in condition.conditions:
        variable = index.get(item.field_id or "")
        if (
            variable is None
            or variable.kind != "question"
            or variable.type == "file_upload"
            or not variable.supported
        ):
            raise _refused("A condition reads a question this form does not have.")
        if item.comparison not in COMPARISONS:
            raise _refused("A condition has a comparison that is not known.")
        if not _comparison_fits(variable.type, item.comparison):
            raise _refused(
                f"A condition on a {variable.type.replace('_', ' ')} question uses "
                f"one of {', '.join(ALLOWED_COMPARISONS[variable.type])}."
            )
        try:
            size = len(json.dumps(item.value, default=str))
        except (TypeError, ValueError):
            size = VALUE_MAX_BYTES + 1
        if size > VALUE_MAX_BYTES:
            raise _refused("A condition's value is too long.")
        change = {"field_type": variable.type}
        if variable.type == "group":
            if item.group_mode not in GROUP_MODES:
                raise _refused(
                    "A repeating group needs COUNT (items), ANY or ALL (a question in the items)."
                )
            if item.group_mode == "COUNT":
                change["child_field_id"] = None
                change["child_field_type"] = None
            else:
                child = index.get(f"{variable.source}.{item.child_field_id or ''}")
                if child is None or not child.supported:
                    raise _refused("A condition reads a question the group does not have.")
                change["child_field_type"] = child.type
                if not _comparison_fits(child.type, item.comparison):
                    raise _refused(
                        f"A condition on a {child.type.replace('_', ' ')} question "
                        f"uses one of {', '.join(ALLOWED_COMPARISONS[child.type])}."
                    )
        else:
            if item.group_mode:
                raise _refused("Only a repeating group takes COUNT, ANY or ALL.")
            change["child_field_id"] = None
            change["child_field_type"] = None
        kept.append(item.model_copy(update=change))
    return ActionCondition(operator=condition.operator, conditions=kept)


def conditions_hold(
    condition: Optional[ActionCondition], form: Any, answers: Dict[str, Any]
) -> Tuple[bool, Optional[str]]:
    """``(runs, code)``: ``code`` says why not (``condition_not_met``, or
    ``condition_invalid`` for one that cannot be read) and is ``None`` when the
    action runs."""
    if condition is None or not condition.conditions:
        return True, None
    try:
        index = body_builder.variables_of(form)
        for item in condition.conditions:
            variable = index.get(item.field_id or "")
            if variable is None or variable.kind != "question":
                return False, INVALID
        sources = logic_sources(getattr(form, "fields", None))
        held = evaluate_conditions(
            condition.operator,
            list(condition.conditions),
            answers if isinstance(answers, dict) else {},
            sources,
            TEXT_MAX,
        )
    except Exception:  # noqa: BLE001 - an unreadable condition never runs the action
        return False, INVALID
    return (True, None) if held else (False, NOT_MET)


def condition_names(condition: Optional[ActionCondition]) -> List[str]:
    return [c.field_id for c in (condition.conditions if condition else []) if c.field_id]
