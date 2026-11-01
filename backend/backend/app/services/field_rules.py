"""Field rules ("logic actions"): the server's replay and save checks.

A question may carry ordered rules at ``properties.rules`` (common
``FieldRule``): ``when`` (the conditions of ``properties.logic``, or an
expressions-v1 ``expression`` that is active when truthy) and ``then`` (at
least one of ``required``, ``readOnly``, ``title``, ``description``,
``setValue``). Spec: docs/spec/README.md "Field rules". The webapp's twin is
``src/lib/field-rules.ts``; the shared cases in
``docs/spec/field-rules.cases.json`` and ``docs/spec/answer-validation.cases.json``
(checks ``fieldRules``) run on both sides, so change one evaluator only
together with the other. The server is the authority.

- **Precedence:** a field's rules apply in order; for each property the last
  active rule wins. ``required`` starts from ``validations.required``. Rules
  never change visibility (``properties.logic`` does).
- **Values the server owns** (``resolve_field_rules``, called from
  ``calculate_and_check`` on every submission and edit): while a rule with
  ``setValue`` is active, the field's answer is the server's value (an empty
  result removes the client's); while a rule with ``readOnly`` is active and
  none sets a value, the client's answer is removed. Calculated fields and
  these fields are evaluated in one dependency order, each written into the
  answers and the variables before the next, so a trigger that reads a
  calculation or a set value sees the final one.
- **Required** (``FieldRuleStates.is_required``): the effective flag of a
  question, per item inside a repeating group (conditions read the item's
  own answers, expressions its siblings by id). A question whose value the
  server owns is never required (an empty result is not the respondent's
  fault); hidden ones are not counted at all.
- **Title and description** are presentation only: nothing is enforced.
- **Variables** are the one namespace of logic, piping and calculations
  (``calculated_fields.build_variables``). A rule that reads something the
  form does not have (a removed question, an unknown variable, its own
  field) is not active.
- **Saving** (``field_rule_problems``): where rules may sit, what they may
  read (an existing, respondent-facing question in scope, never the field
  itself), expressions and their variables, values that fit the field, pipes
  in texts, caps, unique ids and no circle through set values and
  calculations. ``ensure_valid_field_rules`` refuses with 422
  ``invalid_field_rules``; a rule the stored draft already had that a
  structural edit broke is dropped instead (the builder cannot edit rules).

Creator expressions are untrusted: the evaluator bounds them (depth 32, 500
nodes, inputs over 10,000 characters or 1,000 items count as empty, and so
does a text over 10,000 characters that a condition reads), at most
``FIELD_RULES_MAX`` rules per field and ``FORM_FIELD_RULES_MAX`` per form are
read, an expression may read at most ``RULE_VARIABLES_MAX`` variables, and
callers run the replay and the save check off the event loop. Each response
has an evaluation budget (``RULE_COST_PER_RESPONSE`` cost units: expression
nodes, conditions, items of repeating groups read); a form whose rules could
exceed it is refused when it is saved, and a replay that exceeds it anyway
(data no save accepted) refuses the response (422 ``field_rules_too_costly``)
rather than store unchecked answers. The save check stops after
``PROBLEMS_MAX`` problems.
"""

import json
import re
from collections import Counter, deque
from dataclasses import dataclass, field as dataclass_field
from decimal import Decimal
from http import HTTPStatus
from typing import (
    Any,
    Collection,
    Deque,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
)

from common.currencies import DEFAULT_CURRENCY, is_time, parse_amount
from common.expressions import (
    MAX_INPUT_STRING_LENGTH,
    ExpressionError,
    evaluate_expression,
    format_expression_value,
    validate_expression,
)
from common.expressions.decimal_num import Dec
from common.models.standard_form import (
    FIELD_RULES_MAX,
    FORM_FIELD_RULES_MAX,
    is_iso_date,
)
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.services.calculated_fields import (
    CALCULATED,
    GROUP,
    NOT_VARIABLES,
    SLIDE,
    _calculated_value,
    _get,
    _plain,
    _question_keys,
    _title,
    _type,
    build_variables,
    question_variable_keys,
    question_variables,
    calculated_answer,
    calculated_fields,
    expression_variables,
    has_calculated_value,
    variable_keys,
)
from backend.app.services.repeating_groups import (
    comparable_answer_value,
    evaluate_conditions,
    group_items,
    logic_sources,
)

ERROR_CODE = "invalid_field_rules"
DISABLED_CODE = "field_rules_disabled"
COSTLY_CODE = "field_rules_too_costly"
# Problems one save check reports at most (the rest are not looked for).
PROBLEMS_MAX = 50
# Distinct variables one rule expression may read.
RULE_VARIABLES_MAX = 50
# Evaluation cost one response may spend on rules: an expression costs its
# nodes, plus the items of a repeating group for each group list it reads; a
# condition costs 1, plus the group's items for ANY / ALL. A form whose
# worst case (every group at its maximum) is above it cannot be saved.
RULE_COST_PER_RESPONSE = 200_000
# Items a group list may hold when nothing better is known (the hard cap).
_LIST_ITEMS_MAX = 50
COMPARISONS = {
    "IS_EMPTY",
    "IS_NOT_EMPTY",
    "IS_EQUAL",
    "IS_NOT_EQUAL",
    "CONTAINS",
    "DOES_NOT_CONTAIN",
    "LESS_THAN",
    "LESS_THAN_EQUAL",
    "GREATER_THAN",
    "GREATER_THAN_EQUAL",
    "STARTS_WITH",
    "ENDS_WITH",
}
GROUP_MODES = {"COUNT", "ANY", "ALL"}
TEXT_TYPES = {"short_text", "long_text"}
CHOICE_TYPES = {"multiple_choice", "dropdown"}
# Types whose value a rule may set or lock (readOnly / setValue), on a page
# only: never inside a repeating group in this version.
VALUE_TYPES = TEXT_TYPES | CHOICE_TYPES | {
    "number",
    "date",
    "day",
    "time",
    "currency",
    "yes_no",
}
# Types that hold no answer a rule could apply to (content, pages, hidden
# and calculated fields): rules may not sit on them.
# Address and signature questions are no formula variables but may be required,
# retitled or described by a rule (never set or locked: the form cannot invent an
# address or sign for the respondent).
NOT_RULE_TARGETS = (NOT_VARIABLES - {"address", "signature"}) | {CALCULATED, GROUP}
_PIPE = re.compile(r"\{\{\s*(field|hidden|group)\s*:\s*([^|}]*?)\s*(?:\|[^}]*)?\}\}")
_ANSWER_TYPE = {
    "short_text": "text",
    "long_text": "text",
    "number": "number",
    "date": "date",
    "day": "date",
    "time": "time",
    "currency": "currency",
    "yes_no": "boolean",
    "multiple_choice": "choice",
    "dropdown": "choice",
}


