"""User-defined variables that become calculated questions.

Only a variable set by one unconditional calculation that expressions v1 can
hold is carried (services/open_formulieren/variables.py); everything else keeps
being reported as ``user_variable_not_carried``, now with a ``cause``. All the
archives here are our own synthetic shapes.

``OriginalArithmetic`` below is a model of what the original does with the
operators we translate (maykin-json-logic-py 0.16.1, cited in
docs/open-formulieren.md); it lives in the tests only, and a property test
holds the translation to it. The import itself never evaluates anything."""

import random
from decimal import Decimal

import pytest

from backend.app.services.calculated_fields import (
    apply_calculated_fields,
    calculated_field_problems,
)
from backend.app.services.open_formulieren import budget, limits
from backend.app.services.open_formulieren import variables as V
from backend.app.services.open_formulieren.archive import read_archive
from backend.app.services.open_formulieren.errors import ImportRefused
from backend.app.services.open_formulieren.importer import build_draft
from common.expressions import evaluate_expression
from tests.app.open_formulieren.conftest import (
    CATASTROPHIC_SECONDS,
    archive_with,
    comp,
    eq,
    exec_guard,  # noqa: F401  (fixture)
    hide,
    no_deadline,  # noqa: F401  (fixture)
    rule,
)

import time

# ---------------------------------------------------------------- helpers


def setter(variable, value, uuid="a"):
    return {
        "uuid": uuid,
        "variable": variable,
        "form_step_uuid": None,
        "action": {"type": "variable", "value": value},
    }


def always(*actions, order=0):
    """A rule that fires on every evaluation: the literal ``true`` trigger
    (their format needs ``is_advanced`` for it)."""
    return {**rule(True, *actions, order=order), "is_advanced": True}


def uvar(key, data_type="float", initial=None, name=None, **extra):
    return {
        "key": key,
        "name": name if name is not None else key.capitalize(),
        "source": "user_defined",
        "data_type": data_type,
        "initial_value": initial,
        **extra,
    }


def num(key, **extra):
    return comp("number", key, **extra)


def var(key):
    return {"var": key}


def run(steps, rules=(), variables=(), version="4.0.6"):
    return build_draft(
        read_archive(
            archive_with(
                steps, logic=list(rules), variables=list(variables), version=version
            )
        )
    )


def items(built, **match):
    return [
        i for i in built.report.items if all(i.get(k) == v for k, v in match.items())
    ]


def calcs(built):
    """The calculated questions of the draft: ``(page, field)``."""
    return [
        (page, field)
        for page in built.form.fields
        for field in page.properties.fields
        if field.type.value == "calculated"
    ]


def titles(built):
    return [
        [f.title for f in page.properties.fields] for page in built.form.fields
    ]


def not_carried(built, key):
    found = items(built, kind="variable", key=key)
    assert len(found) == 1 and found[0]["reason"] == "user_variable_not_carried", found
    return found[0]["detail"]


def carried(built, key):
    found = items(built, kind="variable", key=key)
    assert len(found) == 1 and found[0]["reason"] == "user_variable_calculated", found
    return found[0]


def number_answer(field_id, value):
    return {field_id: {"field": {"id": field_id}, "type": "number", "number": value}}


def ids_by_title(built):
    return {f.title: f.id for page in built.form.fields for f in page.properties.fields}


def value_of(built, title, **answers):
    """The calculated question ``title``'s value for number answers given by
    question title (a missing one is unanswered)."""
    ids = ids_by_title(built)
    given = {}
    for name, value in answers.items():
        given.update(number_answer(ids[name], value))
    out = apply_calculated_fields(built.form, given, keep_empty=True)
    answer = out[ids[title]]
    for slot in ("number", "boolean", "text"):
        if answer.get(slot) is not None:
            return answer[slot]
    return None


TWO_NUMBERS = [[num("a", label="A"), num("b", label="B")]]


def one(expression, *, variables_extra=None, steps=None, **kw):
    """A build with one variable ``t`` set by an unconditional rule."""
    return run(
        steps or TWO_NUMBERS,
        [always(setter("t", expression))],
        [uvar("t", name="T", **(variables_extra or {}))],
        **kw,
    )


# ----------------------------------------------------- each operator -> v1


@pytest.mark.parametrize(
    "expression, expected",
    [
        ({"+": [var("a"), var("b")]}, {"+": ["A", "B"]}),
        ({"+": [var("a"), 5, var("b")]}, {"+": ["A", 5, "B"]}),
        ({"-": [var("a"), var("b")]}, {"-": ["A", "B"]}),
        ({"-": [var("a")]}, {"-": ["A"]}),
        ({"-": var("a")}, {"-": ["A"]}),
        ({"*": [var("a"), var("b")]}, {"*": ["A", "B"]}),
        ({"/": [var("a"), var("b")]}, {"/": ["A", "B"]}),
        ({"/": [var("a"), 4]}, {"/": ["A", 4]}),
        (
            {"min": [var("a"), var("b")]},
            {"if": [{"or": [{"==": ["A", None]}, {"==": ["B", None]}]}, None, {"min": ["A", "B"]}]},
        ),
        (
            {"max": [var("a"), 3]},
            {"if": [{"==": ["A", None]}, None, {"max": ["A", 3]}]},
        ),
        ({"max": [1, 3]}, {"max": [1, 3]}),
        # nested, and the spellings of a variable the format allows
        (
            {"+": [{"*": [var("a"), 2]}, {"-": [var("b"), {"var": ["a"]}]}]},
            {"+": [{"*": ["A", 2]}, {"-": ["B", "A"]}]},
        ),
        # a whole number written with a fraction is the whole number; others stay
        ({"+": [var("a"), 2.0]}, {"+": ["A", 2]}),
        ({"+": [var("a"), 0.1]}, {"+": ["A", 0.1]}),
        ({"+": [var("a"), -3]}, {"+": ["A", -3]}),
        (
            {"+": [{"min": [var("a"), var("b")]}, 1]},
            {"+": [{"if": [{"or": [{"==": ["A", None]}, {"==": ["B", None]}]}, None, {"min": ["A", "B"]}]}, 1]},
        ),
    ],
)
def test_each_operator_translates_to_its_expression(expression, expected):
    built = one(expression)
    ((page, field),) = calcs(built)
    ids = ids_by_title(built)
    names = {v: k for k, v in ids.items()}

    def named(node):
        if isinstance(node, dict) and set(node) == {"var"}:
            return names[node["var"]]
        if isinstance(node, dict):
            return {op: named(args) for op, args in node.items()}
        if isinstance(node, list):
            return [named(a) for a in node]
        return node

    got = named(field.properties.expression)
    # the expected shapes write a variable as its question's title
    assert got == expected
    assert calculated_field_problems(built.form) == []
    assert carried(built, "t")["detail"] == {"dataType": "float"}


def test_a_constant_or_a_copy_of_an_answer_is_a_calculation_too():
    built = one(7)
    assert calcs(built)[0][1].properties.expression == 7
    assert value_of(built, "T") == 7
    built = one({"var": "a"})
    assert value_of(built, "T", A=4) == 4 and value_of(built, "T") is None


