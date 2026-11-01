"""The parts that need no database: text rules, ids, narrowing, searching, the
shape checks and the "new or changed" comparison."""

import pytest
from common.models.standard_form import StandardForm

from backend.app.services.option_sources import ids, read, text
from backend.app.services.option_sources.checks import (
    new_or_changed,
    piece,
    strip_option_sources,
    structural_problems,
)
from backend.app.services.option_sources.service import (
    Option,
    _with_labels,
    _without_labels,
    chosen_ids,
    narrow,
    search,
    snapshot_labels,
)


def form(*questions):
    return StandardForm(
        builder_version="v2",
        title="t",
        fields=[
            {"id": "p", "type": "slide", "properties": {"fields": list(questions)}}
        ],
    )


def q(field_id, kind="dropdown", source=None, **properties):
    props = dict(properties)
    if source is not None:
        props["option_source"] = source
    return {"id": field_id, "type": kind, "title": field_id, "properties": props}


LIST = {"kind": "list", "list_id": "a" * 24}
ANSWERS = {"kind": "form_answers", "form_id": "b" * 24, "question_id": "q1"}


def test_clean_normalises_and_refuses_hidden_characters():
    assert text.clean("  Zoë \n  van   Dam ", 50) == "Zoë van Dam"
    assert text.clean("é", 5) == "é"  # Unicode form C
    for bad in ("a​b", "a‮b", "a\x00b", "", "   ", None, 5, "x" * 51):
        assert text.clean(bad, 50) is None
    assert text.fold("  Éá  B ") == text.fold("éá b") == "éá b"


def test_answer_ids_are_keyed_scoped_and_stable(monkeypatch):
    first = ids.answer_option_id("w1", "f1", "q1", "alice")
    assert first == ids.answer_option_id("w1", "f1", "q1", "alice")
    assert first.startswith("fa") and len(first) == 24 and "alice" not in first
    assert first != ids.answer_option_id("w1", "f1", "q2", "alice")
    assert first != ids.answer_option_id("w1", "f2", "q1", "alice")
    assert first != ids.answer_option_id("w2", "f1", "q1", "alice")
    assert ids.is_source_id(first) and ids.is_source_id(ids.new_item_id())
    assert not ids.is_source_id("c1")
    # another secret, another id: a leaked id cannot be checked against names
    from backend.config import settings

    monkeypatch.setattr(settings.auth_settings, "JWT_SECRET", "another-secret-value")
    assert ids.answer_option_id("w1", "f1", "q1", "alice") != first


def options():
    return [
        Option("1", "Amsterdam", "amsterdam", "netherlands"),
        Option("2", "Berlin", "berlin", "germany"),
        Option("3", "Anywhere", "anywhere", None),
    ]


def test_a_dependent_list_offers_the_parents_group_and_group_less_items():
    pool = options()
    assert [o.id for o in narrow(pool, None)] == [
        "1",
        "2",
        "3",
    ]  # no answer: nothing filtered
    assert [o.id for o in narrow(pool, {"netherlands"})] == ["1", "3"]
    assert [o.id for o in narrow(pool, {"germany", "netherlands"})] == ["1", "2", "3"]
    assert [o.id for o in narrow(pool, set())] == [
        "3"
    ]  # a parent option no group matches


def test_search_is_a_case_insensitive_contains_and_pages():
    pool = options()
    found, total = search(pool, "BER", 10, 0)
    assert [o.id for o in found] == ["2"] and total == 1
    found, total = search(pool, None, 2, 1)
    assert [o.id for o in found] == ["2", "3"] and total == 3
    assert search(pool, "zzz", 5, 0) == ([], 0)


def test_choice_answers_read_and_carry_a_label_snapshot():
    single = {"type": "choice", "choice": {"value": "li1", "label": "A"}}
    assert chosen_ids(single) == ["li1"] and snapshot_labels(single) == {"li1": "A"}
    many = {"type": "choices", "choices": {"values": ["x", "y"], "labels": {"x": "X"}}}
    assert chosen_ids(many) == ["x", "y"] and snapshot_labels(many) == {"x": "X"}
    out = _with_labels(many, {"x": "X2", "y": "Y"})
    assert out["choices"]["labels"] == {"x": "X2", "y": "Y"}
    assert "labels" not in _with_labels(many, {})["choices"]
    # a label for an id that was not chosen is not kept
    assert _with_labels(single, {"other": "Z"})["choice"].get("label") is None
    assert "label" not in _without_labels(single)["choice"]
    plain = {"type": "choice", "choice": {"value": "c1"}}
    assert _without_labels(plain) is plain


