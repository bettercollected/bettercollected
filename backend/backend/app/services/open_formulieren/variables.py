"""User-defined variables that become calculated questions.

Open Formulieren holds a value the form computes in a *user-defined variable*:
a logic rule with an action of type ``variable`` whose value is a JSON logic
expression sets it. We have no such variable, but we have calculated
questions (``services/calculated_fields.py``, the expression language of
``docs/spec/expressions-v1.md``). A variable becomes one only when the file
says exactly one thing about it that expressions v1 can say too:

* one action in the whole file sets it, and nothing else writes to it (no
  prefill, no service fetch, no other action naming it);
* the rule that action belongs to always fires (its trigger is the literal
  ``true``): a condition would need "unchanged unless" semantics we do not
  have;
* it is a number (``int`` or ``float``) and its expression uses only
  ``+ - * /``, ``min`` and ``max`` (of plain answers or numbers), numbers and
  ``var`` of an imported number question or of another variable that
  qualifies (no cycles, set earlier in the file).

Everything else stays reported as ``user_variable_not_carried`` with a
``cause`` that says why. **Nothing here evaluates anything**: the expression
is walked as plain data and matched against a fixed table, never run (the
tests keep a model of the original's arithmetic to prove the translation
agrees with it, but the import itself has no evaluator for their language).

The format and the original's arithmetic are cited in
docs/open-formulieren.md (rule and action shapes, 4.0.6
``submissions/logic/actions.py:379-441``; the operators,
maykin-json-logic-py 0.16.1 ``json_logic/__init__.py``).
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from backend.app.services.open_formulieren import budget, limits

# the largest expression we translate: what counts against the import's work
# budget is every node and every character of a variable name
MAX_DEPTH = 12
MAX_NODES = 60
MAX_ARGS = 20
MAX_NAME = 200
# most variables that become calculated questions in one import: a form may
# hold this many (``calculated_fields.MAX_CALCULATED_FIELDS``)
MAX_CALCULATIONS = 50

NUMERIC_TYPES = frozenset({"int", "float"})


class Cause:
    """Why a variable did not become a calculated question (``detail.cause``
    of its ``user_variable_not_carried`` item)."""

    NO_RULE = "no_rule"  # nothing sets it
    SEVERAL = "several_rules"  # more than one action sets it
    OTHER_SOURCE = "other_source"  # prefill, service fetch, DMN, synchronise
    DUPLICATE = "duplicate_key"
    NOT_NUMERIC = "not_numeric"
    CONDITION = "condition"  # the rule only fires on a condition
    FROM_STEP = "trigger_from_step"
    OPERATOR = "operator"  # detail.operator
    OPERAND = "operand"
    TOO_COMPLEX = "too_complex"
    INITIAL_VALUE = "initial_value"  # a division leaves a non-empty start
    SOURCE_MISSING = "source_missing"  # detail.source
    SOURCE_NOT_NUMBER = "source_not_number"
    SOURCE_IN_GROUP = "source_in_group"
    SOURCE_MULTIPLE = "source_multiple"
    DEPENDS = "depends_on_variable"  # a variable that is not carried
    CYCLE = "cycle"  # in a circle of variables, or reads one
    ORDER = "order"  # reads a variable a later rule sets
    COLLISION = "key_collision"  # same key as a component
    TOO_MANY = "too_many"
    REJECTED = "rejected"  # the form's own rules refused it


class NotCarried(Exception):
    """A variable or expression outside what we translate."""

    def __init__(self, cause: str, **detail: Any) -> None:
        super().__init__(cause)
        self.cause = cause
        self.detail = detail


# a node of the parsed expression:
#   ("num", value)   a number literal
#   ("var", key)     the value of a component or variable
#   (op, children)   one of ``OPERATORS``
Node = Tuple[Any, ...]

# operator -> (fewest, most) arguments. The arities are the ones both sides
# give the same meaning to: ``-`` with one argument negates; the original
# returns the first argument of a one-argument ``/`` untouched and ignores a
# third argument of ``-``, neither of which we translate.
OPERATORS: Dict[str, Tuple[int, int]] = {
    "+": (2, MAX_ARGS),
    "*": (2, MAX_ARGS),
    "-": (1, 2),
    "/": (2, 2),
    "min": (1, MAX_ARGS),
    "max": (1, MAX_ARGS),
}
AGGREGATES = frozenset({"min", "max"})


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


# ------------------------------------------------------------ the expression


def _number(value: Any) -> Optional[Any]:
    """A JSON number we can hold exactly: finite, below 10^15, at most 15
    significant digits and 15 decimals (what expressions v1 keeps). Whole
    numbers come back as ints."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, int):
        return value if abs(value) < 10**15 else None
    if not math.isfinite(value):
        return None
    shortest = Decimal(repr(value)).normalize()
    _, digits, exponent = shortest.as_tuple()
    if len(digits) > 15 or exponent < -15 or abs(shortest) >= 10**15:
        return None
    return int(shortest) if shortest == shortest.to_integral_value() else value


