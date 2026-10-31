"""Field rules, the second part: the operation ``set_field_rules``, the flag
on every write path (the comparison of stored and new rules, the last gate
in ``persist_form``, the spec check's warning), and the builder's save
dropping the rules of a question that became internal. The shared cases of
the operation are in docs/spec/form-ops-v1.cases.json."""

import pytest
from common.models.standard_form import FORM_FIELD_RULES_MAX
from pydantic import ValidationError

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.services.ai.ops import apply_form_ops, parse_ops
from backend.app.services.ai.prompt_builder import build_chat_system_prompt
from backend.app.services.field_rules import (
    ensure_rules_allowed,
    ensure_valid_field_rules,
    new_or_changed_rules,
)
from backend.app.services.form_spec.checks import check_spec_document
from backend.app.services.form_writes import persist_form
from tests.app.controllers.data import testUser
from tests.app.services.test_field_rules import (
    RULED,
    _form,
    _is,
    _q,
    _rule,
    form_to_spec_dict,
    rules_off,
    rules_on,
)

assert rules_on and rules_off  # fixtures, imported for this module

REQUIRE_B = _rule("r1", {"required": True}, [_is("a", "x")])


def _set(field_id, rules):
    return parse_ops([{"op": "set_field_rules", "fieldId": field_id, "rules": rules}])


def _spec_rule(rule_id="r1", source="a"):
    return {
        "id": rule_id,
        "when": {
            "conditions": [{"fieldId": source, "comparison": "IS_EQUAL", "value": "x"}]
        },
        "then": {"required": True},
    }


def _rules_of(form, field_id):
    for page in form.fields:
        for field in page.properties.fields:
            if field.id == field_id:
                return field.properties.rules if field.properties else None


# --- a question that cannot have rules loses them in a builder save ---------------


def test_an_internal_question_loses_its_rules_in_a_builder_save_instead_of_refusing_it():
    internal = _q(
        "b", rules=[REQUIRE_B, _rule("r2", {"readOnly": True}, [_is("a", "y")])]
    )
    internal["internal"] = True
    form = _form(
        [
            _q("a"),
            internal,
            _q("c", rules=[_rule("r3", {"required": True}, [_is("a", "z")])]),
        ]
    )
    dropped = ensure_valid_field_rules(form, drop=True)
    assert [(d["fieldId"], d["ruleId"]) for d in dropped] == [("b", "r1"), ("b", "r2")]
    assert "internal" in dropped[0]["message"]
    assert _rules_of(form, "b") is None
    # the other question keeps its rule, and the next save is clean
    assert [r.id for r in _rules_of(form, "c")] == ["r3"]
    assert ensure_valid_field_rules(form, drop=True) == []


def test_without_the_drop_an_internal_question_with_rules_is_still_refused():
    internal = _q("b", rules=[REQUIRE_B])
    internal["internal"] = True
    with pytest.raises(HTTPException) as error:
        ensure_valid_field_rules(_form([_q("a"), internal]))
    assert error.value.content["code"] == "invalid_field_rules"


def test_a_question_type_without_rules_loses_every_rule_in_a_builder_save():
    upload = _q(
        "b",
        "file_upload",
        rules=[REQUIRE_B, _rule("r2", {"required": False}, [_is("a", "y")])],
    )
    form = _form([_q("a"), upload])
    dropped = ensure_valid_field_rules(form, drop=True)
    assert [d["ruleId"] for d in dropped] == ["r1", "r2"]
    assert _rules_of(form, "b") is None


def test_rules_on_a_page_are_dropped_in_a_builder_save():
    form = _form([_q("a")])
    form.fields[0].properties.rules = [_rule_model(REQUIRE_B)]
    dropped = ensure_valid_field_rules(form, drop=True)
    assert [(d["fieldId"], d["ruleId"]) for d in dropped] == [("p0", "r1")]
    assert form.fields[0].properties.rules is None


def _rule_model(rule):
    from common.models.standard_form import FieldRule

    return FieldRule.model_validate(rule)


