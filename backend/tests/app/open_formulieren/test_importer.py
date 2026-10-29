"""Every fixture imports to exactly the form and report written in
``tests/fixtures/open_formulieren/golden``: the mapping of docs/open-formulieren.md,
checked question by question. Regenerate a golden file with
``OF_UPDATE_GOLDEN=1 uv run pytest tests/app/open_formulieren/test_importer.py``
and read the diff before committing it."""

import json
import os

import pytest

from backend.app.services.open_formulieren.archive import read_archive
from backend.app.services.open_formulieren.importer import build_draft
from tests.app.open_formulieren.conftest import (
    FIXTURE_NAMES,
    GOLDEN,
    describe,
    fixture_bytes,
)


def build(name: str):
    return build_draft(read_archive(fixture_bytes(name)))


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_a_fixture_imports_to_its_golden_form(name):
    actual = describe(build(name))
    path = GOLDEN / (name.removesuffix(".zip") + ".json")
    if os.environ.get("OF_UPDATE_GOLDEN"):
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n")
    assert actual == json.loads(path.read_text())


# ---------------------------------------------------------------- helpers

from backend.app.services.open_formulieren.errors import ImportRefused  # noqa: E402
from tests.app.open_formulieren.conftest import (  # noqa: E402
    archive_with,
    comp,
    eq,
    hide,
    load,
    make_zip,
    rule,
)


def run(steps, **kw):
    return build_draft(read_archive(archive_with(steps, **kw)))


def items(built, **match):
    return [
        i
        for i in built.report.items
        if all(i.get(k) == v for k, v in match.items())
    ]


def reasons(built, **match):
    return [i["reason"] for i in items(built, **match)]


def questions(built):
    return [q for page in describe(built)["pages"] for q in page["questions"]]


def refusal(steps, **kw):
    with pytest.raises(ImportRefused) as caught:
        run(steps, **kw)
    return caught.value


# --------------------------------------------------------------- the text


def test_markup_in_text_never_reaches_the_form():
    hostile = comp(
        "textfield",
        "a",
        'Name <script>alert(1)</script><b>bold</b> &amp; <img src=x onerror="alert(1)">',
        description="<p onclick='x()'>Line one</p><p>Line two</p><a href='javascript:x()'>link</a>",
        tooltip="<iframe src=//evil></iframe>",
        placeholder="<i>hint</i>",
    )
    built = run([[hostile, comp("content", "c", html="<h1>Title</h1><p>Text <b>b</b></p><style>x{}</style>")]])
    first, statement = questions(built)
    assert first["title"] == "Name bold &"
    assert first["description"] == "Line one Line two link"
    assert first["placeholder"] == "hint"
    assert statement["title"] == "Title\n\nText b"
    assert "<" not in json.dumps(describe(built)["pages"]).replace("<=", "")


def test_control_and_direction_characters_are_removed_and_length_is_capped():
    label = "Pay‮evil​\x00\x07 text" + "x" * 2000
    built = run([[comp("textfield", "a", label)]])
    title = questions(built)[0]["title"]
    assert title.startswith("Payevil text") and len(title) == 500
    assert not any(ord(c) < 32 or c in "‮​" for c in title)


def test_template_syntax_is_kept_as_literal_text():
    built = run([[comp("textfield", "a", "Hello {{ firstName }} {% if x %}")]])
    assert questions(built)[0]["title"] == "Hello {{ firstName }} {% if x %}"


def test_html_in_a_content_block_is_reported_as_simplified():
    built = run([[comp("content", "c", html="<p>Hello <b>you</b></p>"), comp("textfield", "a")]])
    assert reasons(built, key="c") == ["html_simplified"]


def test_an_empty_content_block_is_left_out_quietly():
    built = run([[comp("content", "c", html="<p> </p>"), comp("textfield", "a")]])
    assert [q["type"] for q in questions(built)] == ["short_text"]
    assert items(built, key="c") == []


# ----------------------------------------------------- national identity


def test_a_national_identity_number_is_flagged_prominently():
    built = run(
        [
            [
                comp("bsn", "id", "Identity number"),
                comp("textfield", "t", "Burgerservicenummer"),
                comp("textfield", "p", "Reference", prefill={"plugin": "x", "attribute": "bsn"}),
                comp("textfield", "o", "Order ID"),
                comp("textfield", "n", "Your name"),
            ]
        ]
    )
    flagged = {i["key"] for i in items(built, flag="national_identity_number")}
    assert flagged == {"id", "t", "p"}
    for item in items(built, flag="national_identity_number"):
        assert (item["code"], item["severity"], item["reason"]) == (
            "flagged",
            "warning",
            "national_identity_number",
        )
    assert built.summary["flagged"] == 3
    # imported as plain text, not as anything special
    assert [q["type"] for q in questions(built)] == ["short_text"] * 5
    assert questions(built)[0]["validations"]["regex"] == "^[0-9]{9}$"