def test_the_calculation_is_hidden_numbered_and_named_after_the_variable():
    built = one({"+": [var("a"), var("b")]})
    ((page, field),) = calcs(built)
    assert field.title == "T"
    assert field.properties.hidden_from_respondents is True
    assert field.properties.unanswered_as_zero is False
    assert field.properties.format.model_dump(exclude_none=True) == {"style": "number"}
    assert field.validations.required in (None, False)
    assert built.summary["calculations"] == 1
    assert [i for i in built.report.items if i["kind"] == "logic"] == []  # its rule is consumed


def test_the_title_is_the_variable_name_as_plain_text_or_its_key():
    built = run(
        TWO_NUMBERS,
        [always(setter("t", {"+": [var("a"), var("b")]}), order=0)],
        [uvar("t", name="<b>Total</b> <script>alert(1)</script>due")],
    )
    assert calcs(built)[0][1].title == "Total due"
    built = run(TWO_NUMBERS, [always(setter("t", {"+": [var("a"), 1]}))], [uvar("t", name="")])
    assert calcs(built)[0][1].title == "t"


def test_variables_that_are_not_user_defined_or_have_no_key_are_ignored():
    built = run(
        TWO_NUMBERS,
        [always(setter("t", {"+": [var("a"), 1]}))],
        [
            {"key": "a", "source": "component", "data_type": "float"},
            {"key": 5, "source": "user_defined"},
            {"source": "user_defined"},
            uvar("t"),
        ],
    )
    assert [i["key"] for i in items(built, kind="variable")] == ["t"]


# ------------------------------------------- the translation vs the original


class OriginalArithmetic:
    """What the original does with the six operators (floats, a missing
    operand gives no result, a division by zero is an error that leaves the
    variable as it was): ``json_logic/__init__.py`` lines 112-125 and 305-351
    (0.16.1)."""

    def __init__(self, data):
        self.data = data

    def run(self, node):
        if not isinstance(node, dict):
            return node
        (op, args), = node.items()
        if op == "var":
            name = args[0] if isinstance(args, list) else args
            return self.data.get(name)
        args = args if isinstance(args, list) else [args]
        values = [self.run(a) for a in args]
        if any(v is None for v in values):
            return None
        if op == "+":
            return sum(values)
        if op == "-":
            return -values[0] if len(values) == 1 else values[0] - values[1]
        if op == "*":
            total = 1
            for v in values:
                total = total * float(v)
            return total
        if op == "/":
            return float(values[0]) / float(values[1])
        if op == "min":
            return min(values)
        if op == "max":
            return max(values)
        raise AssertionError(op)


def random_expression(rng, depth=0):
    if depth >= 3 or rng.random() < 0.3:
        return rng.choice([var("a"), var("b"), var("c"), rng.choice([0, 1, 2, -3, 2.5, 100])])
    op = rng.choice(["+", "-", "*", "/", "min", "max"])
    if op in ("min", "max"):
        leaf = lambda: rng.choice([var("a"), var("b"), var("c"), rng.choice([0, 7, -1.5])])  # noqa: E731
        return {op: [leaf() for _ in range(rng.randint(1, 3))]}
    count = 1 if op == "-" and rng.random() < 0.3 else 2
    if op in ("+", "*") and rng.random() < 0.3:
        count = 3
    return {op: [random_expression(rng, depth + 1) for _ in range(count)]}


def test_the_translation_agrees_with_the_originals_arithmetic():
    rng = random.Random(20261027)
    samples = [None, 0, 1, 2, -3, 2.5, 100, 0.5]
    checked = 0
    for _ in range(400):
        expression = random_expression(rng)
        tree, divides = V.parse_expression(expression)
        ast = V.to_ast(tree, {k: k for k in V.references(tree)})
        for _ in range(12):
            data = {k: rng.choice(samples) for k in "abc"}
            try:
                original = OriginalArithmetic(data).run(expression)
            except ZeroDivisionError:
                original = None  # the variable keeps its (empty) start
            ours = evaluate_expression(
                ast, {k: None if v is None else Decimal(str(v)) for k, v in data.items()}, {}
            )
            if original is None:
                assert ours is None, (expression, data)
            elif abs(original) >= 1e12:
                continue
            else:
                assert ours is not None, (expression, data, original)
                assert float(ours) == pytest.approx(original, rel=1e-12, abs=1e-12), (expression, data)
            checked += 1
    assert checked > 2000


@pytest.mark.parametrize(
    "answers, expected",
    [
        ({"A": 6, "B": 7}, 42),
        ({"A": 2.5, "B": 4}, 10),
        ({"A": 6}, None),  # an unanswered operand gives no value, as in the original
        ({}, None),
    ],
)
def test_the_imported_calculation_computes_the_originals_value(answers, expected):
    built = one({"*": [var("a"), var("b")]})
    assert value_of(built, "T", **answers) == expected


def test_unanswered_stays_unanswered_not_zero():
    built = one({"+": [var("a"), var("b")]})
    assert value_of(built, "T", A=1, B=2) == 3
    assert value_of(built, "T", A=1) is None


def test_a_division_by_zero_has_no_value_and_a_division_keeps_decimals():
    built = one({"/": [var("a"), var("b")]})
    assert value_of(built, "T", A=1, B=0) is None
    assert value_of(built, "T", A=1, B=4) == 0.25
    assert value_of(built, "T", A=1, B=3) == pytest.approx(1 / 3, rel=1e-12)


def test_min_and_max_give_nothing_when_an_answer_is_missing_as_in_the_original():
    built = one({"min": [var("a"), var("b")]})
    assert value_of(built, "T", A=4, B=3) == 3
    assert value_of(built, "T", A=0, B=3) == 0
    assert value_of(built, "T", A=4) is None
    built = one({"max": [var("a"), 10]})
    assert value_of(built, "T", A=4) == 10
    assert value_of(built, "T") is None


def test_a_negated_value_and_a_calculation_of_calculations():
    built = run(
        TWO_NUMBERS,
        [
            always(setter("net", {"-": [var("a"), var("b")]}, "n"), order=0),
            always(setter("gross", {"*": [var("net"), 1.21]}, "g"), order=1),
            always(setter("neg", {"-": [var("gross")]}, "x"), order=2),
        ],
        [uvar("net", name="Net"), uvar("gross", name="Gross"), uvar("neg", name="Neg")],
    )
    assert [f.title for _, f in calcs(built)] == ["Net", "Gross", "Neg"]
    assert value_of(built, "Net", A=10, B=4) == 6
    assert value_of(built, "Gross", A=10, B=4) == pytest.approx(7.26)
    assert value_of(built, "Neg", A=10, B=4) == pytest.approx(-7.26)
    assert value_of(built, "Gross", A=10) is None
    assert calculated_field_problems(built.form) == []
    assert built.summary["calculations"] == 3


# ------------------------------------------------------------ what qualifies