# ---------------------------------------------------------------------------
# Form structure
# ---------------------------------------------------------------------------


def _children(field: Any) -> List[Any]:
    return list(_get(_get(field, "properties"), "fields") or [])


def _is_repeating_group(field: Any) -> bool:
    return (
        _type(field) == GROUP and _get(_get(field, "properties"), "repeat") is not None
    )


def _rules(field: Any) -> List[Any]:
    return list(_get(_get(field, "properties"), "rules") or [])


def _slides(form: Any) -> Optional[List[Any]]:
    fields = list(_get(form, "fields") or [])
    if not fields or any(_type(field) != SLIDE for field in fields):
        return None
    return fields


@dataclass(frozen=True)
class _Target:
    """A question that may carry rules: on a page (``group`` None) or in a
    repeating group."""

    field: Any
    group: Any = None

    @property
    def id(self) -> str:
        return str(_get(self.field, "id") or "")

    @property
    def group_id(self) -> Optional[str]:
        return str(_get(self.group, "id")) if self.group is not None else None


def _targets(form: Any) -> List[_Target]:
    """Every question of a page-based form, with its repeating group."""
    found: List[_Target] = []
    for slide in _slides(form) or []:
        for field in _children(slide):
            found.append(_Target(field))
            if _is_repeating_group(field):
                found.extend(_Target(child, field) for child in _children(field))
    return found


def _rule_targets(form: Any) -> List[_Target]:
    """The questions that carry rules, in form order."""
    return [target for target in _targets(form) if _rules(target.field)]


def _effect(rule: Any, key: str) -> Any:
    return _get(_get(rule, "then"), key)


def _has_value_effect(rule: Any) -> bool:
    return (
        _effect(rule, "read_only") is not None or _effect(rule, "set_value") is not None
    )


def _is_value_node(target: _Target) -> bool:
    """A page question whose value rules may set or lock."""
    return (
        target.group is None
        and not _get(target.field, "internal")
        and _type(target.field) in VALUE_TYPES
        and not _multiple(target.field)
        and any(_has_value_effect(rule) for rule in _rules(target.field))
    )


def _multiple(field: Any) -> bool:
    return _type(field) == "multiple_choice" and bool(
        _get(_get(field, "properties"), "allow_multiple_selection")
    )


def _trigger_reads(rule: Any) -> List[str]:
    """The answer keys and variables a rule's trigger reads."""
    when = _get(rule, "when")
    expression = _get(when, "expression")
    if expression is not None:
        return expression_variables(expression)
    keys: List[str] = []
    for condition in _get(when, "conditions") or []:
        key = _get(condition, "field_id")
        if key and str(key) not in keys:
            keys.append(str(key))
    return keys


def _value_reads(rule: Any) -> List[str]:
    set_value = _effect(rule, "set_value")
    expression = _get(set_value, "expression")
    return expression_variables(expression) if expression is not None else []


def _rule_reads(rule: Any) -> List[str]:
    return _trigger_reads(rule) + [
        key for key in _value_reads(rule) if key not in _trigger_reads(rule)
    ]


def _is_own_key(key: str, owner: str) -> bool:
    """Is ``key`` the question's own value? A date range reads as two
    variables, ``<id>.start`` and ``<id>.end``: both are its own."""
    return key == owner or key in (f"{owner}.start", f"{owner}.end")


def _answer_key(key: str) -> str:
    """The answers key a variable reads (``<group>.<child>`` reads the
    group's answer)."""
    return key.split(".", 1)[0]


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def _truthy(value: Any) -> bool:
    if value is None or value is False or value == "":
        return False
    if isinstance(value, Decimal):
        return value != 0
    if isinstance(value, list):
        return len(value) > 0
    return True


@dataclass
class _Scope:
    """What a rule reads: the answers (conditions), the variables
    (expressions), the keys that exist for it and the evaluation context."""

    answers: Dict[str, Any]
    variables: Dict[str, Any]
    known: Set[str]
    sources: Dict[str, Any]
    context: Dict[str, Any]
    budget: "_Budget"
    costs: Dict[int, int]


class FieldRulesTooCostly(Exception):
    """The replay of one response went over ``RULE_COST_PER_RESPONSE``."""


@dataclass
class _Budget:
    left: int = RULE_COST_PER_RESPONSE

    def charge(self, cost: int) -> None:
        self.left -= cost
        if self.left < 0:
            raise FieldRulesTooCostly()


def _ast_cost(ast: Any, group_items: Mapping[str, int]) -> int:
    """Nodes of an AST, plus the items of every group list it reads."""
    cost, pending = 0, [ast]
    while pending:
        node = pending.pop()
        cost += 1
        if not isinstance(node, dict) or len(node) != 1:
            continue
        op, value = next(iter(node.items()))
        if op == "var" and isinstance(value, str) and "." in value:
            cost += group_items.get(_answer_key(value), _LIST_ITEMS_MAX)
        elif isinstance(value, list):
            pending.extend(value)
    return cost


def rule_cost(rule: Any, group_items: Mapping[str, int]) -> int:
    """What one evaluation of a rule (trigger and set value) costs, with
    every repeating group at ``group_items`` (its maximum)."""
    when = _get(rule, "when")
    cost = 0
    if _get(when, "expression") is not None:
        cost += _ast_cost(_get(when, "expression"), group_items)
    for condition in _get(when, "conditions") or []:
        cost += 1
        if _get(condition, "group_mode") in ("ANY", "ALL"):
            source = str(_get(condition, "field_id") or "")
            cost += group_items.get(source, _LIST_ITEMS_MAX)
    expression = _get(_effect(rule, "set_value"), "expression")
    if expression is not None:
        cost += _ast_cost(expression, group_items)
    return cost


def _group_maxima(form: Any) -> Dict[str, int]:
    found: Dict[str, int] = {}
    for target in _targets(form):
        if _is_repeating_group(target.field):
            repeat = _get(_get(target.field, "properties"), "repeat")
            high = getattr(repeat, "effective_max", None)
            found[target.id] = high if isinstance(high, int) else _LIST_ITEMS_MAX
    return found


def _has_state_effect(rule: Any) -> bool:
    return any(
        _effect(rule, key) is not None for key in ("required", "title", "description")
    )


def _question_cost(target: "_Target", maxima: Mapping[str, int]) -> int:
    """The worst case of one question's rules: each at its worst, once per
    pass that reads it (value, state), once per item in a group."""
    times = maxima.get(target.group_id, 1) if target.group is not None else 1
    total = 0
    for rule in _rules(target.field)[:FIELD_RULES_MAX]:
        passes = int(_has_value_effect(rule)) + int(_has_state_effect(rule))
        total += rule_cost(rule, maxima) * times * passes
    return total


