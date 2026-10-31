"""Choice-level logic: which options of a choice question respondents are
offered, and the save checks that keep it enforceable.

A choice question (single or multiple choice, dropdown) may

- give an option its own ``logic`` (``choices[].logic``, the question-level
  ``FieldLogic``: ``SHOW`` = offered only while the conditions hold, ``HIDE``
  = offered unless they hold), and
- filter its options by an earlier choice question's answer
  (``properties.option_filter``, ``OptionFilter``): the options offered are
  those the chosen options of that question map to (the union over a
  multiple choice's selection). Without an answer to it (or with only
  "Other" text) nothing is filtered; a chosen option with no row offers
  nothing.

An option is **available** when its own logic allows it and the filter lets
it through. Spec: docs/spec/README.md "Choice logic". The webapp's twin is
``src/utils/option-logic.ts``; the shared cases in
``docs/spec/option-logic.cases.json`` run on both sides, so change one
evaluator only together with the other. The server is the authority.

- **Enforcement** (``answer_validation``): an answer that selects an option
  that is not available is refused (``hidden_option``) on a question the
  respondent is asked (on their path, not hidden by logic), on submit and on
  the respondent's own edit. The respondent page clears such a selection
  itself, with a polite notice; the server never deletes an answer silently.
  Answers to hidden questions and skipped pages stay kept, as ever.
- **No dead ends:** a question with nothing available (and no "Other") is
  never required, and ``minChoices`` is held to what is available. A
  question whose value a field rule sets or locks is not filtered: the
  form's own value is not the respondent's to fix.
- **Reading answers:** like ``logic``, the answers as given, hidden or not.
  A condition or filter that reads something the form does not have (a
  removed question, an internal one, one the question's group scope does not
  reach) is not active: the option is offered.
- **Saving** (``option_logic_problems``): only page-level choice questions
  carry option logic; a condition or filter reads an **earlier**,
  respondent-facing question (never the question itself), which keeps the
  evaluation acyclic; filter ids name real options; caps below. A builder
  save repairs what a structural edit broke (``prune_option_logic``);
  documents, the API and ops refuse (422 ``invalid_option_logic``).

**The switch:** ``CHOICE_LOGIC_ENABLED`` (default off, until an operator turns it
on): while it is off every write that brings new or changed option logic or a
filter is refused (422 ``choice_logic_disabled``: builder save, spec and API,
edit operations of both kinds, templates, the AI and MCP paths; a provider
import never brings any), and what is stored is kept and still enforced.

Creator conditions are untrusted: caps keep one response's evaluation
bounded (``OPTION_CONDITIONS_MAX`` per option,
``OPTION_LOGIC_OPTIONS_MAX`` options on a question with option logic,
``FORM_OPTION_CONDITIONS_MAX`` conditions and ``FORM_OPTION_FILTERS_MAX``
filters in a form), the replay reads no more than these, and the selected
ids it compares are de-duplicated, so cost does not grow with the size of
an answer. Callers run it with the rest of answer validation, off the event
loop.
"""

import json
from dataclasses import dataclass, field as dataclass_field
from types import SimpleNamespace
from http import HTTPStatus
from typing import Any, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from common.models.standard_form import (
    FORM_OPTION_CONDITIONS_MAX,
    FORM_OPTION_FILTERS_MAX,
    OPTION_CONDITIONS_MAX,
    OPTION_FILTER_PAIRS_MAX,
    OPTION_LOGIC_OPTIONS_MAX,
    FieldLogic,
)

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.repeating_groups import (
    evaluate_conditions,
    group_items,
    logic_sources,
)

ERROR_CODE = "invalid_option_logic"
COSTLY_CODE = "option_logic_too_costly"
# What one response may spend on evaluating option conditions, in units of
# work: a condition costs 1, plus the options chosen in the choice question it
# reads (each is looked up once), or, for ANY / ALL on a repeating group, the
# items it holds (at most 50) and the options chosen in the question it reads
# in each. Far above what a form within the caps needs: a save refuses a form
# whose worst case (every option chosen, every group at 50 items) is over it,
# so respondents never meet the limit; one that is over anyway (data no save
# accepted) refuses the response, never half checks it.
OPTION_LOGIC_COST_PER_RESPONSE = 500_000
_GROUP_ITEMS_MAX = 50
# The rule code of an answer that selects an unavailable option.
HIDDEN_OPTION = "hidden_option"

CHOICE_TYPES = {"multiple_choice", "dropdown"}
PAGE = "slide"
GROUP = "group"
ACTIONS = ("SHOW", "HIDE")
GROUP_MODES = ("COUNT", "ANY", "ALL")
PROBLEMS_MAX = 50


# ---------------------------------------------------------------------------
# Reading the form (models or plain dicts)
# ---------------------------------------------------------------------------


def _get(item: Any, name: str, default: Any = None) -> Any:
    if item is None:
        return default
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def _type(field: Any) -> Optional[str]:
    kind = _get(field, "type")
    return getattr(kind, "value", kind)


def _props(field: Any) -> Any:
    return _get(field, "properties")


def _choices(field: Any) -> List[Any]:
    return list(_get(_props(field), "choices") or [])


