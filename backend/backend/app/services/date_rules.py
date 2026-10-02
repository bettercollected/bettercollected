"""Date rules: server-side checks of date answers.

A date question may carry ``properties.date_rules`` (``DateRule`` in
``common/models/standard_form.py``): its answer must be before / after / on
or before / on or after a fixed date, today, or the answer of another date
question. The webapp applies the same rules while the form is filled
(``webapp/src/utils/date-rules.ts`` — keep the two in step); these checks
make sure a crafted submission or edit cannot store a date the creator ruled
out.

- Dates are calendar dates (``YYYY-MM-DD``) and are compared as strings of
  that shape, never as instants.
- A rule on another question applies only when that question is answered
  (with a valid date) and not hidden by logic; a question hidden by logic is
  not checked at all. Same as the webapp.
- "Today" is the respondent's local day, which the server cannot know: it is
  accepted anywhere between yesterday and tomorrow in UTC (every time zone's
  today lies in that range). On a response edit, "today" is the day the
  response was first submitted, so a later edit of another answer is not
  refused because time has passed.
- Inside a repeating group, a rule on a sibling compares the answers of the
  same item.
"""

import datetime as dt
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from common.models.standard_form import (
    StandardForm,
    StandardFormFieldType,
    is_iso_date,
)

from backend.app.services.repeating_groups import (
    _as_dict,
    group_items,
    is_hidden_by_logic,
    iter_repeating_groups,
)

DATE = StandardFormFieldType.DATE.value

COMPARISON_WORDS = {
    "before": "before",
    "after": "after",
    "on_or_before": "on or before",
    "on_or_after": "on or after",
}

# (earliest, latest) possible "today" of the respondent, as YYYY-MM-DD.
TodayRange = Tuple[str, str]


def today_range(reference: Optional[dt.date] = None) -> TodayRange:
    """The respondent's possible "today": one day either side of the UTC
    date (``reference`` defaults to now)."""
    day = reference or dt.datetime.now(dt.timezone.utc).date()
    return (
        (day - dt.timedelta(days=1)).isoformat(),
        (day + dt.timedelta(days=1)).isoformat(),
    )


def is_violated(value: str, comparison: str, bound: str) -> bool:
    """Does the date ``value`` break "must be <comparison> ``bound``"?"""
    if comparison == "before":
        return not value < bound
    if comparison == "after":
        return not value > bound
    if comparison == "on_or_before":
        return not value <= bound
    if comparison == "on_or_after":
        return not value >= bound
    return False


def display_date(value: str) -> str:
    """``2026-03-12`` -> ``12 Mar 2026`` (same as the webapp's message)."""
    day = dt.date.fromisoformat(value)
    return f"{day.day} {day.strftime('%b')} {day.year}"


def _type_value(field_type: Any) -> Optional[str]:
    return getattr(field_type, "value", field_type)


def _title(field: Any) -> str:
    title = getattr(field, "title", None)
    if isinstance(title, str) and title.strip():
        return title.strip()
    return "a date question"


def _date_value(answer: Any) -> Optional[str]:
    answer = _as_dict(answer)
    if not isinstance(answer, dict):
        return None
    value = answer.get("date")
    return value if is_iso_date(value) else None


def _rules(field: Any) -> List[Any]:
    properties = getattr(field, "properties", None)
    return list((getattr(properties, "date_rules", None) if properties else None) or [])


def _check_field(
    field: Any,
    answers: Dict[str, Any],
    siblings: Dict[str, Any],
    today: TodayRange,
) -> List[str]:
    """Problems with one date question's answer against its rules.
    ``answers`` is the scope the question is answered in (the item's
    answers layered over the form's inside a repeating group); ``siblings``
    the questions a rule may reference in that scope."""
    rules = _rules(field)
    if not rules or _type_value(field.type) != DATE:
        return []
    raw = answers.get(field.id)
    if raw is None or is_hidden_by_logic(field, answers):
        return []
    value = _date_value(raw)
    if value is None:
        raw = _as_dict(raw)
        if not isinstance(raw, dict) or raw.get("date") in (None, ""):
            return []
        return [f"The answer to '{_title(field)}' is not a valid date (YYYY-MM-DD)."]
    problems = []
    for rule in rules:
        comparison = rule.comparison
        if rule.target == "date":
            bound, what = rule.date, display_date(rule.date)
        elif rule.target == "today":
            # The most lenient "today" of any time zone.
            bound = today[0] if comparison in ("after", "on_or_after") else today[1]
            what = "today"
        else:
            ref = siblings.get(rule.field_id)
            if ref is None or _type_value(ref.type) != DATE:
                continue
            if is_hidden_by_logic(ref, answers):
                continue
            bound = _date_value(answers.get(ref.id))
            if bound is None:
                continue
            what = f"'{_title(ref)}' ({display_date(bound)})"
        if is_violated(value, comparison, bound):
            problems.append(
                f"'{_title(field)}' must be {COMPARISON_WORDS[comparison]} {what}."
            )
    return problems


def _page_questions(form: StandardForm) -> List[Any]:
    questions = []
    for top in form.fields or []:
        if _type_value(top.type) == StandardFormFieldType.SLIDE.value:
            questions.extend((top.properties.fields if top.properties else None) or [])
        else:
            questions.append(top)
    return questions


def validate_date_rule_answers(
    form: StandardForm,
    answers: Any,
    today: Optional[TodayRange] = None,
    changed: Optional[Iterable[str]] = None,
) -> List[str]:
    """Human-readable problems with the submitted date answers.

    ``changed`` (a response edit): only rules whose question, referenced
    question or repeating group is among these answer keys are checked, so
    an answer that was valid when submitted never blocks an unrelated edit.
    """
    if form is None or not isinstance(answers, dict):
        return []
    answers = {k: _as_dict(v) for k, v in answers.items()}
    today = today or today_range()
    changed_ids: Optional[Set[str]] = set(changed) if changed is not None else None

    def relevant(field: Any, extra: Iterable[str] = ()) -> bool:
        if changed_ids is None:
            return True
        ids = {field.id, *extra}
        ids.update(r.field_id for r in _rules(field) if r.field_id)
        return bool(ids & changed_ids)

    problems: List[str] = []
    questions = _page_questions(form)
    top_level = {q.id: q for q in questions if q.id}
    for question in questions:
        if _rules(question) and relevant(question):
            problems.extend(_check_field(question, answers, top_level, today))

    for group in iter_repeating_groups(form):
        children = (group.properties.fields if group.properties else None) or []
        ruled = [c for c in children if _rules(c)]
        if not ruled or group.id not in answers:
            continue
        if is_hidden_by_logic(group, answers):
            continue
        siblings = {c.id: c for c in children if c.id}
        label = group.properties.repeat.item_label or "Item"
        for position, item in enumerate(group_items(answers.get(group.id)), start=1):
            # Like the webapp's item scope: the item's answers replace the
            # form's under the child ids, absent ones stay absent.
            scope = {k: v for k, v in answers.items() if k not in siblings}
            scope.update({k: _as_dict(v) for k, v in item.items()})
            for child in ruled:
                if not relevant(child, (group.id,)):
                    continue
                problems.extend(
                    f"{label} {position}: {problem}"
                    for problem in _check_field(child, scope, siblings, today)
                )
    return problems