# ----------------------------------------------------------------- choices


def test_choices_are_read_from_the_labels_and_made_distinct():
    built = run(
        [
            [
                comp("radio", "r", values=[{"value": "a", "label": "Same"}, {"value": "b", "label": "Same"}, {"value": "c", "label": ""}, {"value": 7, "label": "Seven"}]),
            ]
        ]
    )
    assert questions(built)[0]["choices"] == ["Same", "Same (2)", "c", "Seven"]


def test_choices_from_a_variable_or_a_list_are_dropped():
    built = run(
        [
            [
                comp("select", "s", data={"values": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]}, openForms={"dataSrc": "variable"}),
                comp("radio", "r", values=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}], openForms={"dataSrc": "referenceLists"}),
                comp("textfield", "keep"),
            ]
        ]
    )
    assert [q["title"] for q in questions(built)] == ["keep"]
    assert reasons(built, code="dropped", kind="component") == [
        "choices_from_variable",
        "choices_from_variable",
    ]


def test_a_choice_question_needs_two_options():
    built = run([[comp("radio", "r", values=[{"value": "a", "label": "A"}]), comp("textfield", "keep")]])
    assert reasons(built, key="r") == ["too_few_choices"]
    assert [q["title"] for q in questions(built)] == ["keep"]


def test_a_multiple_select_allows_several_answers_and_boxes_keep_their_limits():
    options = [{"value": c, "label": c.upper()} for c in "abc"]
    built = run(
        [
            [
                comp("select", "s", data={"values": options}, multiple=True),
                comp("selectboxes", "b", values=options, validate={"minSelectedCount": 1, "maxSelectedCount": 9}),
            ]
        ]
    )
    select, boxes = questions(built)
    assert (select["type"], select["allowMultiple"]) == ("multiple_choice", True)
    assert boxes["validations"] == {"required": False, "min_choices": 1}


def test_a_default_answer_is_not_carried():
    built = run([[comp("radio", "r", defaultValue="a", values=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}]), comp("selectboxes", "b", defaultValue={"a": False}, values=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}])]])
    assert reasons(built, reason="default_value_not_carried") == ["default_value_not_carried"]
    assert items(built, key="b", reason="default_value_not_carried") == []


# -------------------------------------------------------------- validation


def test_answer_rules_are_carried_where_our_questions_have_them():
    built = run(
        [
            [
                comp("textfield", "t", validate={"required": True, "maxLength": 20, "pattern": "^[a-z]+$"}),
                comp("textarea", "ta", validate={"maxLength": 300, "pattern": "^x$"}),
                comp("email", "e", validate={"maxLength": 80}),
                comp("number", "n", validate={"min": "2", "max": 9.5}),
                comp("number", "neg", allowNegative=False),
                comp("number", "bad", validate={"min": 9, "max": 2}),
            ]
        ]
    )
    t, ta, e, n, neg, bad = questions(built)
    assert t["validations"] == {"required": True, "max_length": 20, "regex": "^[a-z]+$"}
    assert ta["validations"] == {"required": False, "max_length": 300}
    assert e["validations"] == {"required": False}
    assert n["validations"] == {"required": False, "min_value": 2.0, "max_value": 9.5}
    assert neg["validations"]["min_value"] == 0.0
    assert "min_value" not in bad["validations"]
    props = {(i["key"], i["detail"]["property"]) for i in items(built, reason="validation_not_carried")}
    assert props == {("ta", "pattern"), ("e", "maxLength"), ("bad", "min")}


def test_a_pattern_that_cannot_be_enforced_is_dropped_not_carried():
    built = run(
        [
            [
                comp("textfield", "look", validate={"pattern": "^(?!x)a$"}),
                comp("textfield", "broken", validate={"pattern": "([a-z"}),
                comp("textfield", "long", validate={"pattern": "a" * 300}),
                # RE2 matches these in linear time, a browser's engine does not
                comp("textfield", "nested", validate={"pattern": "^(a+)+$"}),
                comp("textfield", "alternatives", validate={"pattern": "^(a|aa)+$"}),
                comp("textfield", "ok", validate={"pattern": "^[a-z]+( [a-z]+)*$"}),
            ]
        ]
    )
    look, broken, long_, nested, alternatives, ok = questions(built)
    for q in (look, broken, long_, nested, alternatives):
        assert "regex" not in q["validations"]
    assert ok["validations"]["regex"] == "^[a-z]+( [a-z]+)*$"
    assert {i["key"] for i in items(built, reason="validation_not_carried", severity="warning")} == {
        "look",
        "broken",
        "long",
        "nested",
        "alternatives",
    }
    # reported by property, never with the pattern itself
    assert "(a+)+" not in json.dumps(built.report.items, default=str)