def worst_case_cost(form: Any) -> int:
    """The most a response's replay can cost: each rule at its worst, once
    per pass that reads it (value, state), once per item in a group."""
    maxima = _group_maxima(form)
    return sum(_question_cost(target, maxima) for target in _rule_targets(form))


def _dangling(rule: Any, owner: str, scope: _Scope) -> bool:
    """Does the rule read something the form does not have, or its own
    field? Such a rule is never active."""
    when = _get(rule, "when")
    if _get(when, "expression") is not None:
        reads = expression_variables(_get(when, "expression"))
        if any(key not in scope.known or _is_own_key(key, owner) for key in reads):
            return True
    else:
        for condition in _get(when, "conditions") or []:
            source = str(_get(condition, "field_id") or "")
            if not source or source == owner or source not in scope.sources:
                return True
            child = _get(condition, "child_field_id")
            if _get(condition, "group_mode") in ("ANY", "ALL") and (
                not child or str(child) not in scope.sources
            ):
                return True
    return any(
        key not in scope.known or _is_own_key(key, owner) for key in _value_reads(rule)
    )


def _evaluate(ast: Any, scope: _Scope) -> Any:
    try:
        return evaluate_expression(ast, scope.variables, scope.context)
    except (ExpressionError, RecursionError):
        return None


def _is_active(rule: Any, owner: str, scope: _Scope) -> bool:
    if _dangling(rule, owner, scope):
        return False
    scope.budget.charge(scope.costs.get(id(rule), 1))
    when = _get(rule, "when")
    expression = _get(when, "expression")
    if expression is not None:
        return _truthy(_evaluate(expression, scope))
    try:
        return evaluate_conditions(
            _get(when, "operator") or "AND",
            _get(when, "conditions"),
            scope.answers,
            scope.sources,
            MAX_INPUT_STRING_LENGTH,
        )
    except (TypeError, ValueError):
        return False


def _read_rules(field: Any, budget: List[int]) -> List[Any]:
    """The rules of a field the server reads: at most FIELD_RULES_MAX, and
    FORM_FIELD_RULES_MAX in the whole form (``budget`` counts down)."""
    rules = _rules(field)[:FIELD_RULES_MAX]
    allowed = max(0, min(len(rules), budget[0]))
    budget[0] -= allowed
    return rules[:allowed]


def _choice_ids(field: Any) -> Set[str]:
    return {
        str(_get(choice, "id"))
        for choice in (_get(_get(field, "properties"), "choices") or [])
        if _get(choice, "id")
    }


def value_answer(field: Any, value: Any) -> Optional[Dict[str, Any]]:
    """The stored answer of a value a rule set for ``field`` (None when it
    is empty or does not fit the field's type)."""
    field_type = _type(field)
    field_id = str(_get(field, "id"))
    answer: Dict[str, Any] = {"field": {"id": field_id}}
    if field_type in TEXT_TYPES:
        text = value if isinstance(value, str) else format_expression_value(value)
        return {**answer, "type": "text", "text": text} if text != "" else None
    if field_type == "number":
        if isinstance(value, Decimal):
            stored = calculated_answer(field_id, value)
            return stored if stored.get("type") == "number" else None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # the numbers formulas can hold (15 significant digits, finite)
            if Dec.from_python(value) is None:
                return None
            return {**answer, "type": "number", "number": value}
        return None
    if field_type in ("date", "day"):
        if is_iso_date(value):
            return {**answer, "type": "date", "date": value}
        return None
    if field_type == "time":
        if is_time(value):
            return {**answer, "type": "time", "time": value}
        return None
    if field_type == "currency":
        # the amount in the question's first currency
        if isinstance(value, bool) or not isinstance(
            value, (str, int, float, Decimal)
        ):
            return None
        code = (
            _get(_get(field, "properties"), "currencies") or [DEFAULT_CURRENCY]
        )[0]
        amount = value if isinstance(value, str) else format_expression_value(value)
        if parse_amount(amount, code) is None:
            return None
        return {
            **answer,
            "type": "currency",
            "currency": {"code": code, "amount": amount},
        }
    if field_type == "yes_no":
        if isinstance(value, bool):
            return {**answer, "type": "boolean", "boolean": value}
        if value in ("Yes", "true"):
            return {**answer, "type": "boolean", "boolean": True}
        if value in ("No", "false"):
            return {**answer, "type": "boolean", "boolean": False}
        return None
    if field_type in CHOICE_TYPES:
        if isinstance(value, str) and value in _choice_ids(field):
            return {**answer, "type": "choice", "choice": {"value": value}}
        return None
    return None


def _set_value(field: Any, rule: Any, scope: _Scope) -> Optional[Dict[str, Any]]:
    set_value = _effect(rule, "set_value")
    const = _get(set_value, "const")
    if const is not None:
        return value_answer(field, const)
    if _type(field) in CHOICE_TYPES:
        return None  # a choice is set by a fixed option only
    return value_answer(field, _evaluate(_get(set_value, "expression"), scope))


def _empty_answer(field: Any) -> Dict[str, Any]:
    return {
        "field": {"id": str(_get(field, "id"))},
        "type": _ANSWER_TYPE.get(_type(field), "text"),
    }


@dataclass
class FieldRuleStates:
    """What the rules decided for one set of answers. Keys are
    ``(field id, group id, item)`` (group and item None on a page)."""

    # page questions whose value the server owns (never required)
    locked: Set[str] = dataclass_field(default_factory=set)
    # effective ``required`` where an active rule set it
    required: Dict[Tuple[str, Optional[str], Optional[int]], bool] = dataclass_field(
        default_factory=dict
    )
    # ``title`` / ``description`` of the last active rules (presentation)
    texts: Dict[Tuple[str, Optional[str], Optional[int]], Dict[str, str]] = (
        dataclass_field(default_factory=dict)
    )

    def is_required(
        self,
        field: Any,
        static: bool,
        group_id: Optional[str] = None,
        item: Optional[int] = None,
    ) -> bool:
        field_id = str(_get(field, "id"))
        if group_id is None and field_id in self.locked:
            return False
        return self.required.get((field_id, group_id, item), static)

    def is_locked(self, field: Any) -> bool:
        return str(_get(field, "id")) in self.locked


NO_RULES = FieldRuleStates()


