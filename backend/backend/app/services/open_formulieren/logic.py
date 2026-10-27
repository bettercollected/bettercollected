"""Visibility from the file's conditions and JSON logic, as data.

Nothing here evaluates anything: a JSON logic expression is walked as a tree
of plain values and matched against a fixed table of operators
(``mapping.COMPARISONS``). What does not fit the small subset we translate is
refused with a reason code and reported by the caller; it is never run.

The subset: one comparison of a component's answer with a literal, or an
``and`` / ``or`` of up to ten such comparisons (no nesting); and the two
visibility outcomes of a rule (a component shown or hidden). Our forms hold
one visibility rule per question, so the rules that meet on one component are
reduced to one or reported as conflicting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

from backend.app.services.open_formulieren.numbers import as_plain, to_number
from backend.app.services.open_formulieren.mapping import (
    COMPARISONS,
    KIND_COMPARISONS,
    NEGATIONS,
    NO,
    YES,
    Reason,
)

MAX_CONDITIONS = 10

# comparisons of a bare variable ("is it set?"), turned into ones our rules
# have once the answer kind is known
TRUTHY = "IS_TRUTHY"
FALSY = "IS_FALSY"


class Unsupported(Exception):
    """A rule or condition outside the subset; ``reason`` is a report code."""

    def __init__(self, reason: str, **detail: Any) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class Cond:
    """One comparison of a component's answer with a literal."""

    source: str  # the component key
    comparison: str  # IS_EQUAL ... or TRUTHY / FALSY
    value: Any = None
    # ``topics.news`` (a selectboxes option read as a boolean)
    option: Optional[str] = None
    # a simple ``conditional``: its ``eq`` names an option when the source
    # turns out to be a selectboxes component
    eq_is_option: bool = False


@dataclass(frozen=True)
class Trigger:
    operator: str  # AND | OR
    conds: Tuple[Cond, ...]


@dataclass(frozen=True)
class Rule:
    """A visibility rule on one question: SHOW it (hidden until the
    conditions hold) or HIDE it (visible until they hold)."""

    action: str  # SHOW | HIDE
    operator: str  # AND | OR
    conds: Tuple[Cond, ...]


@dataclass
class Decision:
    rule: Optional[Rule] = None
    # a reason to report instead of (or beside) the rule
    problem: Optional[str] = None
    always_hidden: bool = False
    conflicts: List[str] = field(default_factory=list)


# ------------------------------------------------------------- the trigger


def _var(node: Any) -> Optional[str]:
    if isinstance(node, dict) and len(node) == 1 and "var" in node:
        value = node["var"]
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        if isinstance(value, str) and value and len(value) <= 200:
            return value
    return None


def _split(name: str) -> Tuple[str, Optional[str]]:
    head, _, rest = name.partition(".")
    return head, (rest or None)


def _literal(node: Any) -> Tuple[bool, Any]:
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        # a number we cannot use (huge) is not a literal of the subset
        return (to_number(node) is not None), node
    if isinstance(node, str):
        return len(node) <= 500, node
    if node is None or isinstance(node, bool):
        return True, node
    return False, None


def parse_comparison(node: Any) -> Cond:
    if not isinstance(node, dict) or len(node) != 1:
        raise Unsupported(Reason.TRIGGER)
    operator, args = next(iter(node.items()))
    if operator in COMPARISONS:
        if not isinstance(args, list) or len(args) != 2:
            raise Unsupported(Reason.TRIGGER)
        name = _var(args[0])
        ok, value = _literal(args[1])
        if name is None or not ok:
            raise Unsupported(Reason.TRIGGER)
        source, option = _split(name)
        comparison = COMPARISONS[operator]
        # == null / == "" ask whether the answer is empty
        if comparison in ("IS_EQUAL", "IS_NOT_EQUAL") and (value is None or value == ""):
            comparison = "IS_EMPTY" if comparison == "IS_EQUAL" else "IS_NOT_EMPTY"
            value = None
        return Cond(source, comparison, value, option)
    if operator in ("!", "!!"):
        inner = args[0] if isinstance(args, list) and len(args) == 1 else args
        name = _var(inner)
        if name is None:
            raise Unsupported(Reason.TRIGGER)
        source, option = _split(name)
        return Cond(source, FALSY if operator == "!" else TRUTHY, None, option)
    raise Unsupported(Reason.TRIGGER)