def _filter(field: Any) -> Any:
    return _get(_props(field), "option_filter")


def _option_logic(choice: Any) -> Any:
    logic = _get(choice, "logic")
    if logic is None or not _get(logic, "action") or not _get(logic, "conditions"):
        return None
    return logic


def has_option_logic(field: Any) -> bool:
    """Does a question carry option logic or an option filter?"""
    return _filter(field) is not None or any(
        _option_logic(choice) is not None for choice in _choices(field)
    )


def _pages(form: Any) -> List[Any]:
    return [f for f in (_get(form, "fields") or []) if _type(f) == PAGE]


def _page_questions(form: Any) -> List[Any]:
    """Page-level questions in form order (a group counts as one)."""
    found: List[Any] = []
    for page in _pages(form):
        found.extend(_get(_props(page), "fields") or [])
    return found


def _group_children(group: Any) -> List[Any]:
    return list(_get(_props(group), "fields") or [])


def _is_option_target(field: Any) -> bool:
    return _type(field) in CHOICE_TYPES and not _get(field, "internal")


def form_has_option_logic(form: Any) -> bool:
    """Does any question of the form carry option logic or a filter? (Walks
    pages and groups; cheap for the form most responses are for.)"""
    for field in _page_questions(form):
        if has_option_logic(field):
            return True
        if _type(field) == GROUP and any(
            has_option_logic(child) for child in _group_children(field)
        ):
            return True
    return False


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _as_dict(value: Any) -> Any:
    return value.model_dump() if hasattr(value, "model_dump") else value


def selected_option_ids(answer: Any, field: Any) -> List[str]:
    """The option ids an answer to a choice question selects, de-duplicated
    and only those the question has (the text typed as "Other" is not an
    option)."""
    answer = _as_dict(answer)
    if not isinstance(answer, dict):
        return []
    known = {
        str(_get(choice, "id")) for choice in _choices(field) if _get(choice, "id")
    }
    picked: List[str] = []
    many = _as_dict(answer.get("choices"))
    one = _as_dict(answer.get("choice"))
    values: List[Any] = []
    if isinstance(many, dict) and isinstance(many.get("values"), list):
        values.extend(many["values"])
    if isinstance(one, dict) and one.get("value") not in (None, ""):
        values.append(one["value"])
    seen: Set[str] = set()
    for value in values:
        if isinstance(value, str) and value in known and value not in seen:
            seen.add(value)
            picked.append(value)
    return picked


@dataclass
class OptionStates:
    """What the options of the form's questions are for one set of
    answers. Keys are page question ids."""

    # option ids not available
    hidden: Dict[str, FrozenSet[str]] = dataclass_field(default_factory=dict)
    # questions with no available option and no "Other" (never required)
    none_left: Set[str] = dataclass_field(default_factory=set)
    # how many options a question offers (with "Other"), where it has logic
    offered: Dict[str, int] = dataclass_field(default_factory=dict)

    def hidden_options(self, field_id: str) -> FrozenSet[str]:
        return self.hidden.get(field_id, frozenset())

    def is_none_left(self, field_id: str) -> bool:
        return field_id in self.none_left

    def min_choices(self, field: Any, static: Optional[int]) -> Optional[int]:
        """``minChoices`` held to what the question offers."""
        offered = self.offered.get(str(_get(field, "id")))
        if static is None or offered is None:
            return static
        return min(static, offered)


NO_OPTION_LOGIC = OptionStates()


class OptionLogicTooCostly(Exception):
    """One response's option conditions went over
    ``OPTION_LOGIC_COST_PER_RESPONSE``."""


@dataclass
class _Budget:
    """What one response may read: conditions and filters, as the form caps
    allow (more than that exists only in data no save accepted)."""

    conditions: int = FORM_OPTION_CONDITIONS_MAX
    filters: int = FORM_OPTION_FILTERS_MAX
    cost: int = OPTION_LOGIC_COST_PER_RESPONSE

    def charge(self, units: int) -> None:
        self.cost -= units
        if self.cost < 0:
            raise OptionLogicTooCostly()

    def take_conditions(self, wanted: int) -> bool:
        if wanted > self.conditions:
            return False
        self.conditions -= wanted
        return True

    def take_filter(self) -> bool:
        if self.filters <= 0:
            return False
        self.filters -= 1
        return True


def _dangling(conditions: Iterable[Any], owner: str, sources: Dict[str, Any]) -> bool:
    for condition in conditions:
        source = str(_get(condition, "field_id") or "")
        if not source or source == owner or source not in sources:
            return True
        if _get(condition, "group_mode") in ("ANY", "ALL"):
            child = _get(condition, "child_field_id")
            if not child or str(child) not in sources:
                return True
    return False