def test_validator_plugins_are_reported():
    built = run([[comp("textfield", "t", validate={"plugins": ["kvk-kvkNumber"]})]])
    assert items(built, reason="validation_not_carried")[0]["detail"] == {"property": "plugins"}


# ------------------------------------------------------------------- types


def test_types_that_change_shape_are_reported():
    built = run(
        [
            [
                comp("time", "t"),
                comp("datetime", "dt"),
                comp("currency", "c"),
                comp("checkbox", "cb", validate={"required": True}),
                comp("iban", "i"),
                comp("postcode", "p"),
                comp("licenseplate", "l"),
            ]
        ]
    )
    assert [q["type"] for q in questions(built)] == ["short_text", "date", "short_text", "number", "yes_no", "short_text", "short_text", "short_text"]
    got = {(i["reason"], i["key"]) for i in items(built, code="changed")}
    assert got == {
        ("converted_to_text", "t"),
        ("datetime_split", "dt"),
        ("converted_to_number", "c"),
        ("checkbox_required_not_enforced", "cb"),
        ("converted_to_yes_no", "cb"),
        ("converted_to_text", "i"),
        ("converted_to_text", "p"),
        ("converted_to_text", "l"),
    }
    assert items(built, key="cb", reason="checkbox_required_not_enforced")[0]["severity"] == "warning"


def test_unsupported_and_unknown_types_are_dropped_and_reported():
    types = ["signature", "map", "partners", "children", "npFamilyMembers", "cosign", "coSign", "customerProfile"]
    built = run([[comp(t, t) for t in types] + [comp("somethingNew", "x"), comp("textfield", "keep")]])
    assert [q["title"] for q in questions(built)] == ["keep"]
    assert {i["detail"]["componentType"] for i in items(built, reason="unsupported_component_type")} == set(types)
    assert items(built, key="x")[0]["reason"] == "unknown_component_type"
    assert built.summary["dropped"] == len(types) + 1


def test_a_helper_component_is_left_out_without_a_word():
    built = run([[comp("softRequiredErrors", "s"), comp("textfield", "keep")]])
    assert items(built, key="s") == []


def test_a_component_without_a_usable_type_or_key_does_not_break_the_import():
    built = run([[{"label": "no type"}, {"type": 5, "key": []}, "text", None, comp("textfield", "keep")]])
    assert [q["title"] for q in questions(built)] == ["keep"]


def test_dates_carry_the_rules_that_have_an_equivalent():
    built = run(
        [
            [
                comp("date", "a", datePicker={"minDate": "2020-02-30T00:00:00+01:00"}, openForms={"minDate": {"mode": "fixedValue"}}),
                comp("date", "b", datePicker={"maxDate": "2030-12-31T00:00:00+01:00"}, openForms={"maxDate": {"mode": "fixedValue"}}),
                comp("date", "c", openForms={"minDate": {"mode": "relativeToVariable", "variable": "x"}, "maxDate": {"mode": "future"}}),
                comp("date", "d", openForms={"minDate": {"mode": "future", "includeToday": True}, "maxDate": {"mode": "past", "delta": {"days": 3}}}),
            ]
        ]
    )
    a, b, c, d = questions(built)
    assert "dateRules" not in a  # not a real day
    assert b["dateRules"] == [{"comparison": "on_or_before", "target": "date", "date": "2030-12-31"}]
    assert "dateRules" not in c
    assert d["dateRules"] == [{"comparison": "on_or_after", "target": "today"}]
    assert sorted(i["key"] for i in items(built, reason="date_rule_not_carried")) == ["a", "c", "c", "d"]


# ------------------------------------------------------------------ layout


def test_a_fieldset_becomes_a_heading_and_columns_become_widths():
    built = run(
        [
            [
                comp(
                    "fieldset",
                    "fs",
                    "Group heading",
                    components=[comp("textfield", "a"), comp("columns", "cols", columns=[{"size": 4, "components": [comp("textfield", "b")]}, {"size": 99, "components": [comp("textfield", "c")]}])],
                ),
                comp("fieldset", "quiet", "No heading", hideHeader=True, components=[comp("textfield", "d")]),
            ]
        ]
    )
    flat = [(q["type"], q["title"], q.get("colSpan")) for q in questions(built)]
    assert flat == [("text", "Group heading", None), ("short_text", "a", None), ("short_text", "b", 4), ("short_text", "c", None), ("short_text", "d", None)]