def test_a_variable_with_a_start_value_qualifies_unless_it_divides():
    built = one({"*": [var("a"), var("b")]}, variables_extra={"initial_value": 0.0})
    assert len(calcs(built)) == 1
    built = one({"/": [var("a"), var("b")]}, variables_extra={"initial_value": 0.0})
    assert calcs(built) == []
    assert not_carried(built, "t") == {"dataType": "float", "cause": "initial_value"}
    built = one({"/": [var("a"), var("b")]}, variables_extra={"initial_value": None})
    assert len(calcs(built)) == 1


def test_an_integer_variable_qualifies_a_text_or_list_or_date_variable_does_not():
    assert len(calcs(one({"+": [var("a"), 1]}, variables_extra={"data_type": "int"}))) == 1
    for data_type in ("string", "boolean", "date", "datetime", "array", "object", "", "time"):
        built = one({"+": [var("a"), 1]}, variables_extra={"data_type": data_type})
        assert not_carried(built, "t")["cause"] == "not_numeric", data_type


def test_two_actions_that_set_one_variable_carry_neither():
    built = run(
        TWO_NUMBERS,
        [
            always(setter("t", {"+": [var("a"), 1]}, "1"), order=0),
            always(setter("t", {"+": [var("b"), 1]}, "2"), order=1),
        ],
        [uvar("t")],
    )
    assert calcs(built) == []
    assert not_carried(built, "t") == {"dataType": "float", "cause": "several_rules", "rules": 2}
    # the rules are reported as they always were
    assert len(items(built, kind="logic", reason="trigger_not_supported")) == 2


def test_two_actions_in_one_rule_that_set_one_variable_carry_neither():
    built = run(
        TWO_NUMBERS,
        [always(setter("t", 1, "1"), setter("t", {"+": [var("a"), 1]}, "2"))],
        [uvar("t")],
    )
    assert not_carried(built, "t")["cause"] == "several_rules"


@pytest.mark.parametrize(
    "other",
    [
        {"uuid": "o", "variable": "t", "action": {"type": "fetch-from-service", "value": "1"}},
        {
            "uuid": "o",
            "action": {
                "type": "synchronize-variables",
                "config": {"destination_variable": "t", "source_variable": "x", "identifier_variable": "i", "data_mappings": []},
            },
        },
        {
            "uuid": "o",
            "action": {
                "type": "evaluate-dmn",
                "config": {"output_mapping": [{"form_variable": "t", "dmn_variable": "x"}]},
            },
        },
    ],
)
def test_another_way_to_write_the_variable_keeps_it_out(other):
    built = run(
        TWO_NUMBERS,
        [always(setter("t", {"+": [var("a"), 1]})), rule(eq_a(), other, order=1)],
        [uvar("t")],
    )
    assert not_carried(built, "t")["cause"] == "other_source"


def eq_a():
    return {"==": [var("a"), 1]}


@pytest.mark.parametrize(
    "extra", [{"prefill_plugin": "demo"}, {"prefill_attribute": "x"}, {"service_fetch_configuration": {"id": 1}}]
)
def test_a_variable_with_a_prefill_or_a_service_fetch_stays_out(extra):
    built = one({"+": [var("a"), 1]}, variables_extra=extra)
    assert not_carried(built, "t")["cause"] == "other_source"


def test_a_variable_no_rule_sets_is_reported_with_its_cause():
    built = run(TWO_NUMBERS, [], [uvar("t")])
    assert not_carried(built, "t") == {"dataType": "float", "cause": "no_rule"}


def test_a_conditional_rule_keeps_the_variable_out_and_is_reported_as_before():
    for trigger in (eq_a(), {"!!": [var("a")]}, {"and": [True, True]}, 1, "true", {"var": "a"}):
        built = run(
            TWO_NUMBERS,
            [{**rule(trigger, setter("t", {"+": [var("a"), 1]})), "is_advanced": True}],
            [uvar("t")],
        )
        assert calcs(built) == [], trigger
        assert not_carried(built, "t")["cause"] == "condition"
    built = run(
        TWO_NUMBERS,
        [rule(eq_a(), setter("t", {"+": [var("a"), 1]}))],
        [uvar("t")],
    )
    assert [i["detail"]["actionType"] for i in items(built, reason="action_not_supported")] == ["variable"]


def test_a_rule_with_another_action_beside_the_calculation_is_still_reported():
    built = run(
        [[num("a", label="A"), comp("textfield", "x", label="X")]],
        [
            always(
                setter("t", {"+": [var("a"), 1]}),
                {"component": "x", "action": {"type": "property", "property": {"value": "hidden", "type": "bool"}, "state": True}},
            )
        ],
        [uvar("t")],
    )
    assert len(calcs(built)) == 1
    # the hide action sits in a rule the visibility logic cannot read: reported as it was
    assert len(items(built, kind="logic", reason="trigger_not_supported")) == 1


# --------------------------------------------------- operators we refuse


@pytest.mark.parametrize(
    "expression, cause, operator",
    [
        ({"reduce": [var("a"), {"+": [var("accumulator"), var("current")]}, 0]}, "operator", "reduce"),
        ({"map": [var("a"), {"+": [var(""), 1]}]}, "operator", "map"),
        ({"cat": [var("a"), "x"]}, "operator", "cat"),
        ({"date": [var("a")]}, "operator", "date"),
        ({"datetime": [var("a")]}, "operator", "datetime"),
        ({"today": []}, "operator", "today"),
        ({"rdelta": [1]}, "operator", "rdelta"),
        ({"%": [var("a"), 2]}, "operator", "%"),
        ({"if": [True, 1, 2]}, "operator", "if"),
        ({"?:": [True, 1, 2]}, "operator", "?:"),
        ({"<": [var("a"), 2]}, "operator", "<"),
        ({"==": [var("a"), 2]}, "operator", "=="),
        ({"and": [var("a"), var("b")]}, "operator", "and"),
        ({"!": [var("a")]}, "operator", "!"),
        ({"!!": [var("a")]}, "operator", "!!"),
        ({"in": [1, [1]]}, "operator", "in"),
        ({"merge": [[1], [2]]}, "operator", "merge"),
        ({"substr": [var("a"), 1]}, "operator", "substr"),
        ({"count": [var("a")]}, "operator", "count"),
        ({"missing": ["a"]}, "operator", "missing"),
        ({"log": [var("a")]}, "operator", "log"),
        ({"__import__('os').system('x')": [1]}, "operator", None),
        ({"+": [{"cat": ["a", "b"]}, 1]}, "operator", "cat"),
        # shapes
        ({"+": [var("a")]}, "operand", None),  # one argument: not the same on both sides
        ({"*": [var("a")]}, "operand", None),
        ({"-": [var("a"), var("b"), 1]}, "operand", None),  # the original ignores the third
        ({"/": [var("a")]}, "operand", None),  # the original returns it untouched
        ({"/": [var("a"), 1, 2]}, "operand", None),
        ({"min": []}, "operand", None),
        ({"min": [{"+": [var("a"), 1]}, 3]}, "operand", None),  # a calculation inside min
        ({"max": [{"min": [var("a"), 1]}, 3]}, "operand", None),
        ({"+": [var("a"), "5"]}, "operand", None),  # a text
        ({"+": [var("a"), True]}, "operand", None),
        ({"+": [var("a"), None]}, "operand", None),
        ({"+": [var("a"), [1]]}, "operand", None),
        ({"+": [var("a"), {}]}, "operand", None),
        ({"+": [var("a"), {"var": "a", "x": 1}]}, "operand", None),
        ({"+": [var("a"), {"var": ["a", 0]}]}, "operand", None),  # a default value
        ({"+": [var("a"), {"var": ""}]}, "operand", None),
        ({"+": [var("a"), {"var": 5}]}, "operand", None),
        ({"+": [var("a"), {"var": "x" * 201}]}, "operand", None),
        ({"+": [var("a"), 1e15]}, "operand", None),  # beyond what expressions hold
        ({"+": [var("a"), 123456789.123456789]}, "operand", None),  # more than 15 digits
        ({"+": [var("a"), 10**20]}, "operand", None),
        ({"+": [var("a"), 1e-20]}, "operand", None),
        ("5", "operand", None),
        (None, "operand", None),
        (True, "operand", None),
        ([1, 2], "operand", None),
    ],
)
def test_an_expression_outside_the_subset_stays_reported(expression, cause, operator):
    built = one(expression)
    assert calcs(built) == []
    detail = not_carried(built, "t")
    assert detail["cause"] == cause
    if operator is not None:
        assert detail["operator"] == operator
    assert len(detail["cause"]) < 40
    # and the rule is reported exactly as it was before this feature
    assert len(items(built, kind="logic", reason="trigger_not_supported")) == 1