def _allowed_by_filter(
    flt: Any, owner: str, answers: Dict[str, Any], sources: Dict[str, Any]
) -> Optional[Set[str]]:
    """The option ids a filter lets through, or None when it filters nothing
    (its source is gone, is not a choice question, or has no selected
    option)."""
    source_id = str(_get(flt, "field_id") or "")
    source = sources.get(source_id)
    if source is None or source_id == owner or _type(source) not in CHOICE_TYPES:
        return None
    selected = set(selected_option_ids(answers.get(source_id), source))
    if not selected:
        return None
    allowed: Set[str] = set()
    for entry in list(_get(flt, "mapping") or [])[:OPTION_FILTER_PAIRS_MAX]:
        if _get(entry, "when") in selected:
            allowed.update(
                str(option)
                for option in list(_get(entry, "show") or [])[:OPTION_FILTER_PAIRS_MAX]
            )
    return allowed


def _indexed(source: Any) -> Any:
    """A choice question as a condition reads it: its options looked up once
    (``token_index``: option id -> what the option answers to: its id, text
    and label), so a condition costs the options chosen, not a search of the
    question's list for each."""
    index: Dict[str, List[str]] = {}
    for choice in _choices(source):
        choice_id = _get(choice, "id")
        if not choice_id:
            continue
        tokens: List[str] = []
        for token in (str(choice_id), _get(choice, "value"), _get(choice, "label")):
            if isinstance(token, bool):
                continue
            if isinstance(token, (str, int, float)) and token != "":
                text = str(token)
                if text not in tokens:
                    tokens.append(text)
        index[str(choice_id)] = tokens
    return SimpleNamespace(
        id=_get(source, "id"),
        type=_type(source),
        internal=False,
        properties=SimpleNamespace(choices=_choices(source)),
        token_index=index,
    )


def _bounded_answer(answer: Any, source: Any) -> Tuple[Any, int]:
    """A choice answer reduced to the options it really selects (each once,
    only options the question has; the text typed as "Other" stays), and how
    many that are."""
    answer = _as_dict(answer)
    if not isinstance(answer, dict):
        return answer, 0
    picked = selected_option_ids(answer, source)
    many = _as_dict(answer.get("choices"))
    one = _as_dict(answer.get("choice"))
    if isinstance(many, dict):
        return {"choices": {"values": picked, "other": many.get("other")}}, len(picked)
    other = one.get("other") if isinstance(one, dict) else None
    return (
        {"choice": {"value": picked[0] if picked else None, "other": other}},
        len(picked),
    )


class _Reading:
    """The answers and questions a condition reads. A choice question's answer
    is read as the options it really selects (each once, only options the
    question has) and its options are looked up once, so that the work of a
    condition follows the options chosen, never the size of an answer or of
    the question's list of options. The answers of a repeating group are read
    the same way, for at most 50 items."""

    def __init__(self, answers: Dict[str, Any], sources: Dict[str, Any]):
        self.answers = dict(answers)
        self.sources = dict(sources)
        # top-level choice question -> options chosen
        self.chosen: Dict[str, int] = {}
        # repeating group -> its items as read
        self.items: Dict[str, List[Dict[str, Any]]] = {}
        for key, source in sources.items():
            if _type(source) in CHOICE_TYPES:
                self.sources[key] = _indexed(source)
        for key, source in sources.items():
            kind = _type(source)
            if kind in CHOICE_TYPES:
                if isinstance(answers.get(key), dict):
                    self.answers[key], self.chosen[key] = _bounded_answer(
                        answers[key], source
                    )
            elif kind == GROUP:
                items = group_items(answers.get(key))[:_GROUP_ITEMS_MAX]
                read_items: List[Dict[str, Any]] = []
                for item in items:
                    read = dict(item)
                    for child in _group_children(source):
                        child_id = str(_get(child, "id"))
                        if _type(child) in CHOICE_TYPES and isinstance(
                            item.get(child_id), dict
                        ):
                            read[child_id], _ = _bounded_answer(item[child_id], child)
                    read_items.append(read)
                self.items[key] = read_items
                if isinstance(_as_dict(answers.get(key)), dict):
                    self.answers[key] = {
                        **_as_dict(answers.get(key)),
                        "items": read_items,
                    }

    def cost(self, conditions: Iterable[Any]) -> int:
        """The work of evaluating these conditions on these answers."""
        total = 0
        for condition in conditions:
            total += 1
            field_id = str(_get(condition, "field_id") or "")
            mode = _get(condition, "group_mode")
            if mode == "COUNT":
                continue
            if mode in ("ANY", "ALL"):
                child = str(_get(condition, "child_field_id") or "")
                for item in self.items.get(field_id, []):
                    total += 1 + _values_in(item.get(child))
            else:
                total += self.chosen.get(field_id, 0)
        return total


def _values_in(answer: Any) -> int:
    many = (
        _as_dict(answer).get("choices") if isinstance(_as_dict(answer), dict) else None
    )
    values = _as_dict(many).get("values") if isinstance(_as_dict(many), dict) else None
    return len(values) if isinstance(values, list) else 0