def _name(node: Dict[str, Any]) -> Optional[str]:
    """The key of ``{"var": key}`` (or ``{"var": [key]}``); a default value or
    an empty key (the whole data) is not translated."""
    value = node.get("var")
    if isinstance(value, list) and len(value) == 1:
        value = value[0]
    if isinstance(value, str) and 0 < len(value) <= MAX_NAME:
        return value
    return None


class _Walk:
    def __init__(self) -> None:
        self.nodes = 0
        self.division = False

    def count(self, size: int = 0) -> None:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise NotCarried(Cause.TOO_COMPLEX)
        budget.charge(1 + size)

    def parse(self, node: Any, depth: int) -> Node:
        if depth > MAX_DEPTH:
            raise NotCarried(Cause.TOO_COMPLEX)
        self.count()
        number = _number(node)
        if number is not None:
            return ("num", number)
        if not isinstance(node, dict) or len(node) != 1:
            raise NotCarried(Cause.OPERAND)
        operator, args = next(iter(node.items()))
        if not isinstance(operator, str):
            raise NotCarried(Cause.OPERAND)
        if operator == "var":
            key = _name(node)
            if key is None:
                raise NotCarried(Cause.OPERAND)
            budget.charge(len(key))
            return ("var", key)
        if operator not in OPERATORS:
            # the operator is only ever reported as a short plain name
            raise NotCarried(Cause.OPERATOR, operator=operator[:40])
        # JSON logic lets a single argument stand without its list
        args = args if isinstance(args, list) else [args]
        low, high = OPERATORS[operator]
        if not low <= len(args) <= high:
            raise NotCarried(Cause.OPERAND, operator=operator)
        if operator == "/":
            self.division = True
        children = tuple(self.parse(a, depth + 1) for a in args)
        if operator in AGGREGATES and any(c[0] not in ("num", "var") for c in children):
            # "no answer in any argument = no result" is only said for plain
            # answers (see ``to_ast``)
            raise NotCarried(Cause.OPERAND, operator=operator)
        return (operator, children)


def parse_expression(expression: Any) -> Tuple[Node, bool]:
    """``(tree, divides)`` of a JSON logic expression, or ``NotCarried``."""
    walk = _Walk()
    tree = walk.parse(expression, 1)
    return tree, walk.division


def references(tree: Node) -> List[str]:
    """The keys a tree reads, in order of appearance, each once."""
    found: List[str] = []
    pending = [tree]
    while pending:
        node = pending.pop()
        if node[0] == "var":
            if node[1] not in found:
                found.append(node[1])
        elif node[0] != "num":
            pending.extend(reversed(node[1]))
    return found


def to_ast(tree: Node, ids: Mapping[str, str]) -> Any:
    """The expressions-v1 AST of a tree, each key replaced by its id in
    ``ids``.

    ``min`` and ``max`` need a guard: the original gives no result when any
    argument has no value, while v1's aggregates skip the unanswered ones. So
    ``min(a, b)`` becomes ``if(a == null or b == null, null, min(a, b))``
    (the other four operators already give no result for a missing value, in
    v1 as in the original)."""
    kind = tree[0]
    if kind == "num":
        return tree[1]
    if kind == "var":
        return {"var": ids[tree[1]]}
    args = [to_ast(child, ids) for child in tree[1]]
    if kind not in AGGREGATES:
        return {kind: args}
    guards = []
    seen: Set[str] = set()
    for child in tree[1]:
        if child[0] == "var" and child[1] not in seen:
            seen.add(child[1])
            guards.append({"==": [{"var": ids[child[1]]}, None]})
    core = {kind: args}
    if not guards:
        return core
    return {"if": [guards[0] if len(guards) == 1 else {"or": guards}, None, core]}