def test_a_circle_is_still_refused_not_dropped():
    from backend.app.services.field_rules import field_rule_problems

    a = _q(
        "a",
        "number",
        rules=[
            _rule(
                "r1",
                {"setValue": {"expression": {"+": [{"var": "b"}, 1]}}},
                expression=True,
            )
        ],
    )
    b = _q(
        "b",
        "number",
        rules=[
            _rule(
                "r2",
                {"setValue": {"expression": {"+": [{"var": "a"}, 1]}}},
                expression=True,
            )
        ],
    )
    form = _form([a, b])
    assert any("circle" in p.message for p in field_rule_problems(form))
    with pytest.raises(HTTPException) as error:
        ensure_valid_field_rules(form, drop=True)
    assert error.value.content["code"] == "invalid_field_rules"


async def test_the_builder_save_after_a_question_became_internal_goes_through(
    workspace, rules_on
):
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form(RULED), testUser)
    became_internal = _q("b", rules=[REQUIRE_B])
    became_internal["internal"] = True
    dropped = []
    # every autosave after the click used to be a 422
    for _ in range(2):
        dropped = []
        await service.update_form(
            workspace.id,
            form.form_id,
            _form([_q("a"), became_internal]),
            testUser,
            dropped_rules=dropped,
        )
        assert [(d["fieldId"], d["ruleId"]) for d in dropped] == [("b", "r1")]
        became_internal = _q("b", rules=[REQUIRE_B])
        became_internal["internal"] = True
    saved = await container.form_service().get_form_document_by_id(str(form.form_id))
    assert _rules_of(saved, "b") is None
    assert saved.fields[0].properties.fields[1].internal is True