def test_a_hostile_operator_name_is_cut_and_never_run(exec_guard):
    name = "__import__('os').system('boom')" + "x" * 500
    built = one({name: [1]})
    detail = not_carried(built, "t")
    assert detail["cause"] == "operator" and len(detail["operator"]) <= 40
    assert exec_guard == []


def test_the_import_runs_nothing(exec_guard):
    built = run(
        TWO_NUMBERS,
        [
            always(setter("t", {"*": [var("a"), {"+": [var("b"), 1]}]}, "1"), order=0),
            always(setter("u", {"cat": ["__import__('os')", var("a")]}, "2"), order=1),
            always(setter("w", {"reduce": [var("a"), {"+": [var("accumulator"), 1]}, 0]}, "3"), order=2),
        ],
        [uvar("t"), uvar("u"), uvar("w")],
    )
    assert len(calcs(built)) == 1
    assert exec_guard == []


# ---------------------------------------------------------------- limits


def nested(depth, leaf=None):
    node = leaf if leaf is not None else var("a")
    for _ in range(depth - 1):
        node = {"+": [node, 1]}
    return node


def test_the_depth_limit():
    ok = nested(V.MAX_DEPTH - 1)  # the root is level 1, the variable the last
    assert len(calcs(one(ok))) == 1
    built = one(nested(V.MAX_DEPTH + 2))
    assert not_carried(built, "t")["cause"] == "too_complex"


def test_the_node_limit():
    # 1 + 19 * 3 + 1 = 59 nodes
    at_limit = {"+": [{"+": [1, 1]} for _ in range(19)] + [1]}
    assert V.parse_expression(at_limit)[0][0] == "+"
    # a list of numbers: every one is a node, at most 20 arguments
    assert len(calcs(one({"+": [1] * V.MAX_ARGS}))) == 1
    assert not_carried(one({"+": [1] * (V.MAX_ARGS + 1)}), "t")["cause"] == "operand"
    # 1 + 20 * 3 = 61 nodes
    over = {"+": [{"+": [1, 1]} for _ in range(20)]}
    with pytest.raises(V.NotCarried) as caught:
        V.parse_expression(over)
    assert caught.value.cause == "too_complex"
    assert not_carried(one(over), "t")["cause"] == "too_complex"
    wide = {"+": [{"+": [1] * V.MAX_ARGS} for _ in range(V.MAX_ARGS)]}  # 421 nodes
    assert not_carried(one(wide), "t")["cause"] == "too_complex"


def test_too_many_arguments_are_refused_before_any_is_read():
    # inside an archive (its own size limits allow a thousand)
    assert not_carried(one({"+": [var("a")] * 1000}), "t")["cause"] == "operand"
    # and straight to the translator, far beyond what an archive may hold
    started = time.perf_counter()
    with pytest.raises(V.NotCarried) as caught:
        V.parse_expression({"+": [var("a")] * 200_000})
    assert caught.value.cause == "operand"
    assert time.perf_counter() - started < CATASTROPHIC_SECONDS


def test_a_hostile_deep_expression_is_cut_without_recursing_into_it():
    deep = var("a")
    for _ in range(100_000):
        deep = {"-": [deep]}
    with pytest.raises(V.NotCarried) as caught:
        V.parse_expression(deep)
    assert caught.value.cause == "too_complex"


def test_a_hostile_deep_expression_in_an_archive_does_not_break_the_import():
    # 28 levels (two JSON levels each): within the archive's own depth limit
    built = one(nested(28))
    assert not_carried(built, "t")["cause"] == "too_complex"
    # deeper than the archive allows: refused as an archive, as it always was
    with pytest.raises(ImportRefused):
        one(nested(limits.MAX_JSON_DEPTH + 10))


def test_what_an_expression_costs_counts_against_the_import_budget(monkeypatch):
    monkeypatch.setattr(limits, "MAX_TEXT_CHARS", 10)
    expression = {"+": [{"*": [var("a"), var("b")]} for _ in range(5)]}
    with budget.scope():
        with pytest.raises(ImportRefused) as caught:
            V.parse_expression(expression)
    assert caught.value.code == "archive_too_complex"
    monkeypatch.setattr(limits, "MAX_TEXT_CHARS", 10_000)
    with budget.scope():
        V.parse_expression(expression)


def test_many_variables_are_bounded_in_time_and_in_number(no_deadline):
    count = 400
    rules = [always(setter(f"v{i}", {"+": [var("a"), {"*": [var("b"), i]}]}, str(i)), order=i) for i in range(count)]
    variables = [uvar(f"v{i}", name=f"V{i}") for i in range(count)]
    started = time.perf_counter()
    built = run(TWO_NUMBERS, rules, variables)
    assert time.perf_counter() - started < CATASTROPHIC_SECONDS
    assert len(calcs(built)) == V.MAX_CALCULATIONS == 50
    assert built.summary["calculations"] == 50
    assert calculated_field_problems(built.form) == []
    # the report is capped (500 items), so only some of the rest is in it
    assert built.report.truncated
    over = [i for i in items(built, kind="variable") if i["reason"] == "user_variable_not_carried"]
    assert over and {i["detail"]["cause"] for i in over} == {"too_many"}
    # the first fifty in the file's order are the ones kept
    assert [f.title for _, f in calcs(built)] == [f"V{i}" for i in range(50)]