# ----------------------------------------------------- what the file says


@dataclass
class Info:
    """One user-defined variable of the file and what became of it."""

    key: str
    name: Any
    data_type: str
    rule_index: Optional[int] = None
    tree: Optional[Node] = None
    refs: Tuple[str, ...] = ()
    cause: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)
    # set by the importer once the calculated question exists
    converted: bool = False

    def fail(self, cause: str, **detail: Any) -> None:
        self.cause, self.detail = cause, detail

    @property
    def carried(self) -> bool:
        return self.cause is None


def _other_writers(action: Dict[str, Any]) -> Set[str]:
    """Keys of variables an action that is not a ``variable`` action writes
    to: the action's own target, a synchronisation's destination, a decision's
    output mapping."""
    names: Set[str] = set()
    target = action.get("variable")
    if isinstance(target, str) and target:
        names.add(target)
    config = _dict(_dict(action.get("action")).get("config"))
    destination = config.get("destination_variable")
    if isinstance(destination, str) and destination:
        names.add(destination)
    for mapping in _list(config.get("output_mapping"))[:200]:
        found = _dict(mapping).get("form_variable")
        if isinstance(found, str) and found:
            names.add(found)
    return names


def analyse(
    variables: List[Dict[str, Any]], rules: List[Dict[str, Any]], is_3x: bool
) -> Dict[str, Info]:
    """What the file alone says about each user-defined variable: whether
    one unconditional rule sets it with an expression we can translate.
    ``rules`` are in the file's order (the importer's, by ``order``). Whether
    its sources are questions we made is decided later (``resolve``)."""
    infos: Dict[str, Info] = {}
    duplicates: Set[str] = set()
    records: Dict[str, Dict[str, Any]] = {}
    for variable in variables:
        if variable.get("source") not in (None, "user_defined"):
            continue
        key = variable.get("key")
        if not isinstance(key, str) or not key:
            continue
        if key in infos:
            duplicates.add(key)
            continue
        data_type = variable.get("data_type")
        infos[key] = Info(key, variable.get("name"), data_type if isinstance(data_type, str) else "")
        records[key] = variable
    setters: Dict[str, List[Tuple[int, Dict[str, Any], Dict[str, Any]]]] = {}
    elsewhere: Set[str] = set()
    for index, rule in enumerate(rules):
        for raw in _list(rule.get("actions")):
            action = _dict(raw)
            body = _dict(action.get("action"))
            target = action.get("variable")
            if body.get("type") == "variable" and isinstance(target, str):
                setters.setdefault(target, []).append((index, rule, action))
            else:
                elsewhere |= _other_writers(action)
    for key, info in infos.items():
        record = records[key]
        found = setters.get(key, [])
        if key in duplicates:
            info.fail(Cause.DUPLICATE)
        elif (
            key in elsewhere
            or record.get("prefill_plugin")
            or record.get("prefill_attribute")
            or record.get("service_fetch_configuration")
        ):
            info.fail(Cause.OTHER_SOURCE)
        elif not found:
            info.fail(Cause.NO_RULE)
        elif len(found) > 1:
            info.fail(Cause.SEVERAL, rules=len(found))
        elif info.data_type not in NUMERIC_TYPES:
            info.fail(Cause.NOT_NUMERIC)
        else:
            index, rule, action = found[0]
            info.rule_index = index
            if is_3x and rule.get("trigger_from_step"):
                info.fail(Cause.FROM_STEP)
            elif rule.get("json_logic_trigger") is not True:
                info.fail(Cause.CONDITION)
            else:
                try:
                    tree, divides = parse_expression(_dict(action.get("action")).get("value"))
                except NotCarried as why:
                    info.fail(why.cause, **why.detail)
                else:
                    # a division by zero is an error in the original that
                    # leaves the variable as it was; here it has no value,
                    # which is the same only when it started with none
                    if divides and record.get("initial_value") is not None:
                        info.fail(Cause.INITIAL_VALUE)
                    else:
                        info.tree, info.refs = tree, tuple(references(tree))
    return infos