def test_a_repeating_grid_becomes_a_repeating_group():
    built = run(
        [
            [
                comp(
                    "editgrid",
                    "eg",
                    "People",
                    groupLabel="Person",
                    validate={"required": True, "maxLength": 80},
                    components=[comp("textfield", "n"), comp("file", "f"), comp("editgrid", "inner", components=[comp("textfield", "z")]), comp("radio", "r", values=[{"value": "a", "label": "A"}, {"value": "b", "label": "B"}])],
                ),
                comp("editgrid", "empty", components=[comp("file", "only")]),
            ]
        ]
    )
    [group] = questions(built)
    assert group["repeat"] == {"minItems": 1, "maxItems": 50, "itemLabel": "Person"}
    assert [c["title"] for c in group["children"]] == ["n", "r"]
    assert {(i["key"], i["reason"]) for i in items(built, kind="component")} >= {
        ("f", "not_allowed_in_repeating_group"),
        ("inner", "not_allowed_in_repeating_group"),
        ("empty", "empty_group"),
    }
    assert built.summary["repeatingGroups"] == 1


# ------------------------------------------------------------------- steps


def test_steps_become_pages_in_order_and_an_empty_one_is_dropped():
    built = run([[comp("textfield", "a")], [comp("signature", "s")], [comp("textfield", "b")]])
    assert [p["title"] for p in describe(built)["pages"]] == ["Step 1", "Step 3"]
    assert items(built, reason="empty_step")[0]["step"] == 1


def test_steps_are_ordered_by_their_index_not_their_place():
    data = load("all-components.en.zip")
    data["formSteps.json"].reverse()
    built = build_draft(read_archive(make_zip(data)))
    assert [p["title"] for p in describe(built)["pages"]] == ["Contact details", "Choices and dates", "Extras"]


def test_nothing_importable_is_refused_with_the_reasons():
    error = refusal([[comp("signature", "s"), comp("content", "c", html="<p>only text</p>")]])
    assert (error.status, error.code) == (422, "no_importable_fields")
    assert error.extra["reportItems"][0]["reason"] == "unsupported_component_type"


def test_too_many_components_or_levels_are_too_complex(monkeypatch):
    from backend.app.services.open_formulieren import limits

    monkeypatch.setattr(limits, "MAX_COMPONENTS", 5)
    assert refusal([[comp("textfield", f"k{n}") for n in range(6)]]).code == "archive_too_complex"
    monkeypatch.undo()
    deep = comp("textfield", "leaf")
    for n in range(limits.MAX_COMPONENT_DEPTH + 2):
        deep = comp("fieldset", f"f{n}", components=[deep])
    assert refusal([[deep]]).code == "archive_too_complex"


# ------------------------------------------------------------------- logic


def test_a_simple_condition_becomes_a_visibility_rule():
    cb = comp("checkbox", "cb")
    sel = comp("selectboxes", "sb", values=[{"value": "x", "label": "Ex"}, {"value": "y", "label": "Why"}])
    num = comp("number", "num")
    rad = comp("radio", "rad", values=[{"value": "a", "label": "Alpha"}, {"value": "b", "label": "Beta"}])
    built = run(
        [
            [
                cb, sel, num, rad,
                comp("textfield", "t1", conditional={"show": True, "when": "cb", "eq": True}),
                comp("textfield", "t2", conditional={"show": False, "when": "cb", "eq": "false"}),
                comp("textfield", "t3", conditional={"show": True, "when": "sb", "eq": "y"}),
                comp("textfield", "t4", conditional={"show": True, "when": "num", "eq": "5"}),
                comp("textfield", "t5", conditional={"show": False, "when": "rad", "eq": "b"}),
                comp("textfield", "t6", conditional={"show": True, "when": "rad", "eq": ""}),
                comp("textfield", "t7", conditional={"show": True, "when": "", "eq": "x"}),
                comp("textfield", "t8", conditional={"show": True, "when": "rad", "eq": None}),
            ]
        ]
    )
    logic = {q["title"]: q.get("logic") for q in questions(built) if q["title"].startswith("t")}
    one = lambda action, source, comparison, value: {  # noqa: E731
        "action": action,
        "operator": "AND",
        "conditions": [{"source": source, "comparison": comparison, "value": value}],
    }
    assert logic["t1"] == one("SHOW", "cb", "IS_EQUAL", "Yes")
    assert logic["t2"] == one("HIDE", "cb", "IS_EQUAL", "No")
    assert logic["t3"] == one("SHOW", "sb", "IS_EQUAL", "Why")
    assert logic["t4"] == one("SHOW", "num", "IS_EQUAL", 5)
    assert logic["t5"] == one("HIDE", "rad", "IS_EQUAL", "Beta")
    # an unreadable option, an incomplete condition: no rule (and for the
    # first, a report line)
    assert logic["t6"] is None and logic["t7"] is None and logic["t8"] is None
    assert reasons(built, kind="logic") == ["condition_value_not_supported"]