def test_hostile_chains_and_circles_of_variables_are_resolved_in_linear_time(no_deadline):
    count = 450
    # each reads the next one, which a later rule sets: every one is out of order
    reverse = [always(setter(f"v{i}", {"+": [var(f"v{i + 1}"), 1]}, str(i)), order=i) for i in range(count - 1)]
    reverse.append(always(setter(f"v{count - 1}", {"+": [var("a"), 1]}, "x"), order=count - 1))
    started = time.perf_counter()
    built = run(TWO_NUMBERS, reverse, [uvar(f"v{i}") for i in range(count)])
    assert time.perf_counter() - started < CATASTROPHIC_SECONDS
    assert [f.title for _, f in calcs(built)] == [f"V{count - 1}"]
    # all of them in one circle, each reading twenty others
    dense = [
        always(setter(f"v{i}", {"+": [var(f"v{(i + j) % count}") for j in range(1, 20)]}, str(i)), order=i)
        for i in range(count)
    ]
    started = time.perf_counter()
    built = run(TWO_NUMBERS, dense, [uvar(f"v{i}") for i in range(count)])
    assert time.perf_counter() - started < CATASTROPHIC_SECONDS
    assert calcs(built) == []
    assert {i["detail"]["cause"] for i in items(built, kind="variable")} == {"cycle"}


def test_calculations_count_against_the_thousand_question_cap(no_deadline):
    fields = [comp("textfield", f"t{i}") for i in range(limits.MAX_IMPORT_FIELDS - 5 - 1)]
    steps = [[num("a", label="A")] + fields]
    rules = [always(setter(f"v{i}", {"+": [var("a"), i]}, str(i)), order=i) for i in range(10)]
    built = run(steps, rules, [uvar(f"v{i}") for i in range(10)])
    assert len(calcs(built)) == 5
    causes = [i["detail"].get("cause") for i in items(built, kind="variable") if i["reason"] == "user_variable_not_carried"]
    assert causes == ["too_many"] * 5
    total = sum(len(page.properties.fields) for page in built.form.fields)
    assert total == limits.MAX_IMPORT_FIELDS


# -------------------------------------------------- the sources it reads


def test_a_reference_to_a_component_we_did_not_import_stays_out():
    steps = [[
        num("a", label="A"),
        {**num("hiddenNumber", label="H"), "hidden": True},
        comp("signature", "sig"),
    ]]
    for key in ("hiddenNumber", "sig", "nowhere", "now", "auth_bsn"):
        built = run(steps, [always(setter("t", {"+": [var("a"), var(key)]}))], [uvar("t")])
        assert calcs(built) == [], key
        assert not_carried(built, "t") == {"dataType": "float", "cause": "source_missing", "source": key}


def test_a_reference_to_a_question_that_is_not_a_number_stays_out():
    steps = [[num("a", label="A"), comp("textfield", "x", label="X"), comp("checkbox", "c", label="C")]]
    for key in ("x", "c"):
        built = run(steps, [always(setter("t", {"+": [var("a"), var(key)]}))], [uvar("t")])
        assert not_carried(built, "t")["cause"] == "source_not_number"


def test_a_reference_into_a_repeating_group_or_to_a_list_stays_out():
    steps = [[
        num("a", label="A"),
        comp("editgrid", "grid", label="Grid", components=[num("inner", label="Inner")]),
        num("many", label="Many", multiple=True),
    ]]
    cases = {"inner": "source_in_group", "grid": "source_not_number", "many": "source_multiple"}
    for key, cause in cases.items():
        built = run(steps, [always(setter("t", {"+": [var("a"), var(key)]}))], [uvar("t")])
        assert not_carried(built, "t")["cause"] == cause, key


def test_a_currency_component_counts_as_a_number():
    steps = [[comp("currency", "price", label="Price"), num("qty", label="Qty")]]
    built = run(steps, [always(setter("t", {"*": [var("price"), var("qty")]}))], [uvar("t", name="T")])
    assert len(calcs(built)) == 1
    assert value_of(built, "T", Price=2.5, Qty=4) == 10


def test_a_variable_with_the_key_of_a_component_stays_out():
    built = run(TWO_NUMBERS, [always(setter("a", {"+": [var("b"), 1]}))], [uvar("a")])
    assert not_carried(built, "a")["cause"] == "key_collision"


def test_a_source_that_was_not_imported_as_a_question_is_named_in_the_cause():
    infos = V.analyse([uvar("t")], [always(setter("t", {"+": [var("a"), 1]}))], False)
    assert V.resolve(infos, {}, {"a": "source_missing"}, {"a"}) == []
    assert infos["t"].cause == "source_missing" and infos["t"].detail == {"source": "a"}


def test_a_source_that_a_rule_writes_stays_out():
    """Rule 1 sets the component ``a`` from ``b``; rule 2 reads ``a``: the
    original reads the rule's value, we would read the answer."""
    rules = [
        always(setter("a", {"*": [var("b"), 2]}, "1"), order=0),
        always(setter("t", {"+": [var("a"), 1]}, "2"), order=1),
    ]
    built = run(TWO_NUMBERS, rules, [uvar("t")])
    assert calcs(built) == []
    assert not_carried(built, "t") == {"dataType": "float", "cause": "source_rewritten", "source": "a"}


@pytest.mark.parametrize(
    "writer",
    [
        {"uuid": "o", "variable": "a", "action": {"type": "fetch-from-service", "value": "1"}},
        {
            "uuid": "o",
            "action": {
                "type": "synchronize-variables",
                "config": {"destination_variable": "a", "source_variable": "x", "identifier_variable": "i", "data_mappings": []},
            },
        },
        {
            "uuid": "o",
            "action": {"type": "evaluate-dmn", "config": {"output_mapping": [{"form_variable": "a", "dmn_variable": "x"}]}},
        },
    ],
)
def test_a_source_another_action_writes_stays_out(writer):
    built = run(TWO_NUMBERS, [always(setter("t", {"+": [var("a"), 1]})), rule(eq_a(), writer, order=1)], [uvar("t")])
    assert not_carried(built, "t")["cause"] == "source_rewritten"


@pytest.mark.parametrize(
    "extra",
    [
        {"prefill": {"plugin": "demo", "attribute": "x"}},
        {"calculateValue": "value = 1"},
        {"customDefaultValue": "value = 1"},
        {"logic": [{"name": "x", "trigger": {"type": "simple"}, "actions": []}]},
    ],
)
def test_a_source_with_a_prefill_or_a_script_stays_out(extra):
    steps = [[num("a", label="A", **extra), num("b", label="B")]]
    built = run(steps, [always(setter("t", {"+": [var("a"), var("b")]}))], [uvar("t")])
    assert not_carried(built, "t") == {"dataType": "float", "cause": "source_rewritten", "source": "a"}
    # reading only the other one is fine
    built = run(steps, [always(setter("t", {"+": [var("b"), 1]}))], [uvar("t")])
    assert len(calcs(built)) == 1


