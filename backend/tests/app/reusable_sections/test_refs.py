"""Isolating, remapping and closing the references of a section fragment (pure)."""

import copy

import pytest

from backend.app.services.reusable_sections import refs


def cond(field_id, comparison="equals", value="x", **extra):
    return {"fieldId": field_id, "comparison": comparison, "value": value, **extra}


def pipe(key, kind="field"):
    return {"type": refs.PIPE_NODE, "attrs": {"kind": kind, "pipeKey": key, "label": "x"}}


def rich(*nodes):
    return {"type": "doc", "content": [{"type": "paragraph", "content": list(nodes)}]}


def section():
    """Questions a..g inside the section; every kind of reference between them."""
    fields = [
        {"id": "a", "type": "short_text", "title": rich({"type": "text", "text": "Name "}, pipe("b"))},
        {"id": "b", "type": "number", "title": "Age", "logic": {"action": "SHOW", "operator": "AND", "conditions": [cond("a")]}},
        {
            "id": "c",
            "type": "multiple_choice",
            "title": "Pick {{field:a|someone}}",
            "choices": [
                {"id": "c1", "value": "one", "logic": {"action": "SHOW", "operator": "AND", "conditions": [cond("a")]}},
                {"id": "c2", "value": "two"},
            ],
            "optionFilter": {"fieldId": "d", "mapping": [{"when": "d1", "show": ["c1"]}]},
        },
        {
            "id": "d",
            "type": "dropdown",
            "title": "Kind",
            "choices": [{"id": "d1", "value": "p"}, {"id": "d2", "value": "q"}],
            "optionSource": None,
        },
        {"id": "e", "type": "date", "title": "When", "dateRules": [{"comparison": "after", "target": "field", "fieldId": "a"}, {"comparison": "before", "target": "today"}]},
        {
            "id": "f",
            "type": "short_text",
            "title": "F",
            "rules": [
                {"id": "r1", "when": {"conditions": [cond("b", "greater_than", 3)]}, "then": {"required": True, "title": "Because {{field:b}}"}},
                {"id": "r2", "when": {"expression": {">": [{"var": "b"}, 1]}}, "then": {"setValue": {"expression": {"+": [{"var": "b"}, {"var": "g.h"}]}}}},
            ],
        },
        {
            "id": "g",
            "type": "group",
            "title": "People",
            "repeat": {"minItems": 1, "maxItems": 3, "itemTitle": "Person {{field:h}}"},
            "fields": [
                {"id": "h", "type": "short_text", "title": "Who"},
                {"id": "i", "type": "short_text", "title": "Role", "logic": {"action": "SHOW", "operator": "AND", "conditions": [cond("h")]}},
            ],
        },
        {"id": "j", "type": "calculated", "title": "Total", "expression": {"+": [{"var": "b"}, {"var": "g.h"}, {"var": "e.start"}]}},
        {"id": "k", "type": "short_text", "title": rich(pipe("g:count", "group"), pipe("g:list:h", "group"))},
    ]
    containers = [
        {"id": "box", "type": "panel", "title": "Box", "fields": ["a", "b"], "logic": {"action": "SHOW", "operator": "AND", "conditions": [cond("d")]}},
        {"id": "strip", "type": "tabs", "tabs": [{"id": "t1", "title": "One", "fields": ["c"]}, {"id": "t2", "title": "Two", "fields": ["d"]}]},
    ]
    return fields, containers


def by_id(fields):
    return {f["id"]: f for f in refs.questions(fields)}


def test_a_closed_section_isolates_to_itself_without_warnings():
    fields, containers = section()
    before = copy.deepcopy((fields, containers))
    kept, kept_containers, warnings = refs.isolate(fields, containers)
    assert warnings == []
    assert (kept, kept_containers) == before
    refs.assert_closed(kept, kept_containers)