def test_a_condition_on_something_missing_or_later_or_dropped_is_reported():
    built = run(
        [
            [
                comp("textfield", "early", conditional={"show": True, "when": "late", "eq": "x"}),
                comp("textfield", "late"),
                comp("textfield", "t", conditional={"show": True, "when": "nowhere", "eq": "x"}),
                comp("signature", "sig"),
                comp("textfield", "u", conditional={"show": True, "when": "sig", "eq": "x"}),
                comp("textfield", "self", conditional={"show": True, "when": "self", "eq": "x"}),
            ]
        ]
    )
    assert sorted(reasons(built, kind="logic")) == [
        "condition_source_later",  # a question that depends on a later one
        "condition_source_later",  # ... or on itself
        "condition_source_missing",
        "condition_source_missing",  # a question that was dropped
    ]
    assert all(q.get("logic") is None for q in questions(built))


def test_a_condition_on_a_repeated_question_stays_inside_its_group():
    grid = comp("editgrid", "g", components=[comp("textfield", "a"), comp("textfield", "b", conditional={"show": True, "when": "a", "eq": "x"})])
    built = run([[grid, comp("textfield", "out", conditional={"show": True, "when": "a", "eq": "x"})]])
    [group, out] = questions(built)
    assert group["children"][1]["logic"]["conditions"][0]["source"] == "a"
    assert out.get("logic") is None
    assert reasons(built, kind="logic") == ["condition_source_missing"]


def test_a_layout_condition_applies_to_everything_inside_and_combines():
    built = run(
        [
            [
                comp("checkbox", "c1"),
                comp("checkbox", "c2"),
                comp(
                    "fieldset",
                    "fs",
                    "Box",
                    conditional={"show": True, "when": "c1", "eq": True},
                    components=[
                        comp("textfield", "in1"),
                        comp("textfield", "in2", conditional={"show": True, "when": "c2", "eq": True}),
                        comp("textfield", "in3", conditional={"show": False, "when": "c2", "eq": True}),
                    ],
                ),
            ]
        ]
    )
    logic = {q["title"]: q["logic"] for q in questions(built) if q.get("logic")}
    assert logic["Box"]["conditions"][0]["source"] == "c1"
    assert logic["in1"]["conditions"][0]["source"] == "c1"
    assert [c["source"] for c in logic["in2"]["conditions"]] == ["c1", "c2"] and logic["in2"]["operator"] == "AND"
    # show and hide cannot be said together: the question keeps its own
    assert logic["in3"]["action"] == "HIDE" and len(logic["in3"]["conditions"]) == 1
    assert reasons(built, kind="logic") == ["conflicting_rules"]


def test_rules_that_show_or_hide_a_component_are_translated():
    plan = comp("radio", "plan", values=[{"value": "basic", "label": "Basic"}, {"value": "pro", "label": "Pro"}])
    n = comp("number", "n")
    built = run(
        [
            [
                plan, n,
                comp("textfield", "shown", hidden=True),
                comp("textfield", "hidden"),
                comp("textfield", "pair", hidden=True),
                comp("textfield", "many"),
                comp("textfield", "clash"),
                comp("textfield", "never", hidden=True),
            ]
        ],
        logic=[
            rule(eq("plan", "pro"), hide("shown", False), order=0),
            rule({">=": [{"var": "n"}, 10]}, hide("hidden"), order=1),
            rule(eq("plan", "pro"), hide("pair", False), order=2),
            rule({"!=": [{"var": "plan"}, "pro"]}, hide("pair", True), order=3),
            rule({"or": [eq("plan", "basic"), {"<": [{"var": "n"}, 3]}]}, hide("many"), order=4),
            rule({"!": [{"var": "n"}]}, hide("many"), order=5),
            rule({"and": [eq("plan", "pro"), {">": [{"var": "n"}, 1]}]}, hide("clash"), order=6),
            rule({"<": [{"var": "n"}, 0]}, hide("clash"), order=7),
        ],
    )
    logic = {q["title"]: q.get("logic") for q in questions(built)}
    assert logic["shown"] == {"action": "SHOW", "operator": "AND", "conditions": [{"source": "plan", "comparison": "IS_EQUAL", "value": "Pro"}]}
    assert logic["hidden"] == {"action": "HIDE", "operator": "AND", "conditions": [{"source": "n", "comparison": "GREATER_THAN_EQUAL", "value": 10}]}
    assert logic["pair"]["action"] == "SHOW" and logic["pair"]["conditions"][0]["value"] == "Pro"
    # rules that hide it for different reasons become one "any of these" rule when each is a single
    # condition or itself an "any"; a rule that needs several at once cannot be joined to another
    assert logic["many"] == {
        "action": "HIDE",
        "operator": "OR",
        "conditions": [
            {"source": "plan", "comparison": "IS_EQUAL", "value": "Basic"},
            {"source": "n", "comparison": "LESS_THAN", "value": 3},
            {"source": "n", "comparison": "IS_EMPTY"},
        ],
    }
    assert logic["clash"] is None
    assert "conflicting_rules" in reasons(built, key="clash")
    # ... and a question hidden for good has nothing left to show
    assert "never" not in logic and [q["title"] for q in questions(built)].count("never") == 0
    assert reasons(built, key="never") == ["always_hidden"]
    assert built.summary["logicRules"] == 4