def parse_trigger(expression: Any) -> Trigger:
    """The trigger of a rule as conditions, or ``Unsupported``."""
    if isinstance(expression, dict) and len(expression) == 1:
        operator, args = next(iter(expression.items()))
        if operator in ("and", "or"):
            if not isinstance(args, list) or not 1 <= len(args) <= MAX_CONDITIONS:
                raise Unsupported(Reason.TRIGGER)
            return Trigger(
                "AND" if operator == "and" else "OR",
                tuple(parse_comparison(a) for a in args),
            )
    return Trigger("AND", (parse_comparison(expression),))


def simple_conditional(conditional: Any) -> Optional[Tuple[bool, Cond]]:
    """``(show, condition)`` of a component's ``conditional`` object, or None
    when it is not complete (a missing ``show``, ``when`` or ``eq`` means no
    condition)."""
    if not isinstance(conditional, dict):
        return None
    show, when, eq = conditional.get("show"), conditional.get("when"), conditional.get(
        "eq"
    )
    if not isinstance(show, bool) or not isinstance(when, str) or not when:
        return None
    if eq is None or isinstance(eq, (dict, list)):
        return None
    return show, Cond(_split(when)[0], "IS_EQUAL", eq, None, True)


# ---------------------------------------------------- reading an answer kind


_number = to_number


def translate(cond: Cond, source: Any) -> Tuple[str, Any]:
    """The comparison and value one of our rules uses for ``cond`` on the
    question ``source`` (an ``importer.Question``), or ``Unsupported``."""
    rule = source.rule
    kind = rule.kind
    comparison, value = cond.comparison, cond.value
    option = cond.option
    if cond.eq_is_option and source.of_type == "selectboxes":
        option, value, comparison = str(cond.value), True, "IS_EQUAL"

    if option is not None:
        if source.of_type != "selectboxes" or option not in source.choices:
            raise Unsupported(Reason.VALUE)
        if comparison not in ("IS_EQUAL", "IS_NOT_EQUAL") or not isinstance(
            value, bool
        ):
            raise Unsupported(Reason.VALUE)
        chosen = (comparison == "IS_EQUAL") == value
        return ("IS_EQUAL" if chosen else "IS_NOT_EQUAL"), source.choices[option]

    if comparison == TRUTHY:
        comparison = "IS_NOT_EMPTY"
    elif comparison == FALSY:
        comparison = "IS_EMPTY"

    if kind == "yes_no":
        if cond.comparison in (TRUTHY, FALSY):
            return "IS_EQUAL", YES if cond.comparison == TRUTHY else NO
        if comparison not in ("IS_EQUAL", "IS_NOT_EQUAL"):
            raise Unsupported(Reason.VALUE)
        text = {"true": YES, "false": NO}.get(str(value).strip().lower())
        if isinstance(value, bool):
            text = YES if value else NO
        if text is None:
            raise Unsupported(Reason.VALUE)
        return comparison, text

    if comparison not in KIND_COMPARISONS.get(kind, frozenset()):
        raise Unsupported(Reason.VALUE)
    if comparison in ("IS_EMPTY", "IS_NOT_EMPTY"):
        return comparison, None
    if kind == "choice":
        text = source.choices.get(str(value)) if value is not None else None
        if text is None:
            raise Unsupported(Reason.VALUE)
        return comparison, text
    if kind == "number":
        number = _number(value)
        if number is None:
            raise Unsupported(Reason.VALUE)
        return comparison, as_plain(number)
    if value is None or isinstance(value, bool):
        raise Unsupported(Reason.VALUE)
    return comparison, str(value)


