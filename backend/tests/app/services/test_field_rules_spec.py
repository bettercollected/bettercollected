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
    field_rule_problems,
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


def test_moving_a_question_to_another_page_or_group_changes_no_rule():
    stored = _form([_q("a"), _q("b", rules=[REQUIRE_B]), _q("c")])
    # the same question (id, type, rules) on another page
    other_page = _form([_q("a"), _q("c")], [_q("b", rules=[REQUIRE_B])])
    assert new_or_changed_rules(other_page, stored) == []
    # ... or in a group
    group = {
        "id": "g",
        "type": "group",
        "title": "G",
        "properties": {
            "repeat": {"minItems": 1, "maxItems": 3},
            "fields": [_q("b", rules=[REQUIRE_B])],
        },
    }
    assert new_or_changed_rules(_form([_q("a"), group, _q("c")]), stored) == []
    # a moved question that is edited is still a change, and so is another type
    edited = _q("b", rules=[_rule("r1", {"required": True}, [_is("a", "y")])])
    assert new_or_changed_rules(_form([_q("a"), _q("c")], [edited]), stored) == [
        ("b", "r1")
    ]
    other_type = _form([_q("a"), _q("c")], [_q("b", "number", rules=[REQUIRE_B])])
    assert new_or_changed_rules(other_type, stored) == [("b", "r1")]


def test_a_save_that_moves_a_ruled_question_passes_with_the_flag_off(rules_off):
    stored = _form([_q("a"), _q("b", rules=[REQUIRE_B]), _q("c")])
    moved = _form([_q("a"), _q("c")], [_q("b", rules=[REQUIRE_B])])
    ensure_rules_allowed(moved, stored)  # no 422
    # a new rule on the moved question is still refused
    changed = _form(
        [_q("a"), _q("c")],
        [_q("b", rules=[REQUIRE_B, _rule("r2", {"required": False}, [_is("a", "y")])])],
    )
    with pytest.raises(HTTPException) as error:
        ensure_rules_allowed(changed, stored)
    assert error.value.content["code"] == "field_rules_disabled"


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


# --- review fixes: dropped rules are noted, deep expressions, per-op cost ------------

SETS_COUNTRY = _rule("r1", {"setValue": {"const": "nl"}}, [_is("a", "x")])


def _choice_question(rules=None):
    return {
        "id": "c",
        "type": "dropdown",
        "title": "C",
        "properties": {
            "choices": [
                {"id": "nl", "value": "Netherlands"},
                {"id": "be", "value": "Belgium"},
            ],
            **({"rules": rules} if rules else {}),
        },
    }


def test_replacing_the_options_says_which_rules_went_with_them():
    form = _form([_q("a"), _choice_question([SETS_COUNTRY])])
    patch = {"choices": ["Belgium", "France"]}
    after, results = apply_form_ops(
        form,
        parse_ops([{"op": "update_field", "fieldId": "c", "patch": patch}]),
    )
    assert results[0].ok, results[0].message
    assert "1 field rule(s)" in results[0].message
    assert _rules_of(after, "c") is None
    # an option edit that keeps the option the rule sets says nothing
    keep = {"choices": ["Netherlands", "France"]}
    _, results = apply_form_ops(
        form,
        parse_ops([{"op": "update_field", "fieldId": "c", "patch": keep}]),
    )
    assert "field rule" not in results[0].message


def test_removing_an_option_says_which_rules_went_with_it():
    form = _form([_q("a"), _choice_question([SETS_COUNTRY])])
    after, results = apply_form_ops(
        form,
        parse_ops(
            [{"op": "remove_choice", "fieldId": "c", "choiceId": "nl"}],
            allow_editor_ops=True,
        ),
    )
    assert results[0].ok, results[0].message
    assert "1 field rule(s)" in results[0].message
    assert _rules_of(after, "c") is None


def _nested(depth, leaf=None):
    node = leaf or {"var": "a"}
    for _ in range(depth):
        node = {"+": [node, 1]}
    return node


@pytest.mark.parametrize("depth", [33, 250, 1000, 5000])
def test_an_expression_nested_too_deep_is_refused_cleanly(rules_on, depth):
    """Not a RecursionError (a 500): a refusal, from the parse for a rule and
    from the walks for anything else."""
    rule = {
        "id": "r1",
        "when": {"expression": _nested(depth)},
        "then": {"required": True},
    }
    with pytest.raises(ValidationError) as error:
        _set("b", [rule])
    assert "nested at most 32 levels" in str(error.value)
    # a value formula is checked the same way
    value_rule = {
        "id": "r1",
        "when": {"conditions": [_spec_rule()["when"]["conditions"][0]]},
        "then": {"setValue": {"expression": _nested(depth)}},
    }
    with pytest.raises(ValidationError):
        _set("b", [value_rule])