@pytest.mark.parametrize("default", [5, 0, 2.5, "7", "0"])
def test_a_source_that_starts_from_a_default_stays_out(default):
    steps = [[num("a", label="A", defaultValue=default), num("b", label="B")]]
    built = run(steps, [always(setter("t", {"+": [var("a"), var("b")]}))], [uvar("t")])
    assert not_carried(built, "t") == {"dataType": "float", "cause": "source_default", "source": "a"}


@pytest.mark.parametrize("default", [None, ""])
def test_a_source_with_no_default_is_fine(default):
    steps = [[num("a", label="A", defaultValue=default), num("b", label="B")]]
    built = run(steps, [always(setter("t", {"+": [var("a"), var("b")]}))], [uvar("t")])
    assert len(calcs(built)) == 1


def test_a_bare_copy_of_an_answer_needs_an_empty_start_the_rest_assign_empty():
    # a hidden question is gone from the original's data: a bare ``var`` of it
    # assigns nothing (the variable keeps what it held), arithmetic assigns empty
    built = one({"var": "a"}, variables_extra={"initial_value": 0.0})
    assert not_carried(built, "t") == {"dataType": "float", "cause": "initial_value"}
    built = one({"var": ["a"]}, variables_extra={"initial_value": 5})
    assert not_carried(built, "t")["cause"] == "initial_value"
    for expression in ({"+": [var("a"), 1]}, {"-": [var("a")]}, {"min": [var("a"), 3]}, {"*": [var("a"), var("b")]}):
        assert len(calcs(one(expression, variables_extra={"initial_value": 0.0}))) == 1, expression


def test_an_integer_variable_keeps_a_fraction_as_the_original_stores_it():
    # their int variable is not truncated on assignment: the value is stored as
    # computed (submission_value_variable.py:597-605, 694-702)
    built = one({"/": [var("a"), var("b")]}, variables_extra={"data_type": "int"})
    assert len(calcs(built)) == 1
    assert value_of(built, "T", A=1, B=4) == 0.25
    assert len(calcs(one({"*": [var("a"), 0.5]}, variables_extra={"data_type": "int"}))) == 1


def choice_and_a(**extra):
    return [[comp("textfield", "choice", label="Choice"), num("a", label="A", **extra), num("b", label="B")]]


COND = {"conditional": {"show": False, "when": "choice", "eq": "no"}}


def test_a_source_a_rule_can_hide_stays_out_the_owners_repro():
    """``a`` is hidden when choice is no. There it is cleared, so ``a + 1`` has
    no value; here the answer is still read."""
    steps = choice_and_a()
    rules = [rule(eq("choice", "no"), hide("a"), order=0), always(setter("t", {"+": [var("a"), 1]}), order=1)]
    built = run(steps, rules, [uvar("t")])
    assert calcs(built) == []
    assert not_carried(built, "t") == {"dataType": "float", "cause": "source_conditional", "source": "a"}


def test_a_bare_copy_of_a_source_a_rule_can_hide_stays_out_too():
    rules = [rule(eq("choice", "no"), hide("a"), order=0), always(setter("t", var("a")), order=1)]
    built = run(choice_and_a(), rules, [uvar("t")])
    assert not_carried(built, "t")["cause"] == "source_conditional"


def test_a_rule_that_shows_the_source_counts_and_so_does_one_we_cannot_read():
    # showing a question that starts hidden, hiding on a trigger we cannot
    # translate: either way the original may clear the answer
    for target, trigger in (
        (hide("a", False), eq("choice", "no")),
        (hide("a"), {"cat": [var("choice"), "x"]}),
    ):
        rules = [rule(trigger, target, order=0), always(setter("t", {"+": [var("a"), 1]}), order=1)]
        built = run(choice_and_a(), rules, [uvar("t")])
        assert not_carried(built, "t")["cause"] == "source_conditional", target


def test_a_source_with_its_own_show_or_hide_condition_stays_out():
    for cond in (
        {"conditional": {"show": False, "when": "choice", "eq": "no"}},
        {"conditional": {"show": True, "when": "choice", "eq": "yes"}},
        {"conditional": {"show": True, "when": "choice"}},  # incomplete: refused anyway
    ):
        built = run(choice_and_a(**cond), [always(setter("t", {"+": [var("a"), 1]}))], [uvar("t")])
        assert not_carried(built, "t") == {"dataType": "float", "cause": "source_conditional", "source": "a"}, cond
    # the other source is not touched by it
    built = run(choice_and_a(**COND), [always(setter("t", {"+": [var("b"), 1]}))], [uvar("t")])
    assert len(calcs(built)) == 1


@pytest.mark.parametrize(
    "extra",
    [
        {},
        {"conditional": None},
        {"conditional": {}},
        {"conditional": {"show": True}},
        {"conditional": {"show": True, "when": "", "eq": ""}},
        {"conditional": {"show": True, "when": None, "eq": "x"}},
    ],
)
def test_a_source_with_no_condition_is_fine(extra):
    built = run(choice_and_a(**extra), [always(setter("t", {"+": [var("a"), 1]}))], [uvar("t")])
    assert len(calcs(built)) == 1


def test_a_rule_that_changes_another_property_does_not_count():
    other = {
        "component": "a",
        "action": {"type": "property", "property": {"value": "validate.required", "type": "bool"}, "state": True},
    }
    rules = [rule(eq("choice", "no"), other, order=0), always(setter("t", {"+": [var("a"), 1]}), order=1)]
    built = run(choice_and_a(), rules, [uvar("t")])
    assert len(calcs(built)) == 1


@pytest.mark.parametrize(
    "layout",
    [
        lambda inner: comp("fieldset", "fs", components=inner, **COND),
        lambda inner: comp("fieldset", "fs", components=[comp("fieldset", "inner", components=inner, **COND)]),
        lambda inner: comp("columns", "cols", columns=[{"size": 6, "components": inner}], **COND),
        lambda inner: comp("fieldset", "fs", components=[comp("columns", "cols", columns=[{"size": 6, "components": inner}], **COND)]),
    ],
)
def test_a_source_inside_a_layout_component_that_can_be_hidden_stays_out(layout):
    steps = [[comp("textfield", "choice", label="Choice"), layout([num("a", label="A")]), num("b", label="B")]]
    built = run(steps, [always(setter("t", {"+": [var("a"), 1]}))], [uvar("t")])
    assert not_carried(built, "t") == {"dataType": "float", "cause": "source_conditional", "source": "a"}


def test_a_source_inside_a_fieldset_a_rule_hides_stays_out_and_a_plain_one_is_fine():
    def steps(**extra):
        return [[comp("textfield", "choice"), comp("fieldset", "fs", components=[num("a", label="A")], **extra)]]

    rules = [rule(eq("choice", "no"), hide("fs"), order=0), always(setter("t", {"+": [var("a"), 1]}), order=1)]
    assert not_carried(run(steps(), rules, [uvar("t")]), "t")["cause"] == "source_conditional"
    built = run(steps(), [always(setter("t", {"+": [var("a"), 1]}))], [uvar("t")])
    assert len(calcs(built)) == 1