def worst_case_cost(form: Any) -> int:
    """The most a response can spend on the form's option conditions: every
    option of a question a condition reads chosen, every group it reads at
    50 items with every option chosen in each."""
    questions = _page_questions(form)
    by_id: Dict[str, Any] = {}
    for question in questions:
        if _get(question, "id"):
            by_id[str(_get(question, "id"))] = question
        if _type(question) == GROUP:
            for child in _group_children(question):
                if _get(child, "id"):
                    by_id.setdefault(str(_get(child, "id")), child)
    total = 0
    for question in questions:
        for choice in _choices(question):
            logic = _option_logic(choice)
            for condition in (
                (_get(logic, "conditions") or [])[:OPTION_CONDITIONS_MAX]
                if logic
                else []
            ):
                total += 1
                source = by_id.get(str(_get(condition, "field_id") or ""))
                mode = _get(condition, "group_mode")
                if source is None or mode == "COUNT":
                    continue
                if mode in ("ANY", "ALL"):
                    child = by_id.get(str(_get(condition, "child_field_id") or ""))
                    per_item = 1 + (
                        len(_choices(child)) if _type(child) in CHOICE_TYPES else 0
                    )
                    total += _GROUP_ITEMS_MAX * per_item
                elif _type(source) in CHOICE_TYPES:
                    total += len(_choices(source))
    return total


def _question_state(
    field: Any,
    reading: _Reading,
    budget: _Budget,
) -> Tuple[FrozenSet[str], int]:
    """``(hidden option ids, options offered)`` of one question."""
    owner = str(_get(field, "id"))
    answers, sources = reading.answers, reading.sources
    choices = _choices(field)[:OPTION_LOGIC_OPTIONS_MAX]
    flt = _filter(field)
    allowed = (
        _allowed_by_filter(flt, owner, answers, sources)
        if flt is not None and budget.take_filter()
        else None
    )
    hidden: Set[str] = set()
    for choice in choices:
        choice_id = _get(choice, "id")
        if not choice_id:
            continue
        choice_id = str(choice_id)
        if allowed is not None and choice_id not in allowed:
            hidden.add(choice_id)
            continue
        logic = _option_logic(choice)
        if logic is None:
            continue
        conditions = list(_get(logic, "conditions") or [])[:OPTION_CONDITIONS_MAX]
        if not budget.take_conditions(len(conditions)):
            continue
        if _dangling(conditions, owner, sources):
            continue
        budget.charge(reading.cost(conditions))
        met = evaluate_conditions(_get(logic, "operator"), conditions, answers, sources)
        if (_get(logic, "action") == "SHOW") != met:
            hidden.add(choice_id)
    return frozenset(hidden), len(choices) - len(hidden)


def _plain(answers: Any) -> Dict[str, Any]:
    if not isinstance(answers, dict):
        return {}
    return {str(key): _as_dict(value) for key, value in answers.items()}


def option_states(
    form: Any,
    answers: Any,
    locked: Iterable[str] = (),
) -> OptionStates:
    """The availability of the options of every page-level choice question
    that has option logic, for ``answers`` (as handed to validation).
    ``locked``: questions whose value a field rule sets or locks: not
    filtered."""
    questions = [
        field
        for field in _page_questions(form)
        if _is_option_target(field) and has_option_logic(field)
    ]
    if not questions:
        return NO_OPTION_LOGIC
    plain = _plain(answers)
    pages = _pages(form)
    sources = {
        key: field
        for key, field in logic_sources(pages).items()
        if not _get(field, "internal")
    }
    locked_ids = set(locked)
    budget = _Budget()
    reading = _Reading(plain, sources)
    states = OptionStates()
    for field in questions:
        field_id = str(_get(field, "id"))
        if field_id in locked_ids:
            continue
        hidden, offered = _question_state(field, reading, budget)
        if not hidden:
            continue
        other = bool(_get(_props(field), "allow_other_choice"))
        states.hidden[field_id] = hidden
        states.offered[field_id] = offered + (1 if other else 0)
        if offered <= 0 and not other:
            states.none_left.add(field_id)
    return states


def hidden_selection(field: Any, answer: Any, states: OptionStates) -> bool:
    """Does the answer select an option the question does not offer?"""
    hidden = states.hidden_options(str(_get(field, "id")))
    return bool(hidden) and any(
        option in hidden for option in selected_option_ids(answer, field)
    )


# ---------------------------------------------------------------------------
# Which questions an edit puts in question
# ---------------------------------------------------------------------------


def _reads(field: Any) -> Set[str]:
    reads: Set[str] = set()
    flt = _filter(field)
    if flt is not None and _get(flt, "field_id"):
        reads.add(str(_get(flt, "field_id")))
    for choice in _choices(field):
        logic = _option_logic(choice)
        for condition in (_get(logic, "conditions") or []) if logic else []:
            if _get(condition, "field_id"):
                reads.add(str(_get(condition, "field_id")))
            if _get(condition, "child_field_id"):
                reads.add(str(_get(condition, "child_field_id")))
    return reads


def option_keys_affected(form: Any, keys: Iterable[str]) -> Set[str]:
    """Choice questions whose options read one of ``keys`` (an answer an
    edit changed), through other such questions as well: an edit of an
    earlier answer can strand a later selection, which the edit must report
    (a respondent edit checks what it changes)."""
    reads = {
        str(_get(field, "id")): _reads(field)
        for field in _page_questions(form)
        if _is_option_target(field) and has_option_logic(field)
    }
    if not reads:
        return set()
    changed = set(keys)
    affected: Set[str] = set()
    grew = True
    while grew:
        grew = False
        for field_id, read in reads.items():
            if field_id not in affected and read & (changed | affected):
                affected.add(field_id)
                grew = True
    return affected


