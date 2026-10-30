"""Field rules ("logic actions"): the server's replay and save checks.

A question may carry ordered rules at ``properties.rules`` (common
``FieldRule``): ``when`` (the conditions of ``properties.logic``, or an
expressions-v1 ``expression`` that is active when truthy) and ``then`` (at
least one of ``required``, ``readOnly``, ``title``, ``description``,
``setValue``). Spec: docs/spec/README.md "Field rules". The webapp twin is to
come; until then the server is the only evaluator, and the shared cases in
``docs/spec/answer-validation.cases.json`` (checks ``fieldRules``) pin the
semantics for it.

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
nodes, inputs over 10,000 characters or 1,000 items count as empty), at most
``FIELD_RULES_MAX`` rules per field and ``FORM_FIELD_RULES_MAX`` per form are
read, and callers run the replay off the event loop.
"""

import re
from dataclasses import dataclass, field as dataclass_field
from decimal import Decimal
from http import HTTPStatus
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple

from common.expressions import (
    ExpressionError,
    evaluate_expression,
    format_expression_value,
    validate_expression,
)
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
VALUE_TYPES = TEXT_TYPES | CHOICE_TYPES | {"number", "date", "yes_no"}
# Types that hold no answer a rule could apply to (content, pages, hidden
# and calculated fields): rules may not sit on them.
NOT_RULE_TARGETS = NOT_VARIABLES | {CALCULATED, GROUP}
_PIPE = re.compile(r"\{\{\s*(field|hidden|group)\s*:\s*([^|}]*?)\s*(?:\|[^}]*)?\}\}")
_ANSWER_TYPE = {
    "short_text": "text",
    "long_text": "text",
    "number": "number",
    "date": "date",
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


def _dangling(rule: Any, owner: str, scope: _Scope) -> bool:
    """Does the rule read something the form does not have, or its own
    field? Such a rule is never active."""
    when = _get(rule, "when")
    if _get(when, "expression") is not None:
        reads = expression_variables(_get(when, "expression"))
        if any(key not in scope.known or key == owner for key in reads):
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
    return any(key not in scope.known or key == owner for key in _value_reads(rule))


def _evaluate(ast: Any, scope: _Scope) -> Any:
    try:
        return evaluate_expression(ast, scope.variables, scope.context)
    except (ExpressionError, RecursionError):
        return None


def _is_active(rule: Any, owner: str, scope: _Scope) -> bool:
    if _dangling(rule, owner, scope):
        return False
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
            if value != value or value in (float("inf"), float("-inf")):
                return None
            return {**answer, "type": "number", "number": value}
        return None
    if field_type == "date":
        if is_iso_date(value):
            return {**answer, "type": "date", "date": value}
        return None
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
    for key in deps:
        deps[key] = {ref for ref in deps[key] if ref in by_id and ref != key}
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
        if not _is_active(rule, owner, scope):
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
    sources = logic_sources(slides or [])
    question_keys = _question_keys(form)
    states = FieldRuleStates()
    budget = [FORM_FIELD_RULES_MAX]
    read: Dict[int, List[Any]] = {
        id(target.field): _read_rules(target.field, budget) for target in targets
    }
    nodes = [target for target in targets if _is_value_node(target)]
    scope = _Scope(plain, variables, known, sources, context)

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
        answer = _set_value(field, setter, scope) if setter is not None else None
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
        sibling_ids = {str(_get(c, "id")) for c in children if _get(c, "id")}
        for index in range(_item_count(group, items)):
            item = items[index] if index < len(items) else {}
            item_scope = _Scope(
                {**plain, **item},
                {
                    **variables,
                    **{
                        str(_get(child, "id")): comparable_answer_value(
                            item.get(str(_get(child, "id"))), _type(child)
                        )
                        for child in children
                        if _get(child, "id")
                    },
                },
                known | sibling_ids,
                sources,
                context,
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
    a readable message and, for a problem of one rule, its position."""

    field_id: str
    path: str
    message: str
    rule: Optional[int] = None

    def as_json(self) -> Dict[str, str]:
        return {"fieldId": self.field_id, "path": self.path, "message": self.message}


def _pointer(*parts: Any) -> str:
    return "".join(
        "/" + str(part).replace("~", "~0").replace("/", "~1") for part in parts
    )


class _Checker:
    """Checks the rules of one form; see :func:`field_rule_problems`."""

    def __init__(self, form: Any):
        self.form = form
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

    def add(self, field_id: str, path: str, message: str, rule: Optional[int]):
        self.problems.append(FieldRuleProblem(field_id, path, message, rule))

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
                self.rule(target, index, rule)
        if total > FORM_FIELD_RULES_MAX:
            self.add(
                "",
                "",
                f"A form can have at most {FORM_FIELD_RULES_MAX} rules; this one "
                f"has {total}.",
                None,
            )
        self.cycles()
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
            )
        elif _type(field) in NOT_RULE_TARGETS:
            self.add(
                target.id,
                "",
                f"'{name}' cannot have rules: rules apply to questions with one "
                "answer (not content, calculations, groups, matrices, uploads, "
                "tables or payments).",
                None,
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
                    f"number, date, yes/no and single-choice questions, not "
                    f"'{name}'."
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
        known = set(self.known)
        if target.group is not None:
            # inside an item, a sibling's id reads that item's answer
            known |= _sibling_ids(target)
        for key in expression_variables(ast):
            path = _pointer(index, *where) + _var_pointer(ast, key)
            if key == target.id:
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
            elif key not in known:
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
    """The JSON pointer of the first ``{"var": key}`` in an AST."""
    pending: List[Tuple[Any, str]] = [(ast, "")]
    while pending:
        node, path = pending.pop(0)
        if not isinstance(node, dict) or len(node) != 1:
            continue
        op, value = next(iter(node.items()))
        here = path + _pointer(op)
        if op == "var" and value == key:
            return here
        if isinstance(value, list):
            pending.extend((child, f"{here}/{i}") for i, child in enumerate(value))
    return ""


def field_rule_problems(form: Any) -> List[FieldRuleProblem]:
    """Problems with the rules of a form (see the module doc)."""
    if not any(_rules(f) for f in _walk(form)):
        return []
    return _Checker(form).check()


def _walk(form: Any) -> Iterable[Any]:
    pending = list(_get(form, "fields") or [])
    while pending:
        field = pending.pop()
        yield field
        pending.extend(_children(field))


def _rule_signature(rule: Any) -> Any:
    return rule.model_dump() if hasattr(rule, "model_dump") else rule


def _stored_rules(form: Any) -> Dict[Tuple[str, str], Any]:
    return {
        (str(_get(field, "id")), str(_get(rule, "id"))): _rule_signature(rule)
        for field in _walk(form)
        for rule in _rules(field)
    }


def prune_field_rules(
    form: Any, only: Optional[Mapping[Tuple[str, str], Any]] = None
) -> int:
    """Drop the rules with problems of their own (references, targets,
    values), in place; with ``only``, just those among ``only`` (rules by
    ``(field id, rule id)``, as stored) that are unchanged. Returns how many
    were dropped. Form-wide problems (caps, circles) are left to the check."""
    dropped = 0
    for _ in range(FORM_FIELD_RULES_MAX + 1):
        bad: Dict[str, Set[int]] = {}
        for problem in field_rule_problems(form):
            if problem.rule is not None:
                bad.setdefault(problem.field_id, set()).add(problem.rule)
        removed = 0
        for field in _walk(form):
            positions = bad.get(str(_get(field, "id")))
            rules = _rules(field)
            if not positions or not rules:
                continue
            kept = []
            for index, rule in enumerate(rules):
                key = (str(_get(field, "id")), str(_get(rule, "id")))
                if index in positions and (
                    only is None or only.get(key) == _rule_signature(rule)
                ):
                    removed += 1
                    continue
                kept.append(rule)
            if len(kept) != len(rules):
                properties = _get(field, "properties")
                if isinstance(properties, dict):
                    properties["rules"] = kept or None
                else:
                    properties.rules = kept or None
        dropped += removed
        if not removed:
            break
    return dropped


def ensure_valid_field_rules(
    form: Any, existing: Any = None, drop: bool = False
) -> None:
    """422 ``invalid_field_rules`` with every problem (field id, JSON
    pointer into its rules, message). ``drop`` (a copy, a template) drops
    broken rules instead; with ``existing`` (the stored draft), a rule it
    already had, unchanged, that an edit elsewhere broke (its question was
    removed, moved or changed type) is dropped too."""
    if drop or existing is not None:
        dropped = prune_field_rules(form, None if drop else _stored_rules(existing))
        if dropped:
            logger.info("Dropped {} field rule(s) a form change left broken", dropped)
    problems = field_rule_problems(form)
    if problems:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            content={
                "code": ERROR_CODE,
                "message": " ".join(p.message for p in problems),
                "errors": [p.as_json() for p in problems],
            },
        )