def test_a_source_on_a_step_a_rule_can_make_not_applicable_stays_out():
    step_uuid = "10000000-0000-4000-8000-000000000001"
    skip = {"uuid": "s", "form_step_uuid": step_uuid, "action": {"type": "step-not-applicable"}}
    steps = [[comp("textfield", "choice", label="Choice"), num("b", label="B")], [num("a", label="A")]]
    rules = [rule(eq("choice", "no"), skip, order=0)]
    built = run(steps, rules + [always(setter("t", {"+": [var("a"), 1]}), order=1)], [uvar("t")])
    assert not_carried(built, "t") == {"dataType": "float", "cause": "source_conditional", "source": "a"}
    # a source on the other step is untouched
    built = run(steps, rules + [always(setter("t", {"+": [var("b"), 1]}), order=1)], [uvar("t")])
    assert len(calcs(built)) == 1
    # a target we cannot name puts every step in doubt
    anonymous = {"uuid": "s", "action": {"type": "step-applicable"}}
    built = run(steps, [rule(eq("choice", "no"), anonymous, order=0), always(setter("t", {"+": [var("b"), 1]}), order=1)], [uvar("t")])
    assert not_carried(built, "t")["cause"] == "source_conditional"


def test_a_variable_that_reads_a_variable_with_a_conditional_source_stays_out():
    rules = [
        rule(eq("choice", "no"), hide("a"), order=0),
        always(setter("t", {"+": [var("a"), 1]}, "1"), order=1),
        always(setter("u", {"*": [var("t"), 2]}, "2"), order=2),
    ]
    built = run(choice_and_a(), rules, [uvar("t"), uvar("u")])
    assert calcs(built) == []
    assert not_carried(built, "t")["cause"] == "source_conditional"
    assert not_carried(built, "u") == {"dataType": "float", "cause": "depends_on_variable", "source": "t"}


# ------------------------------------------- an output mapping past its cap


def dmn(*form_variables, filler=0):
    mappings = [{"form_variable": f"filler{i}", "dmn_variable": "x"} for i in range(filler)]
    mappings += [{"form_variable": name, "dmn_variable": "x"} for name in form_variables]
    return {"uuid": "o", "action": {"type": "evaluate-dmn", "config": {"output_mapping": mappings}}}


def test_a_decision_that_names_a_variable_inside_the_cap_is_seen():
    built = run(TWO_NUMBERS, [always(setter("t", {"+": [var("a"), 1]})), rule(eq_a(), dmn("t", filler=V.MAX_MAPPINGS - 1), order=1)], [uvar("t")])
    assert not_carried(built, "t")["cause"] == "other_source"


def test_a_decision_with_more_mappings_than_we_read_writes_every_variable():
    action = dmn("t", filler=V.MAX_MAPPINGS)  # "t" is entry 201: never read
    built = run(TWO_NUMBERS, [always(setter("t", {"+": [var("a"), 1]})), rule(eq_a(), action, order=1)], [uvar("t")])
    assert calcs(built) == []
    assert not_carried(built, "t")["cause"] == "other_source"
    # even a variable it does not name
    built = run(TWO_NUMBERS, [always(setter("t", {"+": [var("a"), 1]})), rule(eq_a(), dmn(filler=V.MAX_MAPPINGS + 1), order=1)], [uvar("t")])
    assert not_carried(built, "t")["cause"] == "other_source"


def test_a_decision_with_more_mappings_than_we_read_may_write_a_source():
    action = dmn("a", filler=V.MAX_MAPPINGS)  # "a" is entry 201: never read
    rules = [always(setter("t", {"+": [var("a"), var("b")]})), rule(eq_a(), action, order=1)]
    built = run(TWO_NUMBERS, rules, [uvar("t")])
    assert calcs(built) == []
    # the action may write the variable too, which is named first
    assert not_carried(built, "t")["cause"] == "other_source"
    # and, were the variable not in doubt itself, the source is
    infos = V.analyse([uvar("t")], [always(setter("t", {"+": [var("a"), 1]}))], False)
    written = V.written_keys([], [rule(eq_a(), action)])
    assert V.resolve(infos, {"a": V.Source("id-a", (0, 1))}, {}, {"a"}, written) == []
    assert infos["t"].cause == "source_rewritten" and infos["t"].detail == {"source": "a"}


def test_written_keys_marks_an_over_long_mapping_as_writing_everything():
    rules = [rule(True, dmn(filler=V.MAX_MAPPINGS + 1))]
    assert V.WRITES_ANY in V.written_keys([], rules)
    assert V.WRITES_ANY not in V.written_keys([], [rule(True, dmn(filler=V.MAX_MAPPINGS))])


# ----------------------------------------------- chains, cycles and order


def test_a_cycle_keeps_every_variable_in_it_out():
    built = run(
        TWO_NUMBERS,
        [
            always(setter("p", {"+": [var("q"), 1]}, "1"), order=0),
            always(setter("q", {"+": [var("p"), 1]}, "2"), order=1),
            always(setter("r", {"+": [var("r"), 1]}, "3"), order=2),
            always(setter("s", {"+": [var("p"), var("a")]}, "4"), order=3),
        ],
        [uvar("p"), uvar("q"), uvar("r"), uvar("s")],
    )
    assert calcs(built) == []
    assert {k: not_carried(built, k)["cause"] for k in "pqrs"} == {
        "p": "cycle", "q": "cycle", "r": "cycle", "s": "cycle",
    }


def test_a_variable_that_reads_one_that_is_not_carried_stays_out():
    built = run(
        TWO_NUMBERS,
        [
            always(setter("p", {"cat": ["x"]}, "1"), order=0),
            always(setter("q", {"+": [var("p"), 1]}, "2"), order=1),
            always(setter("u", {"+": [var("never"), 1]}, "3"), order=2),
        ],
        [uvar("p"), uvar("q"), uvar("never", data_type="string"), uvar("u")],
    )
    assert calcs(built) == []
    assert not_carried(built, "q") == {"dataType": "float", "cause": "depends_on_variable", "source": "p"}
    assert not_carried(built, "u")["cause"] == "depends_on_variable"


def test_a_variable_that_reads_one_a_later_rule_sets_stays_out():
    built = run(
        TWO_NUMBERS,
        [
            always(setter("q", {"+": [var("p"), 1]}, "2"), order=0),
            always(setter("p", {"+": [var("a"), 1]}, "1"), order=1),
        ],
        [uvar("p"), uvar("q")],
    )
    assert [f.title for _, f in calcs(built)] == ["P"]
    assert not_carried(built, "q") == {"dataType": "float", "cause": "order", "source": "p"}
    # the rule of the one kept is not reported; the other one is, as it was
    assert [i["key"] for i in items(built, kind="logic")] == ["rule-1"]


def test_a_rejected_calculation_is_reported_with_its_rule(monkeypatch):
    monkeypatch.setattr(V, "to_ast", lambda tree, ids: {"nope": []})
    built = one({"+": [var("a"), 1]})
    assert calcs(built) == []
    assert not_carried(built, "t")["cause"] == "rejected"
    assert len(items(built, kind="logic", reason="trigger_not_supported")) == 1
    assert "calculations" not in built.summary


