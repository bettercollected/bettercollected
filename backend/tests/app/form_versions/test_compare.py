"""The classification of a structured diff into coded entries
(services/form_versions/compare.py): what a screen words in a sentence.
Pure functions on spec documents; no database."""

import copy

from backend.app.services.form_versions.compare import MAX_ENTRIES, compare_specs, plain


def doc(*pages, **form):
    return {
        "specVersion": "1",
        "pages": [
            {"id": f"p{i}", "fields": list(fields)} for i, fields in enumerate(pages, 1)
        ],
        **form,
    }


def q(qid, title=None, qtype="short_text", **extra):
    return {"id": qid, "type": qtype, "title": title or qid, **extra}


def kinds(result):
    return [(e["kind"], e["ref"]) for e in result["entries"]]


def only(result, kind):
    found = [e for e in result["entries"] if e["kind"] == kind]
    assert len(found) == 1, result["entries"]
    return found[0]


def test_identical_versions_have_no_changes():
    one = doc([q("a"), q("b")], title="Form")
    result = compare_specs(one, copy.deepcopy(one))
    assert result == {"changed": False, "entries": [], "truncated": False}


def test_added_and_removed_questions_carry_their_title_type_and_page():
    before = doc([q("a", "Name")], [q("b", "Phone", "phone_number")])
    after = doc([q("a", "Name"), q("c", "Email", "email")], [])
    result = compare_specs(before, after)
    added = only(result, "question_added")
    assert added["ref"] == "c" and added["title"] == "Email"
    assert added["params"] == {"type": "email", "page": 1}
    removed = only(result, "question_removed")
    assert removed["ref"] == "b" and removed["title"] == "Phone"
    assert removed["params"] == {"type": "phone_number", "page": 2}


def test_a_renamed_question_is_changed_not_added_and_removed():
    before = doc([q("a", "Name"), q("b")])
    after = doc([q("a", "Full name"), q("b")])
    result = compare_specs(before, after)
    assert kinds(result) == [("title_changed", "a")]
    entry = result["entries"][0]
    assert entry["params"] == {"before": "Name", "after": "Full name"}
    assert entry["title"] == "Full name"


def test_a_retyped_question():
    result = compare_specs(
        doc([q("a", qtype="short_text")]), doc([q("a", qtype="long_text")])
    )
    entry = only(result, "type_changed")
    assert entry["params"] == {"before": "short_text", "after": "long_text"}


def test_required_and_other_validations_are_separate_entries():
    before = doc([q("a", validations={"required": False, "maxLength": 10})])
    after = doc([q("a", validations={"required": True, "maxLength": 20, "pattern": "x"})])
    result = compare_specs(before, after)
    assert only(result, "required_changed")["params"] == {"required": True}
    assert only(result, "validation_changed")["params"] == {
        "keys": ["maxLength", "pattern"]
    }


def test_choices_added_removed_renamed_and_reordered():
    def choice(cid, value):
        return {"id": cid, "value": value}

    before = doc(
        [q("a", qtype="dropdown", choices=[choice("1", "Red"), choice("2", "Green"), choice("3", "Blue")])]
    )
    after = doc(
        [q("a", qtype="dropdown", choices=[choice("3", "Blue"), choice("1", "Crimson"), choice("4", "Pink")])]
    )
    result = compare_specs(before, after)
    assert only(result, "choice_added")["params"] == {"value": "Pink"}
    assert only(result, "choice_removed")["params"] == {"value": "Green"}
    assert only(result, "choice_renamed")["params"] == {
        "before": "Red",
        "after": "Crimson",
    }
    assert ("choices_reordered", "a") in kinds(result)


def test_rules_logic_and_calculations_are_named_without_spelling_them_out():
    rule = {"id": "r1", "when": {"expression": "1"}, "then": {"required": True}}
    before = doc([q("a", rules=[rule]), q("b"), q("c", qtype="calculated", expression="1+1")])
    after = doc(
        [
            q("a", rules=[rule, {"id": "r2", "when": {"expression": "2"}, "then": {"readOnly": True}}]),
            q("b", logic={"action": "HIDE", "conditions": []}),
            q("c", qtype="calculated", expression="1+2"),
        ]
    )
    result = compare_specs(before, after)
    assert only(result, "rules_changed")["params"] == {
        "added": 1,
        "removed": 0,
        "changed": 0,
    }
    assert ("logic_changed", "b") in kinds(result)
    assert ("calculation_changed", "c") in kinds(result)


def test_rules_in_another_order():
    r1 = {"id": "r1", "when": {"expression": "1"}, "then": {"required": True}}
    r2 = {"id": "r2", "when": {"expression": "2"}, "then": {"required": True}}
    result = compare_specs(doc([q("a", rules=[r1, r2])]), doc([q("a", rules=[r2, r1])]))
    assert kinds(result) == [("rules_reordered", "a")]


def test_moving_a_question_to_another_page_is_a_move_with_page_numbers():
    before = doc([q("a"), q("b")], [q("c")])
    after = doc([q("a")], [q("c"), q("b")])
    result = compare_specs(before, after)
    moved = only(result, "question_moved")
    assert moved["ref"] == "b" and moved["params"] == {"before": 1, "after": 2}


def test_pages_added_removed_and_jumps():
    before = doc([q("a")], [q("b")])
    after = doc([q("a")], [q("b")], [q("c")])
    after["pages"][0]["jumps"] = [{"target": "p3"}]
    result = compare_specs(before, after)
    assert only(result, "page_added")["params"] == {"number": 3}
    assert ("page_jumps_changed", "p1") in kinds(result)
    gone = compare_specs(after, before)
    assert only(gone, "page_removed")["ref"] == "p3"


def test_form_level_changes():
    before = doc([q("a")], title="Old", language="en", hiddenFields=["utm"])
    after = doc([q("a")], title="New", language="nl", hiddenFields=["ref"], theme={"title": "x"})
    result = compare_specs(before, after)
    assert only(result, "form_title_changed")["params"] == {
        "before": "Old",
        "after": "New",
    }
    assert only(result, "language_changed")["params"] == {"before": "en", "after": "nl"}
    assert only(result, "hidden_fields_added")["params"] == {"names": ["ref"]}
    assert only(result, "hidden_fields_removed")["params"] == {"names": ["utm"]}
    assert ("theme_changed", None) in kinds(result)


def test_a_change_with_no_word_is_listed_by_its_key():
    result = compare_specs(
        doc([q("a", placeholder="one")]), doc([q("a", placeholder="two")])
    )
    assert only(result, "other_changed")["params"] == {"keys": ["placeholder"]}


def test_rich_titles_and_html_are_flattened_and_cut():
    rich = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Your "}, {"type": "text", "text": "name"}]}
        ],
    }
    assert plain(rich) == "Your name"
    assert plain("<p>Hello <b>there</b></p>") == "Hello there"
    assert plain(None) == ""
    assert len(plain("x" * 500)) == 160 and plain("x" * 500).endswith("…")


def test_entries_are_capped():
    before = doc([])
    after = doc([q(f"q{i}") for i in range(MAX_ENTRIES + 20)])
    result = compare_specs(before, after)
    assert len(result["entries"]) == MAX_ENTRIES and result["truncated"] is True