# ---------------------------------------------------------------------------
# Saving: problems, repair, refusal
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OptionLogicProblem:
    """A problem with a question's option logic. ``option_id``: the option
    whose conditions it concerns (None: the question's filter or the
    question itself)."""

    field_id: str
    message: str
    option_id: Optional[str] = None
    in_filter: bool = False

    def as_json(self) -> Dict[str, Optional[str]]:
        return {
            "fieldId": self.field_id,
            "optionId": self.option_id,
            "message": self.message,
        }


def _title(field: Any) -> str:
    title = _get(field, "title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return str(_get(field, "id"))


def _label(choice: Any) -> str:
    for name in ("value", "label", "id"):
        text = _get(choice, name)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return "an option"


class _Check:
    """One pass over a form's option logic. ``fix``: also repair what is
    wrong (drop the condition, filter or logic that breaks a rule) instead
    of only reporting it."""

    def __init__(self, form: Any, fix: bool):
        self.form = form
        self.fix = fix
        self.problems: List[OptionLogicProblem] = []
        self.caps: List[str] = []
        self.repaired = 0
        questions = _page_questions(form)
        # order of the page-level questions: what "earlier" means
        self.position = {
            str(_get(f, "id")): i for i, f in enumerate(questions) if _get(f, "id")
        }
        self.by_id: Dict[str, Any] = {}
        self.group_of: Dict[str, str] = {}
        for field in questions:
            if _get(field, "id"):
                self.by_id[str(_get(field, "id"))] = field
            if _type(field) == GROUP:
                for child in _group_children(field):
                    if _get(child, "id"):
                        self.by_id.setdefault(str(_get(child, "id")), child)
                        self.group_of[str(_get(child, "id"))] = str(_get(field, "id"))
        self.questions = questions

    def _problem(
        self, field: Any, message: str, choice: Any = None, in_filter: bool = False
    ) -> None:
        if len(self.problems) < PROBLEMS_MAX:
            self.problems.append(
                OptionLogicProblem(
                    str(_get(field, "id")),
                    message,
                    str(_get(choice, "id")) if choice is not None else None,
                    in_filter,
                )
            )

    # -- conditions --------------------------------------------------------

    def _condition_problem(self, owner: Any, condition: Any) -> Optional[str]:
        owner_id = str(_get(owner, "id"))
        source_id = _get(condition, "field_id")
        if not source_id:
            return "A condition needs a question to read."
        if not _get(condition, "comparison"):
            return "A condition needs a comparison."
        source_id = str(source_id)
        if source_id == owner_id:
            return "An option cannot depend on the answer to its own question."
        source = self.by_id.get(source_id)
        if source is None:
            return f"'{source_id}' is not a question of this form."
        if _get(source, "internal"):
            return (
                f"'{_title(source)}' is an internal field: respondents never "
                "answer it, so an option cannot depend on it."
            )
        if source_id in self.group_of:
            return (
                f"'{_title(source)}' is asked once per item of a repeating group. "
                "An option reads the group itself with groupMode COUNT, ANY or ALL."
            )
        is_group = _type(source) == GROUP
        mode = _get(condition, "group_mode")
        if is_group and mode not in GROUP_MODES:
            return f"'{_title(source)}' is a repeating group: set groupMode to COUNT, ANY or ALL."
        if not is_group and mode:
            return (
                f"groupMode only applies to repeating groups, not '{_title(source)}'."
            )
        if is_group and mode in ("ANY", "ALL"):
            children = {str(_get(c, "id")) for c in _group_children(source)}
            if str(_get(condition, "child_field_id") or "") not in children:
                return (
                    f"ANY/ALL conditions need childFieldId: a question of "
                    f"'{_title(source)}'."
                )
        if self.position.get(source_id, 1 << 30) >= self.position.get(owner_id, -1):
            return (
                f"An option can only depend on an earlier question: "
                f"'{_title(source)}' comes after '{_title(owner)}'."
            )
        return None

    def _check_choice_logic(self, owner: Any, choice: Any) -> None:
        logic = _get(choice, "logic")
        if logic is None:
            return
        conditions = list(_get(logic, "conditions") or [])
        action = _get(logic, "action")
        what = f"The option '{_label(choice)}' of '{_title(owner)}'"
        if action not in ACTIONS:
            self._problem(owner, f"{what} needs an action: SHOW or HIDE.", choice)
            return self._drop_logic(choice)
        if not conditions:
            self._problem(owner, f"{what} has logic without conditions.", choice)
            return self._drop_logic(choice)
        kept = []
        for condition in conditions:
            problem = self._condition_problem(owner, condition)
            if problem is None:
                kept.append(condition)
                continue
            self._problem(owner, f"{what}: {problem}", choice)
            self._fixed()
        if self.fix and len(kept) != len(conditions):
            # (the dropped conditions are what is counted, not the logic left
            # without any: it goes with the last of them)
            if kept:
                self._set(logic, "conditions", kept)
            else:
                self._set(choice, "logic", None)

    def _fixed(self) -> None:
        if self.fix:
            self.repaired += 1

    def _drop_logic(self, choice: Any) -> None:
        if self.fix:
            self._set(choice, "logic", None)
            self.repaired += 1

    @staticmethod
    def _set(item: Any, name: str, value: Any) -> None:
        if isinstance(item, dict):
            item[name] = value
        else:
            setattr(item, name, value)

    # -- filter ------------------------------------------------------------

    def _check_filter(self, owner: Any) -> None:
        flt = _filter(owner)
        if flt is None:
            return
        owner_id = str(_get(owner, "id"))
        what = f"The option filter of '{_title(owner)}'"
        source_id = str(_get(flt, "field_id") or "")
        source = self.by_id.get(source_id)
        problem: Optional[str] = None
        if source_id == owner_id:
            problem = "cannot read its own question."
        elif source is None:
            problem = f"reads '{source_id}', which is not a question of this form."
        elif _get(source, "internal") or source_id in self.group_of:
            problem = (
                f"cannot read '{_title(source)}': an internal question or one "
                "of a repeating group."
            )
        elif _type(source) not in CHOICE_TYPES:
            problem = (
                f"reads '{_title(source)}', which is not a single or multiple "
                "choice or dropdown question."
            )
        elif self.position.get(source_id, 1 << 30) >= self.position.get(owner_id, -1):
            problem = (
                f"can only read an earlier question: '{_title(source)}' comes "
                f"after '{_title(owner)}'."
            )
        if problem is not None:
            self._problem(owner, f"{what} {problem}", in_filter=True)
            if self.fix:
                self._set(_props(owner), "option_filter", None)
                self.repaired += 1
            return
        source_ids = {str(_get(c, "id")) for c in _choices(source) if _get(c, "id")}
        own_ids = {str(_get(c, "id")) for c in _choices(owner) if _get(c, "id")}
        mapping = list(_get(flt, "mapping") or [])
        kept = []
        for entry in mapping:
            when = _get(entry, "when")
            show = list(_get(entry, "show") or [])
            if when not in source_ids:
                self._problem(
                    owner,
                    f"{what}: '{when}' is not an option of '{_title(source)}'.",
                    in_filter=True,
                )
                self._fixed()
                continue
            good = [option for option in show if option in own_ids]
            if len(good) != len(show):
                self._problem(
                    owner,
                    f"{what}: an entry names an option that '{_title(owner)}' "
                    "does not have.",
                    in_filter=True,
                )
                if self.fix:
                    self.repaired += len(show) - len(good)
                    self._set(entry, "show", good)
            kept.append(entry)
        if self.fix and len(kept) != len(mapping):
            self._set(flt, "mapping", kept)
        if self.fix and not kept:
            self._set(_props(owner), "option_filter", None)

    # -- whole form --------------------------------------------------------

    def run(self) -> List[OptionLogicProblem]:
        conditions = filters = 0
        for field in self.questions:
            targets = [field] + (
                _group_children(field) if _type(field) == GROUP else []
            )
            for question in targets:
                if not has_option_logic(question):
                    continue
                if question is not field:
                    self._whole(
                        question,
                        f"'{_title(question)}' is in a repeating group: option "
                        "logic is not supported there yet.",
                    )
                    continue
                if not _is_option_target(question):
                    self._whole(
                        question,
                        f"'{_title(question)}' is not a single or multiple "
                        "choice or dropdown question (or is internal), so its "
                        "options cannot have logic.",
                    )
                    continue
                if len(_choices(question)) > OPTION_LOGIC_OPTIONS_MAX:
                    # never repaired away: a save that would lose the logic is
                    # refused, saying why, so nobody loses it unseen
                    self._cap(
                        f"'{_title(question)}' has more than "
                        f"{OPTION_LOGIC_OPTIONS_MAX} options, too many for option "
                        "logic: remove its option logic or some of its options."
                    )
                    continue
                for choice in _choices(question):
                    self._check_choice_logic(question, choice)
                self._check_filter(question)
                conditions += sum(
                    len(_get(_get(c, "logic"), "conditions") or [])
                    for c in _choices(question)
                )
                filters += 1 if _filter(question) is not None else 0
        if conditions > FORM_OPTION_CONDITIONS_MAX:
            self._cap(
                f"A form can have at most {FORM_OPTION_CONDITIONS_MAX} option "
                f"conditions; this one has {conditions}."
            )
        if filters > FORM_OPTION_FILTERS_MAX:
            self._cap(
                f"A form can have at most {FORM_OPTION_FILTERS_MAX} option "
                f"filters; this one has {filters}."
            )
        if (
            conditions
            and not self.caps
            and worst_case_cost(self.form) > OPTION_LOGIC_COST_PER_RESPONSE
        ):
            self._cap(
                "This form's option logic is too costly to check for each "
                "response (many conditions on questions with many options or on "
                "repeating groups): use fewer conditions."
            )
        return self.problems

    def _whole(self, question: Any, message: str) -> None:
        self._problem(question, message)
        if not self.fix:
            return
        for choice in _choices(question):
            if _get(choice, "logic") is not None:
                self._set(choice, "logic", None)
        if _filter(question) is not None:
            self._set(_props(question), "option_filter", None)
        self.repaired += 1

    def _cap(self, message: str) -> None:
        self.caps.append(message)


def option_logic_problems(form: Any) -> List[OptionLogicProblem]:
    """What a save of ``form`` would refuse, for the questions that carry
    option logic (not repaired). The form's size caps come last."""
    check = _Check(form, fix=False)
    problems = check.run()
    for message in check.caps:
        problems.append(OptionLogicProblem("", message))
    return problems[:PROBLEMS_MAX]


def prune_option_logic(form: Any) -> int:
    """Repair a form in place: drop the conditions, filters, filter entries
    and option logic a structural edit left broken (a removed or moved
    question, a removed option, a question made internal or of another
    type). Returns how many pieces were dropped. The size caps are not
    repaired: they are refused (``ensure_valid_option_logic``)."""
    check = _Check(form, fix=True)
    check.run()
    return check.repaired


def _refuse(problems: List[OptionLogicProblem]) -> None:
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={
            "code": ERROR_CODE,
            "message": problems[0].message,
            "errors": [problem.as_json() for problem in problems],
        },
    )