def _value_order(nodes: List[_Target], calcs: List[Any]) -> Tuple[List[Any], Set[str]]:
    """Calculated fields and set-value questions, each after the value
    nodes it reads, and the ids of those in a circle (only in data no save
    would accept): they come last, in form order; such a calculation has no
    value (as ``calculated_fields.evaluation_order`` leaves it)."""
    by_id: Dict[str, Any] = {}
    deps: Dict[str, Set[str]] = {}
    for calc in calcs:
        key = str(_get(calc, "id"))
        by_id[key] = calc
        deps[key] = set(
            expression_variables(_get(_get(calc, "properties"), "expression"))
        )
    for node in nodes:
        by_id[node.id] = node
        deps[node.id] = {
            key
            for rule in _rules(node.field)
            if _has_value_effect(rule)
            for key in _rule_reads(rule)
        }
    calc_ids = {str(_get(calc, "id")) for calc in calcs}
    for key in deps:
        # a calculation that reads itself stays in a circle (no value), as
        # calculated_fields.evaluation_order leaves it; a rule reading its
        # own question is inactive anyway
        deps[key] = {
            ref for ref in deps[key] if ref in by_id and (ref != key or key in calc_ids)
        }
    ordered: List[Any] = []
    done: Set[str] = set()
    progress = True
    while progress:
        progress = False
        for key, item in by_id.items():
            if key in done or any(ref not in done for ref in deps[key]):
                continue
            done.add(key)
            ordered.append(item)
            progress = True
    cyclic = {key for key in by_id if key not in done}
    ordered.extend(item for key, item in by_id.items() if key in cyclic)
    return ordered, cyclic


def _item_count(group: Any, items: List[Dict[str, Any]]) -> int:
    """How many items a repeating group shows (as answer validation counts
    them: at least the minimum, at most the maximum)."""
    repeat = _get(_get(group, "properties"), "repeat")
    low = getattr(repeat, "effective_min", None)
    high = getattr(repeat, "effective_max", None)
    low = low if isinstance(low, int) else 1
    high = high if isinstance(high, int) else 3
    return min(high, max(low, len(items)))


def _apply_states(
    rules: List[Any],
    owner: str,
    scope: _Scope,
    key: Tuple[str, Optional[str], Optional[int]],
    states: FieldRuleStates,
) -> None:
    required: Optional[bool] = None
    texts: Dict[str, str] = {}
    for rule in rules:
        if not _has_state_effect(rule) or not _is_active(rule, owner, scope):
            continue
        if _effect(rule, "required") is not None:
            required = bool(_effect(rule, "required"))
        for name in ("title", "description"):
            if _effect(rule, name) is not None:
                texts[name] = _effect(rule, name)
    if required is not None:
        states.required[key] = required
    if texts:
        states.texts[key] = texts


def resolve_field_rules(
    form: Any,
    answers: Any,
    hidden_values: Optional[Mapping[str, Any]] = None,
    today: Optional[str] = None,
    keep_empty: bool = False,
) -> Tuple[Any, FieldRuleStates]:
    """The answers with the server's values (calculated fields and the
    values rules set or lock) and the states the rules give the questions.
    What a client sent for a calculated field, or for a question while a
    rule sets or locks it, is dropped; ``keep_empty`` stores an empty answer
    instead of none, so that an edit overwrites a stored value."""
    slides = _slides(form)
    calcs = [
        field
        for field in calculated_fields(form)
        if _get(field, "id") and not _get(field, "internal")
    ]
    all_calcs = calculated_fields(form)
    targets = _rule_targets(form) if slides is not None else []
    if not all_calcs and not targets:
        return answers, NO_RULES
    out = dict(answers) if isinstance(answers, dict) else {}
    for calc in all_calcs:
        out.pop(str(_get(calc, "id")), None)
    plain = _plain(out)
    variables = build_variables(form, plain, hidden_values)
    context = {"today": today} if today else {}
    known = variable_keys(form)
    # What respondents are served: no internal question (a condition that
    # reads one is not active, as in the browser, which never gets it).
    sources = {
        key: field
        for key, field in logic_sources(slides or []).items()
        if not _get(field, "internal")
    }
    question_keys = _question_keys(form)
    states = FieldRuleStates()
    allowance = [FORM_FIELD_RULES_MAX]
    read: Dict[int, List[Any]] = {
        id(target.field): _read_rules(target.field, allowance) for target in targets
    }
    nodes = [target for target in targets if _is_value_node(target)]
    maxima = _group_maxima(form)
    costs = {
        id(rule): rule_cost(rule, maxima) for rules in read.values() for rule in rules
    }
    budget = _Budget()
    scope = _Scope(plain, variables, known, sources, context, budget, costs)

    ordered, cyclic = _value_order(nodes, calcs)
    for item in ordered:
        if not isinstance(item, _Target):
            field_id = str(_get(item, "id"))
            value = (
                None
                if field_id in cyclic
                else _calculated_value(item, variables, question_keys, context)
            )
            variables[field_id] = value
            answer = calculated_answer(field_id, value)
            plain[field_id] = answer
            if has_calculated_value(answer) or keep_empty:
                out[field_id] = answer
            continue
        field = item.field
        field_id = item.id
        active = [
            rule
            for rule in read[id(field)]
            if _has_value_effect(rule) and _is_active(rule, field_id, scope)
        ]
        if not active:
            continue
        setter = next(
            (rule for rule in reversed(active) if _effect(rule, "set_value")), None
        )
        # a value in a circle has no value (as a calculation in one has not)
        answer = (
            _set_value(field, setter, scope)
            if setter is not None and field_id not in cyclic
            else None
        )
        states.locked.add(field_id)
        if answer is not None:
            out[field_id] = answer
            plain[field_id] = answer
        else:
            out.pop(field_id, None)
            plain.pop(field_id, None)
            if keep_empty:
                out[field_id] = _empty_answer(field)
        variables[field_id] = comparable_answer_value(plain.get(field_id), _type(field))

    groups: Dict[str, Any] = {}
    for target in targets:
        rules = read[id(target.field)]
        if not rules:
            continue
        if target.group is None:
            _apply_states(rules, target.id, scope, (target.id, None, None), states)
            continue
        groups.setdefault(target.group_id, target.group)
    for group_id, group in groups.items():
        items = group_items(plain.get(group_id))
        children = _children(group)
        sibling_keys = {
            key
            for c in children
            if _get(c, "id")
            for key in question_variable_keys(c)
        }
        for index in range(_item_count(group, items)):
            item = items[index] if index < len(items) else {}
            item_scope = _Scope(
                {**plain, **item},
                {
                    **variables,
                    **{
                        key: value
                        for child in children
                        if _get(child, "id")
                        for key, value in question_variables(
                            child, item.get(str(_get(child, "id")))
                        ).items()
                    },
                },
                known | sibling_keys,
                sources,
                context,
                budget,
                costs,
            )
            for child in children:
                rules = read.get(id(child)) or []
                if rules:
                    child_id = str(_get(child, "id"))
                    _apply_states(
                        rules, child_id, item_scope, (child_id, group_id, index), states
                    )
    return out, states


def field_rule_states(
    form: Any,
    answers: Any,
    hidden_values: Optional[Mapping[str, Any]] = None,
    today: Optional[str] = None,
) -> FieldRuleStates:
    """The states only (the answers are left as they are)."""
    return resolve_field_rules(form, answers, hidden_values, today)[1]