def test_structure_a_source_excludes_own_options_and_needs_a_choice_question():
    assert structural_problems(form(q("a", source=LIST))) == []
    assert structural_problems(form(q("a", source=ANSWERS))) == []
    bad = structural_problems(form(q("a", kind="short_text", source=LIST)))
    assert "dropdown" in bad[0]["message"]
    with_choices = structural_problems(
        form(q("a", source=LIST, choices=[{"id": "c1", "value": "X"}]))
    )
    assert any("options of its own" in p["message"] for p in with_choices)
    filtered = structural_problems(
        form(q("a", source=LIST, option_filter={"field_id": "z", "mapping": []}))
    )
    assert any("filter" in p["message"] for p in filtered)
    assert structural_problems(form(q("a", source={"kind": "list"})))
    assert structural_problems(
        form(q("a", source={"kind": "form_answers", "form_id": "x"}))
    )
    assert structural_problems(form(q("a", source={**ANSWERS, "list_id": "l"})))
    assert structural_problems(form(q("a", source={**LIST, "form_id": "f"})))


def test_structure_a_source_is_not_inside_a_group_and_a_parent_comes_first():
    group = {
        "id": "g",
        "type": "group",
        "title": "g",
        "properties": {"fields": [q("in", source=LIST)]},
    }
    assert any("group" in p["message"] for p in structural_problems(form(group)))
    ok = form(
        q("country", choices=[{"id": "c1", "value": "NL"}]),
        q("city", source={**LIST, "parent_field_id": "country"}),
    )
    assert structural_problems(ok) == []
    after = form(
        q("city", source={**LIST, "parent_field_id": "country"}),
        q("country", choices=[{"id": "c1", "value": "NL"}]),
    )
    assert any("before" in p["message"] for p in structural_problems(after))
    for parent in ("city", "missing"):
        assert structural_problems(
            form(q("city", source={**LIST, "parent_field_id": parent}))
        )
    # the parent of a form-answers source is not allowed
    assert structural_problems(
        form(
            q("c", choices=[{"id": "c1", "value": "x"}]),
            q("d", source={**ANSWERS, "parent_field_id": "c"}),
        )
    )


def test_structure_a_condition_on_a_sourced_question_only_tests_whether_it_is_answered():
    def with_logic(comparison):
        return form(
            q("a", source=LIST),
            {
                "id": "b",
                "type": "short_text",
                "title": "b",
                "properties": {
                    "logic": {
                        "action": "SHOW",
                        "operator": "AND",
                        "conditions": [
                            {
                                "field_id": "a",
                                "field_type": "dropdown",
                                "comparison": comparison,
                                "value": "x",
                            }
                        ],
                    }
                },
            },
        )

    assert structural_problems(with_logic("is_not_empty")) == []
    assert structural_problems(with_logic("IS_EMPTY")) == []
    assert any(
        "answered" in p["message"] for p in structural_problems(with_logic("is_equal"))
    )
    assert any(
        "answered" in p["message"] for p in structural_problems(with_logic("IS_EQUAL"))
    )


def test_a_source_is_new_or_changed_unless_stored_as_it_is():
    stored = form(q("a", source=LIST))
    assert new_or_changed(stored, stored) == []
    assert new_or_changed(stored, None) == ["a"]
    assert new_or_changed(form(q("a", source=ANSWERS)), stored) == ["a"]
    assert (
        new_or_changed(form(q("a")), stored) == []
    )  # a source taken away asks nothing
    # a moved question with the same source is the same
    moved = form(q("z", kind="short_text"), q("a", source=LIST))
    assert new_or_changed(moved, stored) == []
    assert piece(read.source_dict(read.page_questions(stored).__next__())) == piece(
        LIST
    )


def test_stripping_removes_sources_by_kind():
    both = form(q("a", source=LIST), q("b", source=ANSWERS))
    assert strip_option_sources(both, ("form_answers",)) == 1
    assert [s["kind"] for _, s in read.sourced_questions(both)] == ["list"]
    assert strip_option_sources(both) == 1
    assert list(read.sourced_questions(both)) == []


def test_the_spec_model_and_stored_model_agree_on_the_keys():
    from common.models.standard_form import OptionSource

    source = OptionSource(**{"kind": "list", "listId": "x", "parentFieldId": "p"})
    assert source.list_id == "x" and source.parent_field_id == "p"
    assert source.model_dump(by_alias=True, exclude_none=True) == {
        "kind": "list",
        "listId": "x",
        "parentFieldId": "p",
    }
    with pytest.raises(Exception):
        OptionSource(kind="url", list_id="x")