def ensure_valid_option_logic(form: Any, drop: bool = False) -> List[Dict[str, Any]]:
    """Refuse (422 ``invalid_option_logic``) a form whose option logic breaks
    the rules above. ``drop``: the builder's save repairs what a structural
    edit broke instead (the size caps still refuse, a question with too many
    options included: its logic is never dropped unseen); returns what it
    repaired (``fieldId``, ``optionId``, ``message``), for the creator to be
    told."""
    if not form_has_option_logic(form):
        return []
    check = _Check(form, fix=drop)
    problems = check.run()
    if check.caps:
        _refuse([OptionLogicProblem("", message) for message in check.caps])
    if problems and not drop:
        _refuse(problems)
    if drop and problems:
        logger.info("Repaired {} piece(s) of option logic on save", check.repaired)
        return [problem.as_json() for problem in problems]
    return []


# ---------------------------------------------------------------------------
# Warnings (the builder shows them; the webapp has the same, option-logic.ts)
# ---------------------------------------------------------------------------

UNREACHABLE_OPTION = "unreachable_option"
SOURCE_OPTION_UNMAPPED = "source_option_unmapped"
CAN_END_EMPTY = "can_end_empty"
TOO_MANY_OPTIONS = "too_many_options"


@dataclass(frozen=True)
class OptionLogicWarning:
    field_id: str
    code: str
    option_id: Optional[str] = None

    def as_json(self) -> Dict[str, Optional[str]]:
        return {
            "fieldId": self.field_id,
            "code": self.code,
            "optionId": self.option_id,
        }