def server_value_ids(form: Any) -> List[str]:
    """Page questions whose value a rule may set or lock: on an edit, the
    server's result for them overwrites what is stored."""
    return [target.id for target in _rule_targets(form) if _is_value_node(target)]


def rule_keys_reading(form: Any, keys: Iterable[str]) -> Set[str]:
    """The answer keys (a question's id, a group's id for a question in a
    repeating group) whose rules read one of ``keys``: an edit of those keys
    may change what the rules require of them."""
    wanted = {_answer_key(str(key)) for key in keys}
    found: Set[str] = set()
    for target in _rule_targets(form):
        reads = {
            _answer_key(key)
            for rule in _rules(target.field)
            for key in _rule_reads(rule)
        }
        if target.group is not None:
            # siblings are read inside the item, i.e. through the group
            reads = {target.group_id if r in _sibling_ids(target) else r for r in reads}
        if reads & wanted:
            found.add(target.group_id or target.id)
    return found


def rule_keys_affected(form: Any, keys: Iterable[str]) -> Set[str]:
    """``rule_keys_reading`` through set values: when a question whose value
    a rule sets reads one of ``keys``, its value may change, so the rules
    that read it are affected too (and so on). What an edit of ``keys`` must
    check again. Each rule's reads are worked out once (key -> readers), then
    a breadth-first walk: linear in the rules, whatever the chain length."""
    readers: Dict[str, Set[str]] = {}
    for target in _rule_targets(form):
        reads = {
            _answer_key(key)
            for rule in _rules(target.field)
            for key in _rule_reads(rule)
        }
        if target.group is not None:
            siblings = _sibling_ids(target)
            reads = {target.group_id if r in siblings else r for r in reads}
        owner = target.group_id or target.id
        for key in reads:
            readers.setdefault(key, set()).add(owner)
    value_ids = set(server_value_ids(form))
    pending = deque({_answer_key(str(key)) for key in keys})
    queued = set(pending)
    found: Set[str] = set()
    while pending:
        for owner in readers.get(pending.popleft(), ()):
            found.add(owner)
            if owner in value_ids and owner not in queued:
                queued.add(owner)
                pending.append(owner)
    return found


def _sibling_ids(target: _Target) -> Set[str]:
    return {str(_get(c, "id")) for c in _children(target.group) if _get(c, "id")}


def required_by_rules(field: Any) -> bool:
    """Does any rule of the field set ``required``? (Their effective flag is
    answer validation's, with the rules replayed.)"""
    return any(_effect(rule, "required") is not None for rule in _rules(field))


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldRuleProblem:
    """A problem with the rules of one field: its id, the JSON pointer into
    its ``rules`` (``/0/when/expression/+/1/var``; ``""`` = all of them),
    a readable message and, for a problem of one rule, its position.
    ``whole_field`` marks a problem with the question itself (it is internal,
    cannot have rules, or is not a question at all): none of its rules can
    stand, and a save that drops broken rules drops all of them."""

    field_id: str
    path: str
    message: str
    rule: Optional[int] = None
    whole_field: bool = False

    def as_json(self) -> Dict[str, str]:
        return {"fieldId": self.field_id, "path": self.path, "message": self.message}


def _pointer(*parts: Any) -> str:
    return "".join(
        "/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts
    )


class _Enough(Exception):
    """The save check found as many problems as it reports."""