def test_several_simple_rules_that_hide_a_question_become_one_with_any():
    a = comp("checkbox", "a")
    b = comp("checkbox", "b")
    built = run([[a, b, comp("textfield", "t")]], logic=[rule(eq("a", True), hide("t")), rule(eq("b", True), hide("t"), order=1)])
    logic = questions(built)[2]["logic"]
    assert (logic["action"], logic["operator"]) == ("HIDE", "OR")
    assert [c["source"] for c in logic["conditions"]] == ["a", "b"]


def test_rules_outside_the_subset_are_reported_and_never_run():
    a = comp("checkbox", "a")
    built = run(
        [[a, comp("textfield", "t"), comp("textfield", "u")]],
        logic=[
            rule({"cat": ["a", {"var": "x"}]}, hide("t"), order=0, description="concat"),
            rule({"in": ["x", {"var": "a"}]}, hide("t"), order=1),
            rule({"and": [{"or": [eq("a", 1), eq("a", 2)]}, eq("a", 3)]}, hide("t"), order=2),
            rule(True, hide("t"), order=3),
            rule({"if": [eq("a", 1), 1, 2]}, hide("t"), order=4),
            rule({"==": [{"var": "a"}, {"var": "b"}]}, hide("t"), order=5),
            rule({"==": [eq("a", 1), True]}, hide("t"), order=6),
            rule({"==": [{"var": ["a", "default"]}, True]}, hide("u"), order=7),
        ],
    )
    got = reasons(built, kind="logic")
    # (a variable read with a default depends on data: not translated either)
    assert got.count("trigger_not_supported") == 8
    assert all(q.get("logic") is None for q in questions(built))


def test_actions_that_are_not_visibility_are_reported_by_type():
    steps = [[comp("number", "n"), comp("textfield", "t")], [comp("textfield", "u")]]
    action = lambda **a: {"component": "t", "variable": "v", "form_step_uuid": "x", "action": a}  # noqa: E731
    built = run(
        steps,
        logic=[
            rule(eq("n", 1), action(type="disable-next"), order=0),
            rule(eq("n", 1), action(type="step-not-applicable"), order=1),
            rule(eq("n", 1), action(type="step-applicable"), order=2),
            rule(eq("n", 1), action(type="variable", value={"+": [1, 2]}), order=3),
            rule(eq("n", 1), action(type="fetch-from-service", value="x"), order=4),
            rule(eq("n", 1), action(type="set-registration-backend", value="x"), order=5),
            rule(eq("n", 1), action(type="evaluate-dmn", config={}), order=6),
            rule(eq("n", 1), action(type="synchronize-variables", config={}), order=7),
            rule(eq("n", 1), action(type="property", property={"value": "validate", "type": "json"}, state={"required": True}), order=8),
            rule(eq("n", 1), action(type="property", property={"value": "hidden", "type": "bool"}, state="yes"), order=9),
            rule(eq("n", 1), action(type="surprise"), order=10),
        ],
    )
    got = [i["detail"] for i in items(built, kind="logic")]
    assert [d["actionType"] for d in got] == ["disable-next", "step-not-applicable", "step-applicable", "variable", "fetch-from-service", "set-registration-backend", "evaluate-dmn", "synchronize-variables", "property", "property", "surprise"]
    assert got[8]["property"] == "validate"
    assert all(i["severity"] == "warning" and i["code"] == "dropped" for i in items(built, kind="logic"))


def test_a_rule_that_names_a_missing_component_is_reported():
    built = run([[comp("checkbox", "a")]], logic=[rule(eq("a", True), hide("ghost"))])
    assert reasons(built, kind="logic") == ["target_missing"]


def test_a_rule_aimed_at_a_dropped_component_is_not_reported_twice():
    built = run([[comp("checkbox", "a"), comp("signature", "sig")]], logic=[rule(eq("a", True), hide("sig"))])
    assert reasons(built, kind="logic") == []


def test_an_always_hidden_layout_drops_what_is_inside_quietly():
    built = run([[comp("checkbox", "a"), comp("fieldset", "fs", "Box", hidden=True, components=[comp("textfield", "in")]), comp("textfield", "t")]], logic=[rule(eq("a", True), hide("in", False))])
    assert [q["title"] for q in questions(built)] == ["a", "t"]
    assert reasons(built, key="fs") == ["always_hidden"]
    assert "target_missing" not in reasons(built)


# ---------------------------------------------------------- not carried