def option_logic_warnings(form: Any) -> List[OptionLogicWarning]:
    """What a creator should look at, without being refused:

    - ``unreachable_option``: an option no row of the question's filter
      shows, so no answer to the earlier question offers it;
    - ``source_option_unmapped``: an option of the earlier question with no
      row (or an empty one): choosing it leaves nothing to choose;
    - ``can_end_empty``: a required question whose every option has its own
      logic, so some answers leave it with nothing to choose (it is then never
      required, but the creator probably did not mean it). A filter that leaves
      nothing is ``source_option_unmapped``'s to say;
    - ``too_many_options``: more options than option logic may sit on (a save
      is refused).
    """
    found: List[OptionLogicWarning] = []
    by_id = {str(_get(f, "id")): f for f in _page_questions(form) if _get(f, "id")}
    for field in by_id.values():
        if not _is_option_target(field) or not has_option_logic(field):
            continue
        field_id = str(_get(field, "id"))
        if len(_choices(field)) > OPTION_LOGIC_OPTIONS_MAX:
            # a save is refused (the logic is never dropped unseen)
            found.append(OptionLogicWarning(field_id, TOO_MANY_OPTIONS))
            continue
        flt = _filter(field)
        source = by_id.get(str(_get(flt, "field_id") or "")) if flt else None
        if flt is not None and source is not None:
            shown: Set[str] = set()
            mapped: Set[str] = set()
            for entry in _get(flt, "mapping") or []:
                show = [str(o) for o in (_get(entry, "show") or [])]
                if show:
                    mapped.add(str(_get(entry, "when")))
                shown.update(show)
            for choice in _choices(field):
                if _get(choice, "id") and str(_get(choice, "id")) not in shown:
                    found.append(
                        OptionLogicWarning(
                            field_id, UNREACHABLE_OPTION, str(_get(choice, "id"))
                        )
                    )
            for choice in _choices(source):
                if _get(choice, "id") and str(_get(choice, "id")) not in mapped:
                    found.append(
                        OptionLogicWarning(
                            field_id, SOURCE_OPTION_UNMAPPED, str(_get(choice, "id"))
                        )
                    )
        required = bool(_get(_get(field, "validations"), "required"))
        choices = [c for c in _choices(field) if _get(c, "id")]
        if (
            required
            and choices
            and not _get(_props(field), "allow_other_choice")
            and all(_option_logic(c) is not None for c in choices)
        ):
            found.append(OptionLogicWarning(field_id, CAN_END_EMPTY))
    return found