def test_a_reference_to_a_question_outside_is_dropped_with_a_warning_per_kind():
    fields, containers = section()
    by = by_id(fields)
    by["b"]["logic"]["conditions"].append(cond("outside"))
    by["c"]["choices"][1]["logic"] = {"action": "HIDE", "operator": "OR", "conditions": [cond("outside")]}
    by["c"]["optionFilter"]["fieldId"] = "outside"
    by["e"]["dateRules"][0]["fieldId"] = "outside"
    by["f"]["rules"][0]["when"]["conditions"].append(cond("outside"))
    by["f"]["rules"][1]["when"] = {"expression": {">": [{"var": "outside"}, 1]}}
    by["a"]["title"]["content"][0]["content"].append(pipe("outside"))
    by["a"]["title"]["content"][0]["content"].append(pipe("utm", "hidden"))
    by["h"]["title"] = "Who {{field:outside|them}} {{hidden:utm|there}}"
    by["i"]["logic"]["conditions"].append(cond("g", "equals", "1", groupMode="ANY", childFieldId="outside"))
    containers[0]["logic"]["conditions"].append(cond("outside"))
    kept, kept_containers, warnings = refs.isolate(fields, containers)
    codes = sorted(w.code for w in warnings)
    assert codes == sorted(
        [
            refs.CONDITION_DROPPED,  # b
            refs.CONDITION_DROPPED,  # choice c2 logic (left without conditions)
            refs.OPTION_FILTER_DROPPED,
            refs.DATE_RULE_DROPPED,
            refs.RULE_DROPPED,  # rule 1 (one condition outside) ...
            refs.RULE_DROPPED,  # ... and rule 2 (expression)
            refs.PIPE_DROPPED,  # rich outside
            refs.PIPE_DROPPED,  # rich hidden
            refs.PIPE_DROPPED,  # token outside
            refs.PIPE_DROPPED,  # token hidden
            refs.CONDITION_DROPPED,  # i (child outside)
            refs.CONTAINER_CONDITION_DROPPED,
        ]
    )
    new = by_id(kept)
    assert [c["fieldId"] for c in new["b"]["logic"]["conditions"]] == ["a"]
    assert new["c"]["choices"][1]["logic"] is None
    assert new["c"]["optionFilter"] is None
    assert new["e"]["dateRules"] == [{"comparison": "before", "target": "today"}]
    assert "rules" not in new["f"] or new["f"]["rules"] is None
    assert new["h"]["title"] == "Who them there"
    assert [c["fieldId"] for c in new["i"]["logic"]["conditions"]] == ["h"] or new["i"]["logic"]["conditions"][0]["fieldId"] == "g"
    assert [c["fieldId"] for c in kept_containers[0]["logic"]["conditions"]] == ["d"]
    refs.assert_closed(kept, kept_containers)


def test_a_calculation_that_reads_outside_is_left_out_and_so_is_what_reads_it():
    fields, containers = section()
    by = by_id(fields)
    by["j"]["expression"] = {"+": [{"var": "outside"}, {"var": "b"}]}
    fields.append(
        {"id": "m", "type": "short_text", "title": "M", "logic": {"action": "SHOW", "operator": "AND", "conditions": [cond("j")]}}
    )
    containers[0]["fields"] = ["a", "b", "j"]
    kept, kept_containers, warnings = refs.isolate(fields, containers)
    ids = refs.question_ids(kept)
    assert "j" not in ids
    assert any(w.code == refs.CALCULATION_LEFT_OUT and w.field_id == "j" for w in warnings)
    assert by_id(kept)["m"].get("logic") is None
    assert kept_containers[0]["fields"] == ["a", "b"]
    refs.assert_closed(kept, kept_containers)


def test_a_form_answers_source_and_sharing_never_stay_and_a_list_source_loses_a_foreign_parent():
    fields, containers = section()
    by = by_id(fields)
    by["d"]["optionSource"] = {"kind": "form_answers", "formId": "f1", "questionId": "q1"}
    by["c"]["optionSource"] = {"kind": "list", "listId": "li1", "parentFieldId": "outside"}
    by["a"]["shareAsChoices"] = True
    _, _, warnings = refs.isolate(fields, containers)
    codes = {w.code for w in warnings}
    assert {refs.FORM_ANSWERS_SOURCE_DROPPED, refs.SOURCE_PARENT_DROPPED, refs.SHARE_AS_CHOICES_DROPPED} <= codes
    assert by["d"]["optionSource"] is None and by["a"]["shareAsChoices"] is None
    assert by["c"]["optionSource"] == {"kind": "list", "listId": "li1"}


def fresh_mapping(fields):
    return {old: f"n-{old}" for old in refs.question_ids(fields)}


def remapped():
    fields, containers = section()
    mapping = fresh_mapping(fields)
    kept, kept_containers = refs.remap(
        fields,
        containers,
        mapping,
        fresh_rule_id=lambda old: f"rule-{old}",
        layout_id=lambda kind, old: f"new-{old}",
    )
    return kept, kept_containers, mapping