# ------------------------------------------------------- reducing the rules


def complementary(a: Trigger, b: Trigger) -> bool:
    """Whether ``b`` holds exactly when ``a`` does not (one comparison each,
    the same answer and value, opposite comparisons)."""
    if len(a.conds) != 1 or len(b.conds) != 1:
        return False
    x, y = a.conds[0], b.conds[0]
    if (x.source, x.option, x.value) != (y.source, y.option, y.value):
        return False
    if x.eq_is_option != y.eq_is_option:
        return False
    return NEGATIONS.get(x.comparison) == y.comparison or (
        {x.comparison, y.comparison} == {TRUTHY, FALSY}
    )


def merge_any(triggers: List[Trigger]) -> Optional[Trigger]:
    """One trigger that holds when any of ``triggers`` does, when that can be
    said in our one-rule shape; None otherwise."""
    if len(triggers) == 1:
        return triggers[0]
    conds: List[Cond] = []
    for trigger in triggers:
        if len(trigger.conds) > 1 and trigger.operator != "OR":
            return None
        conds.extend(trigger.conds)
    return Trigger("OR", tuple(conds)) if len(conds) <= MAX_CONDITIONS else None


def decide(
    default_hidden: bool,
    conditional: Optional[Tuple[bool, Cond]],
    logic: List[Tuple[Trigger, bool]],
) -> Decision:
    """The one visibility rule of a question, from its simple ``conditional``
    (when complete, it decides the starting state, as in the source) and the
    rules that show or hide it (``logic``: trigger, hidden-state)."""
    if conditional is not None:
        # a complete ``conditional`` decides alone: the ``hidden`` flag is only
        # read when there is none (open-forms 4.0.6 formio/visibility.py:59-62,
        # ``is_hidden``; what counts as complete: ``get_conditional``, 23-41)
        show, cond = conditional
        decision = Decision(Rule("SHOW" if show else "HIDE", "AND", (cond,)))
        if logic:
            decision.conflicts.append(Reason.CONFLICT)
        return decision
    shows = [t for t, hidden in logic if not hidden]
    hides = [t for t, hidden in logic if hidden]
    if default_hidden:
        if not shows:
            return Decision(always_hidden=True)
        if not hides:
            merged = merge_any(shows)
        elif len(shows) == 1 and len(hides) == 1 and complementary(shows[0], hides[0]):
            merged = shows[0]
        else:
            return Decision(problem=Reason.CONFLICT)
        if merged is None:
            return Decision(problem=Reason.CONFLICT)
        return Decision(Rule("SHOW", merged.operator, merged.conds))
    if not hides:
        # showing a question that is visible anyway changes nothing
        return Decision()
    if not shows:
        merged = merge_any(hides)
    elif len(shows) == 1 and len(hides) == 1 and complementary(hides[0], shows[0]):
        merged = hides[0]
    else:
        return Decision(problem=Reason.CONFLICT)
    if merged is None:
        return Decision(problem=Reason.CONFLICT)
    return Decision(Rule("HIDE", merged.operator, merged.conds))


def combine(chain: List[Rule]) -> Tuple[Optional[Rule], bool]:
    """One rule for a question from the rules of its enclosing layout
    components and its own, last the question's own: ``(rule, conflict)``.
    All SHOW rules need every condition (AND); all HIDE rules need any
    (OR). A mix, or a rule whose own operator does not fit, is a conflict:
    the question keeps its own rule."""
    if not chain:
        return None, False
    if len(chain) == 1:
        return chain[0], False
    actions = {r.action for r in chain}
    if len(actions) == 1:
        action = actions.pop()
        wanted = "AND" if action == "SHOW" else "OR"
        if all(len(r.conds) == 1 or r.operator == wanted for r in chain):
            conds = tuple(c for r in chain for c in r.conds)
            if len(conds) <= MAX_CONDITIONS:
                return Rule(action, wanted, conds), False
    return chain[-1], True