# ---------------------------------------------------------------- placing


def test_a_calculation_goes_after_the_last_question_it_reads():
    steps = [
        [num("a", label="A"), comp("textfield", "x", label="X")],
        [num("b", label="B"), comp("textfield", "y", label="Y"), comp("textfield", "z", label="Z")],
    ]
    built = run(steps, [always(setter("t", {"+": [var("a"), var("b")]}))], [uvar("t", name="T")])
    assert titles(built) == [["A", "X"], ["B", "T", "Y", "Z"]]
    built = run(steps, [always(setter("t", {"+": [var("b"), var("a")]}))], [uvar("t", name="T")])
    assert titles(built) == [["A", "X"], ["B", "T", "Y", "Z"]]
    built = run(steps, [always(setter("t", {"*": [var("a"), 2]}))], [uvar("t", name="T")])
    assert titles(built) == [["A", "T", "X"], ["B", "Y", "Z"]]


def test_a_calculation_of_constants_goes_to_the_end_of_the_last_page():
    steps = [[num("a", label="A")], [comp("textfield", "x", label="X")]]
    built = run(steps, [always(setter("t", {"+": [1, 2]}))], [uvar("t", name="T")])
    assert titles(built) == [["A"], ["X", "T"]]
    assert value_of(built, "T") == 3


def test_calculations_after_each_other_keep_the_files_order_and_follow_what_they_read():
    steps = [[num("a", label="A"), comp("textfield", "x", label="X")]]
    rules = [
        always(setter("p", {"+": [var("a"), 1]}, "1"), order=0),
        always(setter("q", {"+": [var("a"), 2]}, "2"), order=1),
        always(setter("r", {"+": [var("p"), var("q")]}, "3"), order=2),
        always(setter("s", {"*": [var("p"), 2]}, "4"), order=3),
    ]
    built = run(steps, rules, [uvar(k, name=k.upper()) for k in "pqrs"])
    order = titles(built)[0]
    assert sorted(order) == ["A", "P", "Q", "R", "S", "X"] and order[0] == "A" and order[-1] == "X"
    # a calculation comes after the ones it reads
    assert order.index("R") > order.index("P") and order.index("R") > order.index("Q")
    assert order.index("S") > order.index("P")
    assert value_of(built, "R", A=1) == 5
    assert calculated_field_problems(built.form) == []


def test_a_calculation_in_a_chain_reads_the_other_calculation_by_its_id():
    steps = [[num("a", label="A")]]
    rules = [
        always(setter("p", {"+": [var("a"), 1]}, "1"), order=0),
        always(setter("q", {"*": [var("p"), 2]}, "2"), order=1),
    ]
    built = run(steps, rules, [uvar("p", name="P"), uvar("q", name="Q")])
    by_title = {f.title: f for _, f in calcs(built)}
    assert by_title["Q"].properties.expression == {"*": [{"var": by_title["P"].id}, 2]}
    assert titles(built) == [["A", "P", "Q"]]


# -------------------------------------------------------------- reporting


def test_a_carried_variable_is_one_changed_item_and_its_rule_is_not_reported():
    built = one({"+": [var("a"), var("b")]})
    item = carried(built, "t")
    assert item["code"] == "changed" and item["severity"] == "info"
    assert item["label"] == "T"
    assert built.report.dropped == 0
    assert items(built, kind="logic") == []


def test_what_stays_reported_is_unchanged_but_for_its_cause():
    built = run(
        TWO_NUMBERS,
        [always(setter("w", {"cat": ["x"]}))],
        [uvar("w", data_type="string", name="Words")],
    )
    (item,) = items(built, kind="variable")
    assert item["code"] == "dropped" and item["reason"] == "user_variable_not_carried"
    assert item["severity"] == "info" and item["label"] == "Words"
    assert item["detail"] == {"dataType": "string", "cause": "not_numeric"}


def test_a_report_never_carries_more_than_short_plain_text():
    key = "k" * 150
    built = run(
        TWO_NUMBERS,
        [always(setter(key, {"+": [var("a"), var("z" * 190)]}))],
        [uvar(key, name="<i>" + "n" * 400)],
    )
    (item,) = items(built, kind="variable")
    assert len(item["key"]) <= limits.MAX_KEY_IN_REPORT and len(item["label"]) <= limits.MAX_LABEL_IN_REPORT
    assert all(len(str(v)) <= 80 for v in item["detail"].values())


# ----------------------------------------------------------------- 3.x


def test_a_3x_archive_carries_the_same_variables():
    built = one({"*": [var("a"), var("b")]}, version="3.5.14")
    assert len(calcs(built)) == 1
    assert value_of(built, "T", A=3, B=5) == 15


def test_a_3x_rule_that_only_starts_from_a_step_keeps_the_variable_out():
    steps = TWO_NUMBERS
    built = run(
        steps,
        [{**always(setter("t", {"+": [var("a"), 1]})), "trigger_from_step": "http://x/steps/1"}],
        [uvar("t")],
        version="3.5.14",
    )
    assert calcs(built) == []
    assert not_carried(built, "t")["cause"] == "trigger_from_step"
    # and in a 4.0 archive that key means nothing
    built = run(
        steps,
        [{**always(setter("t", {"+": [var("a"), 1]})), "trigger_from_step": "http://x/steps/1"}],
        [uvar("t")],
    )
    assert len(calcs(built)) == 1


def test_a_duplicate_variable_key_keeps_both_out():
    built = run(TWO_NUMBERS, [always(setter("t", {"+": [var("a"), 1]}))], [uvar("t"), uvar("t")])
    assert calcs(built) == []
    assert [i["detail"]["cause"] for i in items(built, kind="variable")] == ["duplicate_key", "duplicate_key"]


# --------------------------------------------------------------- the API


@pytest.mark.asyncio
async def test_an_uploaded_archive_stores_the_calculated_question_and_reports_it(
    client, workspace, test_user_cookies, import_on
):
    from backend.app.container import container

    data = archive_with(
        TWO_NUMBERS,
        logic=[always(setter("t", {"*": [var("a"), var("b")]}))],
        variables=[uvar("t", name="Total")],
    )
    response = await client.post(
        f"/api/v1/workspaces/{workspace.id}/open-formulieren-imports",
        cookies=test_user_cookies,
        files={"file": ("export.zip", data, "application/zip")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["summary"]["calculations"] == 1
    assert [(i["code"], i["reason"], i["key"]) for i in body["report"]["items"] if i["kind"] == "variable"] == [
        ("changed", "user_variable_calculated", "t")
    ]
    document = await container.form_repo().get_form_document_by_id(body["formId"])
    stored = [f for page in document.fields for f in page.properties.fields if f.type.value == "calculated"]
    assert [f.title for f in stored] == ["Total"]
    assert stored[0].properties.hidden_from_respondents is True
    assert calculated_field_problems(document) == []