def test_custom_code_is_reported_never_carried_and_never_run(monkeypatch, tmp_path, exec_guard):
    marker = tmp_path / "ran"
    script = f"open({str(marker)!r}, 'w').write('x'); raise SystemExit(1)"
    scripted = comp(
        "textfield",
        "t",
        label="Scripted",
        customConditional=script,
        calculateValue="throw new Error('boom'); window.location='http://evil/'",
        customDefaultValue=script,
        validate={"custom": script, "customMessage": "<b>m</b>"},
        logic=[{"trigger": {"type": "javascript", "javascript": script}, "actions": []}],
    )
    calls = exec_guard
    built = run([[scripted]], logic=[rule({"var": "t"}, hide("t"))])
    assert not marker.exists()
    assert calls == []
    got = sorted(i["detail"]["property"] for i in items(built, reason="custom_script_dropped"))
    assert got == ["calculateValue", "customConditional", "customDefaultValue", "logic", "validate.custom"]
    assert all(i["severity"] == "warning" for i in items(built, reason="custom_script_dropped"))
    # nothing of it is in the form
    text = json.dumps(describe(built)["pages"]) + built.form.model_dump_json()
    for needle in ("throw", "evil", "SystemExit", "customConditional", "calculateValue", "boom"):
        assert needle not in text


def test_the_importer_has_no_way_to_run_what_a_file_holds():
    """No JavaScript engine, template engine, JSON logic library, eval or
    subprocess is imported by the import code; a test of the source, so a
    later change that adds one fails here."""
    import ast
    from pathlib import Path

    import backend.app.services.open_formulieren as package

    banned_modules = {
        "js2py", "quickjs", "dukpy", "py_mini_racer", "pythonmonkey", "jsonlogic",
        "json_logic", "jinja2", "mako", "django", "subprocess", "importlib", "pickle",
        "marshal", "shelve", "ctypes", "os", "runpy", "code", "codeop", "pydoc",
    }
    banned_names = {"eval", "exec", "compile", "__import__"}
    banned_attributes = {"eval", "exec", "system", "popen", "load", "loads_unsafe"} - {"load"}
    root = Path(package.__file__).parent
    sources = list(root.glob("*.py")) + [
        root.parent / "open_formulieren_import_service.py",
        root.parent / "open_formulieren_mode.py",
        root.parent.parent / "controllers" / "open_formulieren_import_router.py",
    ]
    assert len(sources) >= 10
    for path in sources:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or "").split(".")[0]}
            else:
                names = set()
            assert not names & banned_modules, (path.name, names)
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    assert func.id not in banned_names, (path.name, func.id)
                elif isinstance(func, ast.Attribute):
                    assert func.attr not in banned_attributes, (path.name, func.attr)