class _Checker:
    """Checks the rules of one form; see :func:`field_rule_problems`."""

    def __init__(
        self,
        form: Any,
        limit: Optional[int] = PROBLEMS_MAX,
        only: Optional[Collection[str]] = None,
    ):
        self.form = form
        self.limit = limit
        self.only = set(only) if only is not None else None
        self.problems: List[FieldRuleProblem] = []
        self.targets = _targets(form)
        self.by_id: Dict[str, _Target] = {t.id: t for t in self.targets if t.id}
        self.pages = {str(_get(s, "id")) for s in _slides(form) or []}
        self.known = variable_keys(form)
        self.hidden_names = {str(n) for n in (_get(form, "hidden_fields") or [])}
        self.internal = {t.id for t in self.targets if _get(t.field, "internal")}
        self.calc_ids = {
            str(_get(f, "id")) for f in calculated_fields(form) if _get(f, "id")
        }
        # worked out once per checker, not once per rule or per run
        self.maxima = _group_maxima(form)
        self._costs: Dict[int, int] = {}
        self._siblings: Dict[int, Set[str]] = {}

    def run(self) -> List[FieldRuleProblem]:
        """The problems of the form as it is now. A checker may run again
        after the rules of the questions in ``only`` were replaced (nothing
        else changed): what does not depend on them is kept, and the cost of
        the other questions' rules is not worked out again."""
        self.problems = []
        total = _total_rules(self.form)
        if not total:
            return self.problems
        if total > FORM_FIELD_RULES_MAX:
            # Nothing else is looked at: the per-rule checks would be paid
            # for every rule of an oversized form.
            return [
                FieldRuleProblem(
                    "",
                    "",
                    f"A form can have at most {FORM_FIELD_RULES_MAX} rules; this "
                    f"one has {total}.",
                )
            ]
        try:
            self.check()
        except _Enough:
            pass
        return self.problems

    def siblings(self, target: _Target) -> Set[str]:
        key = id(target.group)
        if key not in self._siblings:
            # a sibling's id reads its answer; a date range reads as its two days
            self._siblings[key] = _sibling_ids(target) | {
                variable
                for c in _children(target.group)
                if _get(c, "id")
                for variable in question_variable_keys(c)
            }
        return self._siblings[key]

    def cost(self) -> int:
        """``worst_case_cost`` of the form, with each question's cost kept
        between runs unless ``only`` says its rules may have changed."""
        total = 0
        for target in self.targets:
            if not _rules(target.field):
                continue
            key = id(target.field)
            stale = self.only is None or target.id in self.only
            if stale or key not in self._costs:
                self._costs[key] = _question_cost(target, self.maxima)
            total += self._costs[key]
        return total

    def add(
        self,
        field_id: str,
        path: str,
        message: str,
        rule: Optional[int],
        whole_field: bool = False,
    ):
        self.problems.append(
            FieldRuleProblem(field_id, path, message, rule, whole_field)
        )
        if self.limit is not None and len(self.problems) >= self.limit:
            raise _Enough()

    def misplaced(self) -> None:
        """Rules on anything that is not a question of a page-based form."""
        on_questions = {id(t.field) for t in self.targets}
        pending = list(_get(self.form, "fields") or [])
        while pending:
            field = pending.pop()
            pending.extend(_children(field))
            if _rules(field) and id(field) not in on_questions:
                self.add(
                    str(_get(field, "id") or ""),
                    "",
                    f"'{_title(field)}' cannot have rules: only questions on the "
                    "pages of a form (or in a repeating group) can.",
                    None,
                    whole_field=True,
                )

    def check(self) -> List[FieldRuleProblem]:
        self.misplaced()
        seen: Dict[str, str] = {}
        total = 0
        for target in self.targets:
            rules = _rules(target.field)
            if not rules:
                continue
            total += len(rules)
            checked = self.only is None or target.id in self.only
            if checked:
                self.target(target)
            for index, rule in enumerate(rules):
                rule_id = str(_get(rule, "id") or "")
                if rule_id in seen:
                    self.add(
                        target.id,
                        _pointer(index, "id"),
                        f"The rule id '{rule_id}' is used more than once in this form.",
                        index,
                    )
                seen.setdefault(rule_id, target.id)
                if checked:
                    self.rule(target, index, rule)
        self.cycles()
        cost = self.cost()
        if cost > RULE_COST_PER_RESPONSE:
            self.add(
                "",
                "",
                "These rules would take too long to check for each response "
                f"(cost {cost}, at most {RULE_COST_PER_RESPONSE}): use fewer or "
                "shorter rules, or fewer items in the repeating groups they are in.",
                None,
            )
        return self.problems

    def target(self, target: _Target) -> None:
        field = target.field
        name = _title(field)
        if _get(field, "internal"):
            self.add(
                target.id,
                "",
                f"'{name}' is an internal field: rules apply to what respondents "
                "answer.",
                None,
                whole_field=True,
            )
        elif _type(field) in NOT_RULE_TARGETS:
            self.add(
                target.id,
                "",
                f"'{name}' cannot have rules: rules apply to questions with one "
                "answer (not content, calculations, groups, matrices, uploads, "
                "tables or payments).",
                None,
                whole_field=True,
            )

    def rule(self, target: _Target, index: int, rule: Any) -> None:
        field = target.field
        name = _title(field)
        when = _get(rule, "when")
        if _get(when, "expression") is not None:
            self.expression(
                target, index, _get(when, "expression"), ("when", "expression")
            )
        else:
            for c, condition in enumerate(_get(when, "conditions") or []):
                self.condition(target, index, c, condition)
        then = _get(rule, "then")
        if _has_value_effect(rule):
            problem = None
            if target.group is not None:
                problem = (
                    f"'{name}' is in a repeating group: rules cannot lock or set "
                    "the value of a group's questions."
                )
            elif _type(field) not in VALUE_TYPES:
                problem = (
                    f"Rules can lock or set the value of short and long text, "
                    f"number, date, day, time, currency, yes/no and single-choice "
                    f"questions, not '{name}'."
                )
            elif _multiple(field):
                problem = (
                    f"'{name}' allows several choices: rules can only set the "
                    "value of a single-choice question."
                )
            if problem:
                key = "setValue" if _get(then, "set_value") is not None else "readOnly"
                self.add(target.id, _pointer(index, "then", key), problem, index)
            else:
                self.set_value(target, index, _get(then, "set_value"))
        for key, name_key in (("title", "title"), ("description", "description")):
            text = _get(then, key)
            if isinstance(text, str):
                self.pipes(target, index, text, ("then", name_key))

    def condition(self, target: _Target, index: int, c: int, condition: Any) -> None:
        here = (index, "when", "conditions", c)
        name = _title(target.field)
        source_id = str(_get(condition, "field_id") or "")
        comparison = _get(condition, "comparison")
        if comparison not in COMPARISONS:
            self.add(
                target.id,
                _pointer(*here, "comparison"),
                f"A rule of '{name}' has a condition without a known comparison.",
                index,
            )
        if not source_id:
            self.add(
                target.id,
                _pointer(*here, "fieldId"),
                f"A condition of a rule of '{name}' needs a question.",
                index,
            )
            return
        if source_id == target.id:
            self.add(
                target.id,
                _pointer(*here, "fieldId"),
                f"A rule of '{name}' cannot depend on the question's own answer.",
                index,
            )
            return
        source = self.by_id.get(source_id)
        if source is None:
            what = "a page" if source_id in self.pages else "no question"
            self.add(
                target.id,
                _pointer(*here, "fieldId"),
                f"A rule of '{name}' uses '{source_id}', which is {what} of this "
                "form.",
                index,
            )
            return
        source_name = _title(source.field)
        if _get(source.field, "internal"):
            self.add(
                target.id,
                _pointer(*here, "fieldId"),
                f"A rule of '{name}' uses the internal field '{source_name}': "
                "respondents never answer internal fields.",
                index,
            )
            return
        if source.group is not None and source.group_id != target.group_id:
            self.add(
                target.id,
                _pointer(*here, "fieldId"),
                f"A rule of '{name}' uses '{source_name}', which is asked once "
                "per item of a repeating group: outside the group, use the "
                "group itself with groupMode COUNT, ANY or ALL.",
                index,
            )
            return
        group_mode = _get(condition, "group_mode")
        is_group = _is_repeating_group(source.field)
        if is_group and group_mode not in GROUP_MODES:
            self.add(
                target.id,
                _pointer(*here, "groupMode"),
                f"'{source_name}' is a repeating group: a condition on it needs "
                "groupMode COUNT, ANY or ALL.",
                index,
            )
        elif not is_group and group_mode:
            self.add(
                target.id,
                _pointer(*here, "groupMode"),
                f"groupMode only applies to repeating groups, not '{source_name}'.",
                index,
            )
        elif is_group and group_mode in ("ANY", "ALL"):
            child = str(_get(condition, "child_field_id") or "")
            if child not in {str(_get(c, "id")) for c in _children(source.field)}:
                self.add(
                    target.id,
                    _pointer(*here, "childFieldId"),
                    f"An ANY/ALL condition on '{source_name}' needs childFieldId: "
                    "one of the group's questions.",
                    index,
                )
            if target.group_id == source.id:
                self.add(
                    target.id,
                    _pointer(*here, "fieldId"),
                    f"A rule of '{name}' cannot use its own repeating group.",
                    index,
                )
        elif is_group and target.group_id == source.id:
            self.add(
                target.id,
                _pointer(*here, "fieldId"),
                f"A rule of '{name}' cannot use its own repeating group.",
                index,
            )

    def expression(
        self, target: _Target, index: int, ast: Any, where: Tuple[str, ...]
    ) -> None:
        name = _title(target.field)
        structural = validate_expression(ast)
        if structural:
            for problem in structural:
                self.add(
                    target.id,
                    _pointer(index, *where) + problem.path,
                    f"A rule of '{name}': {problem.message}",
                    index,
                )
            return
        # inside an item, a sibling's id reads that item's answer
        siblings = self.siblings(target) if target.group is not None else ()

        def reads(key: str) -> bool:
            return key in self.known or key in siblings

        keys = expression_variables(ast)
        if len(keys) > RULE_VARIABLES_MAX:
            self.add(
                target.id,
                _pointer(index, *where),
                f"A rule of '{name}' reads {len(keys)} variables; an expression "
                f"can read at most {RULE_VARIABLES_MAX}.",
                index,
            )
            return
        for key in keys:
            if reads(key) and not _is_own_key(key, target.id) and key not in self.internal:
                continue
            path = _pointer(index, *where) + _var_pointer(ast, key)
            if _is_own_key(key, target.id):
                self.add(
                    target.id,
                    path,
                    f"A rule of '{name}' cannot read the question's own value.",
                    index,
                )
            elif key in self.internal:
                self.add(
                    target.id,
                    path,
                    f"A rule of '{name}' uses an internal field: respondents "
                    "never answer internal fields.",
                    index,
                )
            elif not reads(key):
                self.add(
                    target.id,
                    path,
                    f"A rule of '{name}' uses '{key}', which is not a question, "
                    "calculation or hidden field it can read.",
                    index,
                )

    def set_value(self, target: _Target, index: int, set_value: Any) -> None:
        if set_value is None:
            return
        field = target.field
        name = _title(field)
        here = (index, "then", "setValue")
        expression = _get(set_value, "expression")
        if expression is not None:
            if _type(field) in CHOICE_TYPES:
                self.add(
                    target.id,
                    _pointer(*here, "expression"),
                    f"'{name}' is a choice question: a rule sets it to one of its "
                    "options with 'const' (the option's id), not an expression.",
                    index,
                )
                return
            self.expression(
                target, index, expression, ("then", "setValue", "expression")
            )
            return
        const = _get(set_value, "const")
        if value_answer(field, const) is None:
            what = {
                "number": "a number",
                "date": "a date written as YYYY-MM-DD",
                "day": "a date written as YYYY-MM-DD",
                "time": "a time written as HH:MM (24-hour)",
                "currency": "an amount such as 12.50 (in the question's first currency)",
                "yes_no": "true or false",
                "multiple_choice": "the id of one of its options",
                "dropdown": "the id of one of its options",
            }.get(_type(field), "a text")
            self.add(
                target.id,
                _pointer(*here, "const"),
                f"A rule of '{name}' sets a value that does not fit it: use {what}.",
                index,
            )

    def pipes(self, target: _Target, index: int, text: str, where: Tuple[str, ...]):
        name = _title(target.field)
        siblings = _sibling_ids(target) if target.group is not None else set()
        for kind, key in _PIPE.findall(text):
            ok = True
            if kind == "hidden":
                ok = key in self.hidden_names
            elif kind == "group":
                group = self.by_id.get(key.split(":", 1)[0])
                ok = group is not None and _is_repeating_group(group.field)
            else:
                source = self.by_id.get(key)
                ok = (
                    source is not None
                    and not _get(source.field, "internal")
                    and (source.group is None or key in siblings)
                )
            if not ok:
                self.add(
                    target.id,
                    _pointer(index, *where),
                    f"A rule of '{name}' pipes '{key}', which this form does not "
                    "have (or the text cannot show).",
                    index,
                )

    def cycles(self) -> None:
        """Set values and calculations must not depend on each other in a
        circle. Circles of calculations alone are the calculations' to
        report."""
        nodes = [t for t in self.targets if _is_value_node(t)]
        if not nodes:
            return
        edges: Dict[str, Set[str]] = {}
        for calc in calculated_fields(self.form):
            key = str(_get(calc, "id"))
            edges[key] = set(
                expression_variables(_get(_get(calc, "properties"), "expression"))
            )
        for node in nodes:
            edges[node.id] = {
                key
                for rule in _rules(node.field)
                if _has_value_effect(rule)
                for key in _rule_reads(rule)
            }
        edges = {
            key: {r for r in refs if r in edges and r != key}
            for key, refs in edges.items()
        }
        reported: Set[frozenset] = set()
        for node in nodes:
            cycle = _cycle_through(node.id, edges)
            if cycle is None or frozenset(cycle) in reported:
                continue
            reported.add(frozenset(cycle))
            names = [
                _title(self.by_id[key].field) if key in self.by_id else key
                for key in cycle
            ]
            self.add(
                node.id,
                "",
                "Set values and calculations cannot depend on each other in a "
                "circle (" + " → ".join(f"'{n}'" for n in names + names[:1]) + ").",
                None,
            )


