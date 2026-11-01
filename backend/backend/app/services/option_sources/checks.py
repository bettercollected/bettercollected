"""What a form may say about option sources when it is saved.

``structural_problems`` is the shape: which questions may have a source, that
it excludes the question's own options, that a parent is an earlier choice
question, that only ``is_empty`` / ``is_not_empty`` conditions read such a
question. ``ensure_valid_structure`` refuses them on every save path (422
``option_source_invalid``).

``ensure_option_sources_allowed`` is the switch (``OPTION_SOURCES_ENABLED``):
while it is off a source that is new or changed against the stored form is
refused (422 ``option_sources_disabled``); one that is stored as it is passes.
Where nobody can be asked whether the saver may read another form's answers
(``persist_form``: chat, MCP, imports), a new or changed ``form_answers``
source is refused outright (``answers_ok=False``, 422
``option_source_forbidden``): that kind is only set by a save that checks the
caller's access to the source form (``OptionSourceService.ensure_resolved``).

``strip_option_sources`` removes every source (a template copied to another
workspace and a provider import never bring one).
"""

from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from backend.app.exceptions import HTTPException
from backend.app.services.option_sources import read
from backend.app.services.option_sources.mode import (
    DISABLED_CODE,
    DISABLED_MESSAGE,
    option_sources_enabled,
)

INVALID_CODE = "option_source_invalid"
FORBIDDEN_CODE = "option_source_forbidden"
PROBLEMS_MAX = 50
# the only comparisons that read a question whose options come from a source
EMPTY_COMPARISONS = frozenset({"is_empty", "is_not_empty"})


def _problem(field_id: str, message: str) -> Dict[str, str]:
    return {"fieldId": field_id, "message": message}


def piece(source: Dict[str, Any]) -> Tuple[Any, ...]:
    """What makes a source the same one."""
    return (
        source.get("kind"),
        source.get("list_id"),
        source.get("parent_field_id"),
        source.get("form_id"),
        source.get("question_id"),
    )


def pieces(form: Any) -> Dict[str, Tuple[Any, ...]]:
    """``{question id: piece}`` of every sourced question (a document may
    carry one id twice: the last one counts, as everywhere)."""
    return {
        str(read.get(field, "id")): piece(source)
        for field, source in read.sourced_questions(form)
    }


def _comparison(condition: Dict[str, Any]) -> str:
    value = condition.get("comparison")
    return str(getattr(value, "value", value) or "").lower()


def _conditions(node: Any, sourced: set) -> List[str]:
    """Ids of sourced questions that a condition in ``node`` reads with a
    comparison other than is_empty / is_not_empty (iterative)."""
    found: List[str] = []
    pending = [node]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            field_id = item.get("field_id", item.get("fieldId"))
            if (
                isinstance(field_id, str)
                and field_id in sourced
                and "comparison" in item
                and _comparison(item) not in EMPTY_COMPARISONS
            ):
                found.append(field_id)
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return found