def test_remap_points_every_kind_of_reference_at_the_new_ids():
    kept, containers, mapping = remapped()
    new = by_id(kept)
    assert set(new) == set(mapping.values())
    assert new["n-a"]["title"]["content"][0]["content"][1]["attrs"]["pipeKey"] == "n-b"
    assert new["n-b"]["logic"]["conditions"][0]["fieldId"] == "n-a"
    assert new["n-c"]["title"] == "Pick {{field:n-a|someone}}"
    assert new["n-c"]["choices"][0]["logic"]["conditions"][0]["fieldId"] == "n-a"
    # choice ids are scoped to their question and stay
    assert [c["id"] for c in new["n-c"]["choices"]] == ["c1", "c2"]
    assert new["n-c"]["optionFilter"] == {"fieldId": "n-d", "mapping": [{"when": "d1", "show": ["c1"]}]}
    assert new["n-e"]["dateRules"][0]["fieldId"] == "n-a"
    rule1, rule2 = new["n-f"]["rules"]
    assert (rule1["id"], rule2["id"]) == ("rule-r1", "rule-r2")
    assert rule1["when"]["conditions"][0]["fieldId"] == "n-b"
    assert rule1["then"]["title"] == "Because {{field:n-b}}"
    assert rule2["when"]["expression"] == {">": [{"var": "n-b"}, 1]}
    # a repeating group's question is keyed <group>.<child>
    assert rule2["then"]["setValue"]["expression"] == {"+": [{"var": "n-b"}, {"var": "n-g.n-h"}]}
    assert new["n-g"]["repeat"]["itemTitle"] == "Person {{field:n-h}}"
    assert new["n-i"]["logic"]["conditions"][0]["fieldId"] == "n-h"
    assert new["n-j"]["expression"] == {"+": [{"var": "n-b"}, {"var": "n-g.n-h"}, {"var": "n-e.start"}]}
    pipes = new["n-k"]["title"]["content"][0]["content"]
    assert [p["attrs"]["pipeKey"] for p in pipes] == ["n-g:count", "n-g:list:n-h"]
    assert containers[0]["id"] == "new-box" and containers[0]["fields"] == ["n-a", "n-b"]
    assert containers[0]["logic"]["conditions"][0]["fieldId"] == "n-d"
    assert [t["id"] for t in containers[1]["tabs"]] == ["new-t1", "new-t2"]
    assert [t["fields"] for t in containers[1]["tabs"]] == [["n-c"], ["n-d"]]
    refs.assert_closed(kept, containers)


def test_two_remaps_of_one_section_share_no_id():
    first, _, one = remapped()
    fields, containers = section()
    second_mapping = {old: f"m-{old}" for old in refs.question_ids(fields)}
    second, _ = refs.remap(fields, containers, second_mapping)
    assert not set(refs.question_ids(first)) & set(refs.question_ids(second))


def test_remap_refuses_a_reference_that_escapes():
    fields, containers = section()
    by_id(fields)["b"]["logic"]["conditions"].append(cond("outside"))
    with pytest.raises(refs.EscapeError):
        refs.remap(fields, containers, fresh_mapping(fields))


@pytest.mark.parametrize(
    "edit",
    [
        lambda by: by["n-b"]["logic"]["conditions"].append(cond("elsewhere")),
        lambda by: by["n-f"]["rules"][1]["then"]["setValue"].update(expression={"var": "elsewhere"}),
        lambda by: by["n-j"].update(expression={"var": "elsewhere.x"}),
        lambda by: by["n-c"]["optionFilter"].update(fieldId="elsewhere"),
        lambda by: by["n-a"]["title"]["content"][0]["content"].append(pipe("elsewhere")),
        lambda by: by["n-h"].update(title="{{hidden:utm}}"),
    ],
)
def test_assert_closed_catches_a_reference_to_another_form(edit):
    kept, containers, _ = remapped()
    edit(by_id(kept))
    with pytest.raises(refs.EscapeError):
        refs.assert_closed(kept, containers)


def test_a_container_member_outside_is_an_escape():
    kept, containers, _ = remapped()
    containers[0]["fields"].append("somewhere-else")
    with pytest.raises(refs.EscapeError):
        refs.assert_closed(kept, containers)


def test_deeply_nested_expression_does_not_overflow_the_stack():
    fields = [{"id": "a", "type": "number", "title": "A"}]
    node = {"var": "a"}
    for _ in range(5000):
        node = {"+": [node, 1]}
    fields.append({"id": "b", "type": "calculated", "title": "B", "expression": node})
    kept, _, warnings = refs.isolate(fields, [])
    assert warnings == [] and len(kept) == 2