def test_nothing_in_the_archive_is_ever_fetched(monkeypatch):
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("the import opened a connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    data = load("all-components.en.zip")
    data["forms.json"][0]["url"] = "http://169.254.169.254/latest/meta-data/"
    data["formSteps.json"][0]["url"] = "file:///etc/passwd"
    data["formSteps.json"][0]["form_definition"] += "?x=http://169.254.169.254/"
    built = build_draft(read_archive(make_zip(data)))
    assert built.summary["pages"] == 3


def test_features_that_are_not_carried_are_reported():
    built = build("signin-prefill-payment.en.zip")
    by = {(i["reason"], i.get("detail", {}).get("plugin")) for i in built.report.items}
    assert ("sign_in_not_carried", "digid") in by
    assert ("payment_not_carried", "worldline") in by
    assert {(i["key"], i["detail"]["plugin"]) for i in items(built, reason="prefill_not_carried")} == {("bsn", "demo"), ("fullName", "demo")}
    built = build("special-components.en.zip")
    assert ("registration_not_carried", "email") in {(i["reason"], i.get("detail", {}).get("plugin")) for i in built.report.items}
    assert ("appointment_not_carried", None) in {(i["reason"], i.get("detail", {}).get("plugin")) for i in build("appointment.en.zip").report.items}


def test_user_variables_are_reported_and_static_ones_are_not_in_the_file():
    built = build("logic-variables.en.zip")
    assert sorted(i["key"] for i in items(built, kind="variable")) == ["greeting", "isPremium", "reviewDate", "tags", "total"]
    assert items(built, kind="variable", key="total")[0]["detail"] == {"dataType": "float"}


def test_an_unexpected_entry_is_listed_in_the_report():
    built = build_draft(read_archive(archive_with([[comp("textfield", "a")]], extra={"README.txt": b"hello"})))
    assert items(built, kind="archive") == [
        {"code": "ignored", "kind": "archive", "reason": "archive_entry_ignored", "severity": "info", "key": "README.txt"}
    ]


# --------------------------------------------------------------- settings


@pytest.mark.parametrize(
    "options, expected",
    [
        ({"successful_submissions_removal_limit": 30, "successful_submissions_removal_method": "delete_permanently"}, ("days", "30")),
        ({"successful_submissions_removal_limit": 3650}, ("days", "3650")),
        ({"successful_submissions_removal_limit": 3651}, (None, "")),
        ({"successful_submissions_removal_limit": 0}, (None, "")),
        ({"successful_submissions_removal_limit": "x"}, (None, "")),
        ({"successful_submissions_removal_limit": None}, (None, "")),
        ({}, (None, "")),
    ],
)
def test_retention_days_are_carried_when_the_form_states_them(options, expected):
    built = run([[comp("textfield", "a")]], form={"submissions_removal_options": options})
    kind, value = describe(built)["retention"]
    assert (kind, value) == expected


def test_a_method_we_do_not_have_is_reported():
    built = run([[comp("textfield", "a")]], form={"submissions_removal_options": {"successful_submissions_removal_limit": 10, "successful_submissions_removal_method": "make_anonymous", "all_submissions_removal_limit": 5}})
    assert {"retention_method_not_carried", "retention_other_limits_not_carried"} <= set(reasons(built))
    assert items(built, reason="retention_method_not_carried")[0]["severity"] == "warning"


def test_the_privacy_policy_and_purpose_are_noted_as_missing():
    built = run([[comp("textfield", "a")]])
    assert [(i["code"], i["reason"]) for i in items(built, kind="setting")][:2] == [("noted", "privacy_policy_missing"), ("noted", "purpose_missing")]


def test_the_draft_is_never_published_and_has_no_custom_address():
    built = run([[comp("textfield", "a")]], form={"active": True, "slug": "nice-slug"})
    form = built.form
    assert form.published_at is None and form.settings.custom_url is None
    assert form.title == "Synthetic"


def test_a_form_without_a_name_gets_a_neutral_title():
    built = run([[comp("textfield", "a")]], form={"name": "  <b> </b>  "})
    assert built.title == "Imported form"


def test_a_huge_report_is_cut_but_counted(monkeypatch):
    from backend.app.services.open_formulieren import limits

    monkeypatch.setattr(limits, "MAX_REPORT_ITEMS", 5)
    built = run([[comp("signature", f"s{n}") for n in range(20)] + [comp("textfield", "keep")]])
    assert len(built.report.items) == 5 and built.report.truncated
    assert built.summary["dropped"] >= 20


def test_the_exec_guard_sees_our_modules_and_ignores_others(exec_guard):
    """The guard of the test above is not vacuous: a call to eval/exec/compile
    made from a module of the import code is counted, one made from anywhere
    else is not (and still works)."""
    ours = {"__name__": "backend.app.services.open_formulieren.fake"}
    other = {"__name__": "somebody.else"}
    exec("value = eval('1 + 1')", other)
    assert other["value"] == 2 and exec_guard == []
    exec("value = eval('1 + 1'); code = compile('2', 'x', 'eval')", ours)
    assert ours["value"] == 2
    assert exec_guard == ["eval", "compile"]


EMPTY_HELP = {
    "help_dialog": {"content": "", "image": None},
    "help_callout_page": {"display": "never", "content": "", "image": None},
}


def test_empty_help_settings_are_not_reported():
    """4.0 exports always write both help objects; empty ones say nothing."""
    built = run([[comp("textfield", "a")]], form=EMPTY_HELP)
    assert "presentation_not_carried" not in reasons(built)


@pytest.mark.parametrize(
    "help_settings",
    [
        {"help_dialog": {"content": "<p>Ask us</p>", "image": None}},
        {"help_dialog": {"content": "", "image": "http://localhost/media/help.png"}},
        {"help_callout_page": {"display": "before_start_page", "content": "", "image": None}},
        {"help_callout_page": {"display": "after_start_page", "content": "", "image": None}},
    ],
    ids=["dialog-content", "dialog-image", "callout-before-start", "callout-after-start"],
)
def test_help_settings_with_content_are_reported(help_settings):
    built = run([[comp("textfield", "a")]], form={**EMPTY_HELP, **help_settings})
    assert "presentation_not_carried" in reasons(built)


def test_whitespace_help_or_odd_shapes_are_not_reported():
    built = run(
        [[comp("textfield", "a")]],
        form={"help_dialog": {"content": "   \n"}, "help_callout_page": "never"},
    )
    assert "presentation_not_carried" not in reasons(built)


@pytest.mark.parametrize("display", ["never", "NEVER", "always", ["before_start_page"], 0, None])
def test_a_callout_not_shown_by_the_form_is_not_reported(display):
    """The callout's text and image are the instance's, not the form's: only
    a known ``display`` that shows it counts."""
    callout = {"display": display, "content": "<p>Global help</p>", "image": "http://localhost/x.png"}
    built = run([[comp("textfield", "a")]], form={**EMPTY_HELP, "help_callout_page": callout})
    assert "presentation_not_carried" not in reasons(built)