def consumed_rules(rules: List[Dict[str, Any]], infos: Mapping[str, Info]) -> Set[int]:
    """The rules whose every action is the one that sets a variable that is
    still a candidate: nothing else is left in them to report."""
    out: Set[int] = set()
    for index, rule in enumerate(rules):
        actions = _list(rule.get("actions"))
        if actions and all(_sets_candidate(_dict(a), index, infos) for a in actions):
            out.add(index)
    return out


def _sets_candidate(action: Dict[str, Any], index: int, infos: Mapping[str, Info]) -> bool:
    target = action.get("variable")
    if _dict(action.get("action")).get("type") != "variable" or not isinstance(target, str):
        return False
    info = infos.get(target)
    return info is not None and info.carried and info.rule_index == index


# --------------------------------------------------- against the questions


@dataclass(frozen=True)
class Source:
    """A question a variable reads: its id in the form and where it is
    (page position, order in the file)."""

    id: str
    pos: Tuple[int, int]


def resolve(
    infos: Mapping[str, Info],
    sources: Mapping[str, Source],
    unusable: Mapping[str, str],
    component_keys: Set[str],
) -> List[Info]:
    """The variables that become calculated questions, in an order where each
    comes after the ones it reads; every other candidate gets its cause.

    ``sources``: the questions a variable may read (key -> question);
    ``unusable``: keys of components that were imported but cannot be read
    (key -> cause); ``component_keys``: every component key of the file."""
    pending: Dict[str, Info] = {}
    for key, info in infos.items():
        if not info.carried:
            continue
        budget.check()
        if key in component_keys:
            info.fail(Cause.COLLISION)
            continue
        for ref in info.refs:
            if ref in infos:
                continue  # another variable: followed below
            if ref in sources:
                continue
            info.fail(unusable.get(ref, Cause.SOURCE_MISSING), source=ref)
            break
        else:
            pending[key] = info
    # the order in which they can be made: Kahn's algorithm, linear in the
    # variables and what they read, the earliest rule first
    dependents: Dict[str, List[str]] = {key: [] for key in pending}
    waiting: Dict[str, int] = {}
    for key, info in pending.items():
        deps = [r for r in info.refs if r in infos]
        waiting[key] = len(deps)
        for ref in deps:
            if ref in dependents:
                dependents[ref].append(key)

    def drop(key: str, cause: str, **detail: Any) -> None:
        """Remove a variable and, with it, every variable that reads it."""
        stack = [(key, cause, detail)]
        while stack:
            name, why, extra = stack.pop()
            info = pending.pop(name, None)
            if info is None:
                continue
            info.fail(why, **extra)
            stack.extend((d, Cause.DEPENDS, {"source": name}) for d in dependents[name])

    for key, info in list(pending.items()):
        for ref in info.refs:
            if ref in infos and ref not in pending:  # a variable that is not carried
                drop(key, Cause.DEPENDS, source=ref)
                break
    ready = [(info.rule_index or 0, key) for key, info in pending.items() if waiting[key] == 0]
    heapq.heapify(ready)
    ordered: List[Info] = []
    while ready:
        budget.check()
        _, key = heapq.heappop(ready)
        info = pending.get(key)
        if info is None:
            continue
        late = [r for r in info.refs if r in infos and (infos[r].rule_index or 0) >= (info.rule_index or 0)]
        if late:
            drop(key, Cause.ORDER, source=late[0])
            continue
        del pending[key]
        ordered.append(info)
        for dependent in dependents[key]:
            if dependent in pending:
                waiting[dependent] -= 1
                if waiting[dependent] == 0:
                    heapq.heappush(ready, (pending[dependent].rule_index or 0, dependent))
    for info in pending.values():
        info.fail(Cause.CYCLE)
    return ordered


__all__ = [
    "Cause",
    "Info",
    "MAX_CALCULATIONS",
    "NotCarried",
    "Source",
    "analyse",
    "consumed_rules",
    "parse_expression",
    "references",
    "resolve",
    "to_ast",
]