def _cycle_through(start: str, edges: Dict[str, Set[str]]) -> Optional[List[str]]:
    """A path from ``start`` back to itself, or None (iterative DFS)."""
    stack: List[Tuple[str, List[str]]] = [(start, [start])]
    seen: Set[str] = set()
    while stack:
        node, path = stack.pop()
        for ref in sorted(edges.get(node, ())):
            if ref == start:
                return path
            if ref not in seen:
                seen.add(ref)
                stack.append((ref, path + [ref]))
    return None


def _var_pointer(ast: Any, key: str) -> str:
    """The JSON pointer of the first ``{"var": key}`` in an AST (breadth
    first). Only worked out for a problem that is reported."""
    pending: Deque[Tuple[Any, str]] = deque([(ast, "")])
    while pending:
        node, path = pending.popleft()
        if not isinstance(node, dict) or len(node) != 1:
            continue
        op, value = next(iter(node.items()))
        here = path + _pointer(op)
        if op == "var" and value == key:
            return here
        if isinstance(value, list):
            pending.extend((child, f"{here}/{i}") for i, child in enumerate(value))
    return ""


def field_rule_problems(
    form: Any,
    limit: Optional[int] = PROBLEMS_MAX,
    only: Optional[Collection[str]] = None,
) -> List[FieldRuleProblem]:
    """Problems with the rules of a form (see the module doc), at most
    ``limit`` (None: all; only after the form-wide cap holds). ``only``
    (question ids) checks the rules of those questions alone, plus what spans
    the form (rule ids, circles, cost): for a caller that changed just them
    and must not pay for every rule of the form again."""
    if not _total_rules(form):
        return []
    return field_rule_checker(form, limit, only).run()


def field_rule_checker(
    form: Any,
    limit: Optional[int] = PROBLEMS_MAX,
    only: Optional[Collection[str]] = None,
) -> _Checker:
    """A checker for ``form`` (``.run()`` gives ``field_rule_problems``). Run
    it before and after replacing the rules of the questions in ``only``, and
    nothing that does not depend on them is worked out twice."""
    return _Checker(form, limit, only)


def _total_rules(form: Any) -> int:
    return sum(len(_rules(field)) for field in _walk(form))


def _walk(form: Any) -> Iterable[Any]:
    pending = list(_get(form, "fields") or [])
    while pending:
        field = pending.pop()
        yield field
        pending.extend(_children(field))


def _rule_signature(rule: Any) -> Any:
    return rule.model_dump() if hasattr(rule, "model_dump") else rule