async def test_the_same_save_goes_through_with_the_flag_off(workspace, monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
    service = container.workspace_form_service()
    form = await service.create_form(workspace.id, _form(RULED), testUser)
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", False)
    became_internal = _q("b", rules=[REQUIRE_B])
    became_internal["internal"] = True
    dropped = []
    await service.update_form(
        workspace.id,
        form.form_id,
        _form([_q("a"), became_internal]),
        testUser,
        dropped_rules=dropped,
    )
    assert [d["ruleId"] for d in dropped] == ["r1"]


# --- the op: an internal question ---------------------------------------------------


def test_the_op_that_makes_a_question_internal_removes_its_rules_and_says_so():
    form = _form(RULED)
    after, results = apply_form_ops(
        form,
        parse_ops(
            [{"op": "update_field", "fieldId": "b", "patch": {"internal": True}}]
        ),
    )
    assert results[0].ok, results[0].message
    assert "1 field rule(s)" in results[0].message
    assert _rules_of(after, "b") is None


def test_the_rules_that_read_a_question_made_internal_go_too():
    other = _q("c", rules=[_rule("r5", {"required": True}, [_is("a", "x")])])
    after, results = apply_form_ops(
        _form([_q("a"), _q("b"), other]),
        parse_ops(
            [{"op": "update_field", "fieldId": "a", "patch": {"internal": True}}]
        ),
    )
    assert results[0].ok, results[0].message
    assert _rules_of(after, "c") is None


# --- the flag compares rules by their content and their question --------------------


def test_a_rule_moved_to_another_question_under_a_reused_id_is_a_change():
    stored = _form([_q("a"), _q("b", rules=[REQUIRE_B]), _q("c")])
    assert new_or_changed_rules(stored, stored) == []
    # "b" is replaced by a question of another type that keeps the id and the rule
    other_type = _form([_q("a"), _q("b", "number", rules=[REQUIRE_B]), _q("c")])
    assert new_or_changed_rules(other_type, stored) == [("b", "r1")]
    # ... or one of the same type that sits on another page
    other_page = _form([_q("a"), _q("c")], [_q("b", rules=[REQUIRE_B])])
    assert new_or_changed_rules(other_page, stored) == [("b", "r1")]
    # the rule's own content counts too
    edited = _form(
        [
            _q("a"),
            _q("b", rules=[_rule("r1", {"required": True}, [_is("a", "y")])]),
            _q("c"),
        ]
    )
    assert new_or_changed_rules(edited, stored) == [("b", "r1")]
    # and another question's rule under the same rule id
    moved = _form([_q("a"), _q("b"), _q("c", rules=[REQUIRE_B])])
    assert new_or_changed_rules(moved, stored) == [("c", "r1")]


def test_two_questions_with_one_id_cannot_hide_a_copied_rule():
    stored = _form([_q("a"), _q("b", rules=[REQUIRE_B])])
    twice = _form([_q("a"), _q("b", rules=[REQUIRE_B]), _q("b", rules=[REQUIRE_B])])
    assert new_or_changed_rules(twice, stored) == [("b", "r1")]


def test_unchanged_rules_stay_unchanged_when_titles_and_neighbours_change():
    stored = _form([_q("a"), _q("b", rules=[REQUIRE_B])])
    edited_b = _q("b", rules=[REQUIRE_B])
    edited_b["title"] = "Another title"
    edited = _form([_q("c"), _q("a"), edited_b])
    assert new_or_changed_rules(edited, stored) == []


def test_ensure_rules_allowed_refuses_the_moved_rule_with_the_flag_off(rules_off):
    stored = _form([_q("a"), _q("b", rules=[REQUIRE_B])])
    ensure_rules_allowed(stored, stored)
    moved = _form([_q("a"), _q("b", "number", rules=[REQUIRE_B])])
    with pytest.raises(HTTPException) as error:
        ensure_rules_allowed(moved, stored)
    assert error.value.content["code"] == "field_rules_disabled"
    assert error.value.content["errors"] == [{"fieldId": "b", "ruleId": "r1"}]


def test_a_replace_field_op_is_compared_where_the_question_sits(rules_off):
    form = _form([_q("a")], [_q("b", rules=[REQUIRE_B])])
    same = {
        "id": "b",
        "type": "short_text",
        "title": "B",
        "properties": {"rules": [REQUIRE_B]},
    }
    _, results = apply_form_ops(
        form,
        parse_ops([{"op": "replace_field", "field": same}], allow_editor_ops=True),
    )
    assert results[0].ok, results[0].message
    retyped = {**same, "type": "number"}
    _, results = apply_form_ops(
        form,
        parse_ops([{"op": "replace_field", "field": retyped}], allow_editor_ops=True),
    )
    assert results[0].ok is False
    assert "FIELD_RULES_ENABLED" in results[0].message


# --- the op: the flag ------------------------------------------------------------------


def test_set_field_rules_follows_the_flag(rules_off):
    form = _form([_q("a"), _q("b")])
    after, results = apply_form_ops(form, _set("b", [_spec_rule()]))
    assert results[0].ok is False
    assert "FIELD_RULES_ENABLED" in results[0].message
    assert _rules_of(after, "b") is None


def test_set_field_rules_keeps_and_clears_stored_rules_with_the_flag_off(rules_off):
    form = _form(RULED)
    # the rules the question already has: nothing new
    same = [
        {
            "id": "r1",
            "when": {
                "conditions": [{"fieldId": "a", "comparison": "IS_EQUAL", "value": "x"}]
            },
            "then": {"required": True},
        }
    ]
    _, results = apply_form_ops(form, _set("b", same))
    assert results[0].ok, results[0].message
    # a changed one is refused, and so is a second rule
    changed = [{**same[0], "then": {"required": False}}]
    _, results = apply_form_ops(form, _set("b", changed))
    assert results[0].ok is False
    _, results = apply_form_ops(form, _set("b", same + [_spec_rule("r2")]))
    assert results[0].ok is False
    # clearing is always allowed
    after, results = apply_form_ops(form, _set("b", None))
    assert results[0].ok, results[0].message
    assert _rules_of(after, "b") is None


def test_set_field_rules_on_a_moved_question_is_not_a_rule_of_the_stored_one(rules_off):
    # the same rules, but on another question: a new rule while the flag is off
    form = _form(RULED + [_q("c")])
    _, results = apply_form_ops(form, _set("c", [_spec_rule("r1")]))
    assert results[0].ok is False


def test_set_field_rules_sets_replaces_and_clears_with_the_flag_on(rules_on):
    form = _form([_q("a"), _q("b")])
    after, results = apply_form_ops(form, _set("b", [_spec_rule()]), atomic=True)
    assert results[0].ok, results[0].message
    rule = _rules_of(after, "b")[0]
    assert rule.id == "r1" and rule.then.required is True
    assert rule.when.conditions[0].field_id == "a"
    assert rule.when.conditions[0].field_type == "short_text"
    after, _ = apply_form_ops(after, _set("b", [_spec_rule("r2")]))
    assert [r.id for r in _rules_of(after, "b")] == ["r2"]
    after, _ = apply_form_ops(after, _set("b", []))
    assert _rules_of(after, "b") is None


def test_set_field_rules_checks_like_a_save(rules_on):
    form = _form([_q("a"), _q("b", "number"), _q("c", "file_upload")])
    cases = [
        ("a", [_spec_rule("r1", "a")], "own answer"),
        ("c", [_spec_rule("r1", "a")], "cannot have rules"),
        ("b", [_spec_rule("r1", "gone")], "was not found"),
        (
            "b",
            [{**_spec_rule(), "then": {"setValue": {"const": "x"}}}],
            "does not fit",
        ),
    ]
    for field_id, rules, message in cases:
        _, results = apply_form_ops(form, _set(field_id, rules))
        assert results[0].ok is False, message
        assert message in results[0].message, results[0].message


def test_set_field_rules_resolves_refs_and_stays_in_a_group_scope(rules_on):
    ops = parse_ops(
        [
            {
                "op": "add_field",
                "pageId": "p0",
                "ref": "n",
                "field": {"title": "N", "type": "number"},
            },
            {
                "op": "set_field_rules",
                "fieldId": "b",
                "rules": [
                    {
                        "id": "r1",
                        "when": {"expression": {">": [{"var": "$ref:n"}, 3]}},
                        "then": {"required": True},
                    }
                ],
            },
        ]
    )
    after, results = apply_form_ops(_form([_q("a"), _q("b")]), ops, atomic=True)
    assert all(r.ok for r in results), [r.message for r in results]
    created = after.fields[0].properties.fields[2].id
    assert _rules_of(after, "b")[0].when.expression == {">": [{"var": created}, 3]}


# --- bounds: counted before anything is parsed ---------------------------------------


def test_too_many_rules_in_an_ops_payload_are_refused_before_each_is_read():
    junk = {"id": "!", "when": 7, "then": []}  # would fail rule by rule
    ops = [
        {"op": "set_field_rules", "fieldId": f"q{i}", "rules": [junk] * 8}
        for i in range(FORM_FIELD_RULES_MAX // 8 + 1)
    ]
    with pytest.raises(ValidationError) as error:
        parse_ops(ops)
    messages = [e["msg"] for e in error.value.errors()]
    assert len(messages) == 1 and "at most 100 rules" in messages[0]
    # whole questions and pages the editor sends count too
    page = {
        "id": "p",
        "type": "slide",
        "properties": {
            "fields": [
                {
                    "id": f"x{i}",
                    "type": "short_text",
                    "properties": {"rules": [junk] * 8},
                }
                for i in range(14)
            ]
        },
    }
    with pytest.raises(ValidationError) as error:
        parse_ops(
            [{"op": "insert_page", "index": 0, "page": page}], allow_editor_ops=True
        )
    assert "at most 100 rules" in error.value.errors()[0]["msg"]


def test_one_question_takes_at_most_eight_rules_in_the_op():
    rules = [_spec_rule(f"r{i}") for i in range(9)]
    with pytest.raises(ValidationError):
        _set("b", rules)


# --- persist_form is the last gate ----------------------------------------------------


async def _stored_form(workspace, fields):
    form = await container.workspace_form_service().create_form(
        workspace.id, _form(fields), testUser
    )
    return await container.form_repo().get_form_document_by_id(str(form.form_id))


async def test_persist_form_refuses_new_rules_with_the_flag_off(workspace, monkeypatch):
    from backend.config import settings

    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", False)
    document = await _stored_form(workspace, [_q("a"), _q("b")])
    repo = container.form_repo()
    ruled = _form(RULED)
    with pytest.raises(HTTPException) as error:
        await persist_form(repo, document, ruled)
    assert error.value.content["code"] == "field_rules_disabled"
    stored = await repo.get_form_document_by_id(document.form_id)
    assert _rules_of(stored, "b") is None
    # the conditional write is gated too
    with pytest.raises(HTTPException):
        await persist_form(repo, document, ruled, expected_updated_at=stored.updated_at)
    # a part that is not the questions is not gated
    assert await persist_form(repo, document, ruled, parts=("title",))
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
    assert await persist_form(repo, document, ruled)
    stored = await repo.get_form_document_by_id(document.form_id)
    assert [r.id for r in _rules_of(stored, "b")] == ["r1"]
    # stored rules pass unchanged with the flag off again
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", False)
    assert await persist_form(repo, stored, _form(RULED + [_q("c")]))


# --- the spec check and the AI text follow the flag ---------------------------------


def test_the_spec_check_warns_about_rules_while_they_are_off(rules_off):
    document = form_to_spec_dict(_form(RULED))
    # the stored form's own rules are not written by this call: still a warning
    result = check_spec_document(document)
    assert result["valid"] is True, result["errors"]
    warnings = [w for w in result["warnings"] if w["path"].endswith("/rules")]
    assert len(warnings) == 1
    assert warnings[0]["path"] == "/pages/0/fields/1/rules"
    assert "switched off" in warnings[0]["message"]


def test_the_spec_check_has_no_warning_while_they_are_on(rules_on):
    result = check_spec_document(form_to_spec_dict(_form(RULED)))
    assert result["valid"] is True
    assert not [w for w in result["warnings"] if w["path"].endswith("/rules")]


def test_the_chat_prompt_teaches_the_op_only_while_it_works(rules_off, monkeypatch):
    from backend.config import settings

    assert "set_field_rules" not in build_chat_system_prompt("{}", None)
    monkeypatch.setattr(settings, "FIELD_RULES_ENABLED", True)
    prompt = build_chat_system_prompt("{}", None)
    assert '"op":"set_field_rules"' in prompt
    assert "set_field_logic" in prompt


# --- checking only the question an op changed ----------------------------------------


def test_the_check_of_one_question_skips_the_others_but_keeps_what_spans_the_form():
    from backend.app.services.field_rules import field_rule_problems

    broken = lambda rule_id: _rule(  # noqa: E731
        rule_id, {"required": True}, [_is("gone", "x")]
    )
    form = _form(
        [_q("a"), _q("b", rules=[broken("r1")]), _q("c", rules=[broken("r2")])]
    )
    assert {p.field_id for p in field_rule_problems(form)} == {"b", "c"}
    assert {p.field_id for p in field_rule_problems(form, only={"b"})} == {"b"}
    # a rule id used on two questions is still found when only one is checked
    twice = _form([_q("a"), _q("b", rules=[REQUIRE_B]), _q("c", rules=[REQUIRE_B])])
    assert any(
        "more than once" in p.message for p in field_rule_problems(twice, only={"b"})
    )


def test_set_field_rules_is_not_refused_for_a_problem_another_question_had(rules_on):
    stored_broken = _q("c", rules=[_rule("r9", {"required": True}, [_is("gone", "x")])])
    form = _form([_q("a"), _q("b"), stored_broken])
    after, results = apply_form_ops(form, _set("b", [_spec_rule()]))
    assert results[0].ok, results[0].message