def structural_problems(form: Any) -> List[Dict[str, str]]:
    """Everything wrong with the sources of ``form``, as ``{fieldId,
    message}`` (at most ``PROBLEMS_MAX``)."""
    problems: List[Dict[str, str]] = []
    sourced = {
        str(read.get(field, "id")): (field, source, top)
        for field, top in read.every_field(form)
        for source in [read.source_dict(field)]
        if source is not None
    }
    if not sourced:
        return problems
    order = [str(read.get(q, "id")) for q in read.page_questions(form)]
    choice_ids = {
        str(read.get(q, "id"))
        for q in read.page_questions(form)
        if read.field_type(q) in read.CHOICE_TYPES
    }
    for field_id, (field, source, top) in sourced.items():
        kind = source.get("kind")
        properties = read.props(field)
        if read.field_type(field) not in read.CHOICE_TYPES:
            problems.append(
                _problem(
                    field_id,
                    "Only a dropdown or a multiple choice question can take its options from a source.",
                )
            )
        if not top:
            problems.append(
                _problem(
                    field_id,
                    "A question inside a group cannot take its options from a source.",
                )
            )
        if read.get(field, "internal"):
            problems.append(
                _problem(
                    field_id,
                    "An internal question cannot take its options from a source.",
                )
            )
        if kind == "list":
            if (
                not source.get("list_id")
                or source.get("form_id")
                or source.get("question_id")
            ):
                problems.append(
                    _problem(field_id, "A list source names a list and nothing else.")
                )
        elif kind == "form_answers":
            if not source.get("form_id") or not source.get("question_id"):
                problems.append(
                    _problem(
                        field_id, "A form-answers source names a form and a question."
                    )
                )
            if source.get("list_id") or source.get("parent_field_id"):
                problems.append(
                    _problem(
                        field_id,
                        "A form-answers source takes no list and no parent question.",
                    )
                )
        else:
            problems.append(
                _problem(
                    field_id, "The source is not a list or another form's answers."
                )
            )
        if read.get(properties, "choices"):
            problems.append(
                _problem(
                    field_id,
                    "A question with a source has no options of its own. Remove them first.",
                )
            )
        if read.get(properties, "option_filter") is not None:
            problems.append(
                _problem(field_id, "An option filter cannot be combined with a source.")
            )
        for rule in read.get(properties, "rules") or []:
            then = read.get(rule, "then")
            if read.get(then, "set_value") is not None:
                problems.append(
                    _problem(
                        field_id,
                        "A rule cannot set the value of a question whose options come from a source.",
                    )
                )
                break
        parent = source.get("parent_field_id")
        if parent:
            if parent == field_id or parent not in choice_ids:
                problems.append(
                    _problem(
                        field_id,
                        "The parent must be another dropdown or multiple choice question.",
                    )
                )
            elif (
                order.index(parent) > order.index(field_id)
                if field_id in order
                else False
            ):
                problems.append(
                    _problem(field_id, "The parent question must come before this one.")
                )
    # conditions anywhere in the form that compare with a value
    if hasattr(form, "model_dump"):
        dumped = form.model_dump(exclude_none=True)
    else:
        dumped = form
    for field_id in dict.fromkeys(_conditions(get_fields(dumped), set(sourced))):
        problems.append(
            _problem(
                field_id,
                "A condition on a question with a source can only test whether it is answered.",
            )
        )
    return problems[:PROBLEMS_MAX]


def get_fields(form: Any) -> Any:
    return read.get(form, "fields") or []


def ensure_valid_structure(form: Any) -> None:
    problems = structural_problems(form)
    if problems:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": INVALID_CODE,
                "message": problems[0]["message"],
                "errors": problems,
            },
        )


def new_or_changed(form: Any, existing: Any = None) -> List[str]:
    """Ids of the questions whose source ``existing`` (the stored form, or
    None) does not hold exactly as it is now."""
    stored = pieces(existing) if existing is not None else {}
    return [
        field_id
        for field_id, now in pieces(form).items()
        if stored.get(field_id) != now
    ]


def ensure_option_sources_allowed(
    form: Any, existing: Any = None, answers_ok: bool = True
) -> None:
    """While the switch is off, refuse a new or changed source (422
    ``option_sources_disabled``). With ``answers_ok`` False, also refuse a new
    or changed ``form_answers`` source (422 ``option_source_forbidden``)."""
    changed = new_or_changed(form, existing)
    if not changed:
        return
    if not option_sources_enabled():
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": DISABLED_CODE,
                "message": DISABLED_MESSAGE,
                "errors": [
                    {"fieldId": field_id} for field_id in changed[:PROBLEMS_MAX]
                ],
            },
        )
    if answers_ok:
        return
    now = pieces(form)
    refused = [f for f in changed if now[f][0] == "form_answers"]
    if refused:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": FORBIDDEN_CODE,
                "message": "Options from another form's answers are set in the form "
                "builder, where access to that form is checked.",
                "errors": [
                    {"fieldId": field_id} for field_id in refused[:PROBLEMS_MAX]
                ],
            },
        )


def strip_option_sources(form: Any, kinds: Optional[Tuple[str, ...]] = None) -> int:
    """Remove the sources of the form (of these ``kinds``, or every one), in
    place; returns how many went."""
    removed = 0
    for field, _ in read.every_field(form):
        properties = read.props(field)
        source = read.source_dict(field)
        if properties is None or source is None:
            continue
        if kinds is not None and source.get("kind") not in kinds:
            continue
        if isinstance(properties, dict):
            properties["option_source"] = None
        else:
            properties.option_source = None
        removed += 1
    return removed