# ---------------------------------------------------------------------------
# The switch: CHOICE_LOGIC_ENABLED (off until an operator turns it on)
# ---------------------------------------------------------------------------

DISABLED_CODE = "choice_logic_disabled"
DISABLED_MESSAGE = (
    "Choice logic (options shown or hidden by answers, option filters) cannot "
    "be created or changed on this server yet (CHOICE_LOGIC_ENABLED is off). "
    "Choice logic already saved is kept."
)


def choice_logic_enabled() -> bool:
    """Is ``CHOICE_LOGIC_ENABLED`` on: may option logic and filters be created
    or changed? Stored ones are enforced either way."""
    from backend.config import settings

    return bool(getattr(settings, "CHOICE_LOGIC_ENABLED", False))


def _condition_key(condition: Any) -> Tuple[Any, ...]:
    return (
        str(_get(condition, "field_id") or ""),
        _get(condition, "comparison"),
        json.dumps(_get(condition, "value"), sort_keys=True, default=str),
        _get(condition, "group_mode"),
        str(_get(condition, "child_field_id") or ""),
    )


def _logic_piece(logic: Any) -> Tuple[Any, Any, FrozenSet[Tuple[Any, ...]]]:
    return (
        _get(logic, "action"),
        _get(logic, "operator") or "AND",
        frozenset(_condition_key(c) for c in (_get(logic, "conditions") or [])),
    )


def _filter_piece(flt: Any) -> Tuple[str, Dict[str, FrozenSet[str]]]:
    rows: Dict[str, Set[str]] = {}
    for entry in _get(flt, "mapping") or []:
        rows.setdefault(str(_get(entry, "when")), set()).update(
            str(option) for option in (_get(entry, "show") or [])
        )
    return (
        str(_get(flt, "field_id") or ""),
        {when: frozenset(show) for when, show in rows.items()},
    )


def _logic_pieces(form: Any) -> Dict[Tuple[str, str], Any]:
    """Every piece of option logic of the form: an option's logic and a
    question's filter, by ``(question id, "option:<id>" | "filter")``."""
    pieces: Dict[Tuple[str, str], Any] = {}
    # every field wherever it sits (a bare question as an op brings it too)
    pending = list(_get(form, "fields") or [])
    while pending:
        field = pending.pop()
        field_id = str(_get(field, "id"))
        for choice in _choices(field):
            logic = _option_logic(choice)
            if logic is not None:
                pieces[(field_id, f"option:{_get(choice, 'id')}")] = _logic_piece(logic)
        if _filter(field) is not None:
            pieces[(field_id, "filter")] = _filter_piece(_filter(field))
        pending.extend(_group_children(field))
    return pieces


def _no_more_than(kind: str, new: Any, stored: Any) -> bool:
    """Is the piece ``new`` nothing but ``stored`` with some of it taken away
    (conditions, filter entries or options dropped by a repair)?"""
    if stored is None:
        return False
    if kind == "filter":
        if new[0] != stored[0]:
            return False
        return all(
            when in stored[1] and show <= stored[1][when]
            for when, show in new[1].items()
        )
    return new[0] == stored[0] and new[1] == stored[1] and new[2] <= stored[2]


def new_or_changed_option_logic(
    form: Any, existing: Any = None
) -> List[Tuple[str, str]]:
    """``(question id, piece)`` of the option logic ``form`` has that
    ``existing`` (the stored version, or None) does not have, as it is: an
    option's logic or a filter that is new, or changed by more than taking
    some of it away. Clearing, a repair and moving a question change
    nothing in this sense."""
    stored = _logic_pieces(existing) if existing is not None else {}
    return [
        key
        for key, piece in _logic_pieces(form).items()
        if piece != stored.get(key)
        and not _no_more_than(
            "filter" if key[1] == "filter" else "option", piece, stored.get(key)
        )
    ]


def ensure_choice_logic_allowed(form: Any, existing: Any = None) -> None:
    """While ``CHOICE_LOGIC_ENABLED`` is off, refuse (422
    ``choice_logic_disabled``) a save that brings new or changed option logic
    or filters. What is stored, unchanged, passes (and is still enforced)."""
    if choice_logic_enabled():
        return
    changed = new_or_changed_option_logic(form, existing)
    if changed:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": DISABLED_CODE,
                "message": DISABLED_MESSAGE,
                "errors": [
                    {
                        "fieldId": field_id,
                        "optionId": (
                            piece.removeprefix("option:") if piece != "filter" else None
                        ),
                    }
                    for field_id, piece in changed[:PROBLEMS_MAX]
                ],
            },
        )


def strip_option_logic(form: Any) -> int:
    """Remove every option's logic and every filter of the form, in place (a
    provider import never brings option logic, whatever its payload holds).
    Returns how many pieces went."""
    removed = 0
    pending = list(_get(form, "fields") or [])
    while pending:
        field = pending.pop()
        for choice in _choices(field):
            if _get(choice, "logic") is not None:
                _Check._set(choice, "logic", None)
                removed += 1
        if _filter(field) is not None:
            _Check._set(_props(field), "option_filter", None)
            removed += 1
        pending.extend(_group_children(field))
    return removed