def _stored_rules(form: Any) -> Dict[Tuple[str, str], Counter]:
    """The rules of ``form`` by ``(question id, rule id)``, each as what makes
    it the same rule: its content, and which question it is on (the
    question's id), so a rule that moved to another question reads as a
    different one. The question's type does not count: changing it keeps a
    rule the new type still accepts (one it cannot carry is dropped by the
    save before this is asked), so with the flag off a type change never
    blocks a save. Where the question sits (its page or group) does not
    count either: moving a question keeps its rules as they are."""
    stored: Dict[Tuple[str, str], Counter] = {}
    for field in _walk(form):
        for rule in _rules(field):
            signature = json.dumps(
                _rule_signature(rule),
                sort_keys=True,
                default=str,
            )
            key = (str(_get(field, "id")), str(_get(rule, "id")))
            stored.setdefault(key, Counter())[signature] += 1
    return stored


def prune_field_rules(form: Any) -> List[FieldRuleProblem]:
    """Drop every rule with a problem of its own (references, targets,
    values), in place, and return the first problem of each dropped rule.
    A question that cannot carry rules at all (internal, not a question of a
    page or group, of a type without rules) loses every one of them, so
    marking a question internal never leaves rules the save would refuse.
    Form-wide problems (caps, circles, cost) are left to the check."""
    problems = field_rule_problems(form, limit=None)
    first: Dict[Tuple[str, int], FieldRuleProblem] = {}
    whole: Dict[str, FieldRuleProblem] = {}
    for problem in problems:
        if problem.whole_field and problem.field_id:
            whole.setdefault(problem.field_id, problem)
        elif problem.rule is not None:
            first.setdefault((problem.field_id, problem.rule), problem)
    if not first and not whole:
        return []
    owners = {key[0] for key in first} | set(whole)
    dropped: List[FieldRuleProblem] = []
    for field in _walk(form):
        field_id = str(_get(field, "id"))
        rules = _rules(field)
        if not rules or field_id not in owners:
            continue
        kept = []
        for index, rule in enumerate(rules):
            problem = whole.get(field_id) or first.get((field_id, index))
            if problem is None:
                kept.append(rule)
                continue
            dropped.append(
                FieldRuleProblem(field_id, f"/{index}", problem.message, index)
            )
        properties = _get(field, "properties")
        if isinstance(properties, dict):
            properties["rules"] = kept or None
        else:
            properties.rules = kept or None
    return dropped


def strip_field_rules(form: Any) -> int:
    """Remove every field rule from ``form``, in place; how many there were.
    For writers that never bring rules (provider imports): whatever such a
    payload holds, no rule comes in through them."""
    removed = 0
    for field in _walk(form):
        rules = _rules(field)
        if not rules:
            continue
        removed += len(rules)
        properties = _get(field, "properties")
        if isinstance(properties, dict):
            properties["rules"] = None
        else:
            properties.rules = None
    return removed


def _refuse(problems: List[FieldRuleProblem]) -> None:
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        content={
            "code": ERROR_CODE,
            "message": " ".join(p.message for p in problems),
            "errors": [p.as_json() for p in problems],
        },
    )


def ensure_valid_field_rules(form: Any, drop: bool = False) -> List[Dict[str, Any]]:
    """422 ``invalid_field_rules`` with the problems (field id, JSON pointer
    into its rules, message; at most ``PROBLEMS_MAX``). ``drop`` (the
    builder's whole-form save, a copy, a template) drops every broken rule
    instead and returns them (``fieldId``, ``ruleId``, ``message``); only
    form-wide problems (caps, circles, cost) still refuse. Nothing broken is
    stored either way. CPU-bound: run it off the event loop."""
    dropped: List[Dict[str, Any]] = []
    if drop and _total_rules(form) <= FORM_FIELD_RULES_MAX:
        rules_by_field = {
            str(_get(field, "id")): _rules(field) for field in _walk(form)
        }
        for problem in prune_field_rules(form):
            dropped.append(
                {
                    "fieldId": problem.field_id,
                    "ruleId": _dropped_rule_id(rules_by_field, problem),
                    "message": problem.message,
                }
            )
        if dropped:
            logger.info("Dropped {} broken field rule(s) on save", len(dropped))
    problems = field_rule_problems(form)
    if problems:
        _refuse(problems)
    return dropped


def _dropped_rule_id(
    rules_by_field: Mapping[str, List[Any]], problem: FieldRuleProblem
) -> Optional[str]:
    rules = rules_by_field.get(problem.field_id) or []
    if problem.rule is not None and problem.rule < len(rules):
        return str(_get(rules[problem.rule], "id"))
    return None


def new_or_changed_rules(form: Any, existing: Any = None) -> List[Tuple[str, str]]:
    """``(field id, rule id)`` of the rules ``form`` has that ``existing``
    (the stored version, or None) does not have exactly as they are: the same
    content, on a question of the same id (whatever its type, and wherever it
    sits: moving a question to another page or group changes no rule), in the same order on
    that question (the last active rule wins, so an order change is a change:
    every rule of that question counts)."""
    stored = _stored_rules(existing) if existing is not None else {}
    changed = [
        key
        for key, signatures in _stored_rules(form).items()
        if stored.get(key) != signatures
    ]
    before = _rule_orders(existing) if existing is not None else {}
    for field_id, ids in _rule_orders(form).items():
        old = before.get(field_id, [])
        kept_now = [rule_id for rule_id in ids if rule_id in old]
        kept_then = [rule_id for rule_id in old if rule_id in ids]
        if kept_now != kept_then:
            changed.extend(
                (field_id, rule_id)
                for rule_id in ids
                if (field_id, rule_id) not in changed
            )
    return changed


def _rule_orders(form: Any) -> Dict[str, List[str]]:
    return {
        str(_get(field, "id")): [str(_get(rule, "id")) for rule in _rules(field)]
        for field in _walk(form)
        if _rules(field)
    }


def field_rules_enabled() -> bool:
    """Is ``FIELD_RULES_ENABLED`` on: may rules be created or changed?"""
    from backend.config import settings

    return bool(getattr(settings, "FIELD_RULES_ENABLED", False))


def ensure_rules_allowed(form: Any, existing: Any = None) -> None:
    """While ``FIELD_RULES_ENABLED`` is off, refuse (422
    ``field_rules_disabled``) a save that brings new or changed rules. Rules
    already stored, unchanged, pass (and are still enforced)."""
    if field_rules_enabled():
        return
    changed = new_or_changed_rules(form, existing)
    if changed:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": DISABLED_CODE,
                "message": DISABLED_MESSAGE,
                "errors": [
                    {"fieldId": field_id, "ruleId": rule_id}
                    for field_id, rule_id in changed[:PROBLEMS_MAX]
                ],
            },
        )


DISABLED_MESSAGE = (
    "Field rules cannot be created or changed on this server yet "
    "(FIELD_RULES_ENABLED is off). Rules already saved are kept."
)