def test_an_expression_at_the_depth_limit_is_checked_by_the_rule_check(rules_on):
    form = _form([_q("a", "number"), _q("b")])
    ok = {"id": "r1", "when": {"expression": _nested(30)}, "then": {"required": True}}
    after, results = apply_form_ops(form, _set("b", [ok]))
    assert results[0].ok, results[0].message
    too_deep = {
        "id": "r1",
        "when": {"expression": _nested(32)},
        "then": {"required": True},
    }
    _, results = apply_form_ops(form, _set("b", [too_deep]))
    assert results[0].ok is False
    assert "32 levels" in results[0].message


@pytest.mark.parametrize("depth", [250, 5000])
def test_the_ref_walks_survive_any_depth(depth):
    from backend.app.services.ai.ops import ref_dependencies

    form = _form([_q("a", "number")])
    op = {
        "op": "add_field",
        "pageId": "p0",
        "field": {"type": "calculated", "title": "c", "expression": _nested(depth)},
    }
    ops = parse_ops([op])
    assert ref_dependencies(ops) == [set()]
    _, results = apply_form_ops(form, ops)
    assert results[0].ok is False
    assert "not valid" in results[0].message
    # refs are still resolved, wherever they sit
    batch = parse_ops(
        [
            {
                "op": "add_field",
                "pageId": "p0",
                "ref": "n",
                "field": {"type": "number", "title": "N"},
            },
            {"op": "update_field", "fieldId": "$ref:n", "patch": {"title": "M"}},
        ]
    )
    assert ref_dependencies(batch) == [set(), {0}]
    after, results = apply_form_ops(form, batch)
    assert [r.ok for r in results] == [True, True], results


def test_a_rule_op_does_not_copy_the_form_for_its_expressions(rules_on):
    from backend.app.services.ai.ops import _carries_calculation

    (op,) = _set(
        "b",
        [
            {
                "id": "r1",
                "when": {"expression": {"var": "a"}},
                "then": {"required": True},
            }
        ],
    )
    assert _carries_calculation(op) is False
    # a calculated field still is
    (calc,) = parse_ops(
        [
            {
                "op": "add_field",
                "pageId": "p0",
                "field": {
                    "type": "calculated",
                    "title": "c",
                    "expression": {"var": "a"},
                },
            }
        ]
    )
    assert _carries_calculation(calc) is True


def test_an_op_works_out_the_cost_of_the_other_questions_once(rules_on, monkeypatch):
    from backend.app.services import field_rules
    from backend.app.services.ai.ops import _apply_set_field_rules

    others = [
        _q(f"q{i}", rules=[_rule(f"rq{i}", {"required": True}, [_is("a", "x")])])
        for i in range(10)
    ]
    form = _form([_q("a"), _q("b"), *others])
    calls = []
    real = field_rules._question_cost
    monkeypatch.setattr(
        field_rules,
        "_question_cost",
        lambda target, maxima: calls.append(target.id) or real(target, maxima),
    )
    # the op itself (apply_form_ops also prunes the finished form, which
    # checks every rule again)
    message = _apply_set_field_rules(form, _set("b", [_spec_rule()])[0])
    assert message.startswith("Set 1 rule(s)")
    # the first run costs the ten questions that have rules; the second only
    # the one whose rules were replaced
    assert sorted(calls) == sorted([f"q{i}" for i in range(10)] + ["b"])


def _circle_form():
    to = lambda target: _rule(  # noqa: E731
        f"r-{target}",
        {"setValue": {"expression": {"+": [{"var": target}, 1]}}},
        expression=True,
    )
    return _form(
        [
            _q("a"),
            _q("s1", "number", rules=[to("s2")]),
            _q("s2", "number", rules=[to("s1")]),
            _q("q"),
        ]
    )


def test_a_problem_the_form_already_had_does_not_stop_an_unrelated_rule(rules_on):
    """The baseline: a circle that was stored before (data no save would
    accept) is not this op's doing, so a valid rule elsewhere still applies;
    a new problem still does not."""
    form = _circle_form()
    assert any("circle" in p.message for p in field_rule_problems(form))
    after, results = apply_form_ops(form, _set("q", [_spec_rule()]))
    assert results[0].ok, results[0].message
    assert _rules_of(after, "q") is not None
    # the same op with a new problem of its own is refused, circle or not
    broken = _spec_rule()
    broken["when"]["conditions"][0]["fieldId"] = "gone"
    _, results = apply_form_ops(form, _set("q", [broken]))
    assert results[0].ok is False
    assert "'gone'" in results[0].message


def test_a_question_with_a_stored_problem_can_still_have_its_rules_replaced(rules_on):
    """The question's own earlier problem is the baseline: replacing its
    rules by ones that keep it is not blamed on the op, a new one is."""

    def reads(rule_id, key):
        return _rule(rule_id, {"required": True}, expression={"var": key})

    stored = _form([_q("a"), _q("b", rules=[reads("r1", "gone")]), _q("c")])
    assert field_rule_problems(stored)
    _, results = apply_form_ops(stored, _set("b", [reads("r2", "gone")]))
    # r2 reads the same missing variable as r1 did: the same problem, not new
    assert results[0].ok, results[0].message
    _, results = apply_form_ops(stored, _set("b", [reads("r3", "other")]))
    assert results[0].ok is False
    assert "'other'" in results[0].message
