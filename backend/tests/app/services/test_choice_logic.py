"""Conditions on choice questions (multiple choice, dropdown): answers hold
the chosen option's id, a condition names the option by its text (what the
builder and the AI operations store) or by its id. Show/hide, page jumps,
endings, group answers, date rules, the flow view's paths and the seeded
"Support triage" template. The shared cases in
docs/spec/answer-validation.cases.json cover the same with the webapp."""

import datetime as dt

from common.models.standard_form import StandardForm

from backend.app.models.dtos.response_dtos import StandardFormResponseCamelModel
from backend.app.services.answer_validation import (
    reached_ending_id,
    resolve_jump_target,
    submission_path,
    validate_answers,
)
from backend.app.services.date_rules import today_range, validate_date_rule_answers
from backend.app.services.repeating_groups import (
    drop_hidden_group_answers,
    evaluate_conditions,
    logic_sources,
    validate_group_answers,
)
from scripts.seed_flow_templates import support_triage

CHOICES = [
    {"id": "c-billing", "value": "Billing"},
    {"id": "c-tech", "value": "Technical issue"},
    {"id": "c-legacy", "label": "Legacy label"},
]


def _form(fields, endings=None, pages=None):
    return StandardForm(
        builder_version="v2",
        title="Choices",
        fields=pages
        or [
            {"id": "p1", "type": "slide", "index": 0, "properties": {"fields": fields}}
        ],
        thankyou_page=endings,
    )


def _answers(answers):
    """Answers as the submit endpoint parses them."""
    return StandardFormResponseCamelModel(answers=answers).answers


def _picked(choice_id, field_id="topic"):
    return {field_id: {"type": "choice", "choice": {"value": choice_id}}}


def _cond(value, comparison="IS_EQUAL", field_id="topic", field_type="dropdown"):
    return {
        "fieldId": field_id,
        "fieldType": field_type,
        "comparison": comparison,
        "value": value,
    }


TOPIC = {
    "id": "topic",
    "type": "dropdown",
    "title": "Topic",
    "properties": {"choices": CHOICES},
}
TAGS = {
    "id": "tags",
    "type": "multiple_choice",
    "title": "Tags",
    "properties": {
        "choices": CHOICES,
        "allowMultipleSelection": True,
        "allowOtherChoice": True,
    },
}
SOURCES = logic_sources(_form([TOPIC, TAGS]).fields)


def _holds(condition, answers, sources=SOURCES):
    return evaluate_conditions("AND", [condition], answers, sources)


def test_sources_are_the_page_and_group_questions():
    group = {
        "id": "g",
        "type": "group",
        "title": "G",
        "properties": {"repeat": {}, "fields": [TOPIC]},
    }
    form = _form([{"id": "q", "type": "short_text", "title": "Q"}, group])
    assert sorted(logic_sources(form.fields)) == ["g", "q", "topic"]
    assert logic_sources(None) == {}


def test_the_chosen_option_matches_by_text_id_or_label():
    assert _holds(_cond("Billing"), _picked("c-billing"))
    assert _holds(_cond("c-billing"), _picked("c-billing"))
    assert _holds(_cond("Legacy label"), _picked("c-legacy"))
    assert not _holds(_cond("Technical issue"), _picked("c-billing"))
    # exactly and case-sensitively, as other equality
    assert not _holds(_cond("billing"), _picked("c-billing"))


def test_is_not_holds_only_when_nothing_the_option_answers_to_is_equal():
    assert not _holds(_cond("Billing", "IS_NOT_EQUAL"), _picked("c-billing"))
    assert not _holds(_cond("c-billing", "IS_NOT_EQUAL"), _picked("c-billing"))
    assert _holds(_cond("Billing", "IS_NOT_EQUAL"), _picked("c-tech"))
    assert _holds(_cond("Billing", "IS_NOT_EQUAL"), {})


def test_empty_and_not_empty():
    assert _holds(_cond("", "IS_EMPTY"), {})
    assert not _holds(_cond("", "IS_EMPTY"), _picked("c-billing"))
    assert _holds(_cond("", "IS_NOT_EMPTY"), _picked("c-billing"))


def test_several_answers_check_membership_by_text_or_id():
    def many(values, other=None):
        choices = {"values": values, **({"other": other} if other else {})}
        return {"tags": {"type": "choices", "choices": choices}}

    tags = lambda value, comparison="CONTAINS": _cond(  # noqa: E731
        value, comparison, "tags", "multiple_choice"
    )
    assert _holds(tags("Technical issue"), many(["c-billing", "c-tech"]))
    assert _holds(tags("c-tech"), many(["c-tech"]))
    assert not _holds(tags("Technical"), many(["c-tech"]))
    assert _holds(tags("Billing", "DOES_NOT_CONTAIN"), many(["c-tech"]))
    assert not _holds(tags("Billing", "DOES_NOT_CONTAIN"), many(["c-billing"]))
    assert _holds(tags("", "IS_EMPTY"), many([]))
    # the text typed as "Other" is compared as it is
    assert _holds(tags("Partners"), many([], "Partners"))
    assert _holds(tags("", "IS_NOT_EMPTY"), many([], "Partners"))


def test_other_text_on_a_single_choice():
    other = {"topic": {"type": "choice", "choice": {"other": "Partners"}}}
    assert _holds(_cond("Partners"), other)
    assert _holds(_cond("", "IS_NOT_EMPTY"), other)


def test_without_the_form_only_option_ids_match():
    assert evaluate_conditions("AND", [_cond("c-billing")], _picked("c-billing"))
    assert not evaluate_conditions("AND", [_cond("Billing")], _picked("c-billing"))


def test_stored_answer_models_are_read_too():
    assert _holds(_cond("Billing"), _answers(_picked("c-billing")))


# ---------------------------------------------------------------------------
# Paths, endings, groups, date rules
# ---------------------------------------------------------------------------


def _jump_pages(target="p3", ending_id=None):
    jump = {"operator": "AND", "conditions": [_cond("Billing")], "target": target}
    if ending_id:
        jump["endingId"] = ending_id
    return [
        {
            "id": "p1",
            "type": "slide",
            "index": 0,
            "properties": {"fields": [TOPIC], "jumps": [jump]},
        },
        {
            "id": "p2",
            "type": "slide",
            "index": 1,
            "properties": {
                "fields": [{"id": "q2", "type": "short_text", "title": "Q2"}]
            },
        },
        {
            "id": "p3",
            "type": "slide",
            "index": 2,
            "properties": {
                "fields": [{"id": "q3", "type": "short_text", "title": "Q3"}]
            },
        },
    ]


def test_a_jump_on_an_option_text_decides_the_path():
    form = _form(None, pages=_jump_pages())
    assert resolve_jump_target(form.fields[0], _picked("c-billing"), SOURCES) == "p3"
    steps, ended, _ = submission_path(form, _answers(_picked("c-billing")))
    assert [page for page, _ in steps] == ["p1", "p3"] and ended
    steps, _, _ = submission_path(form, _answers(_picked("c-tech")))
    assert [page for page, _ in steps] == ["p1", "p2", "p3"]


def test_a_jump_on_an_option_text_chooses_the_ending():
    endings = [
        {"id": "thanks", "name": "Thanks", "title": "Thank you"},
        {"id": "billing", "name": "Billing", "title": "We will look at your bill"},
    ]
    form = _form(None, endings=endings, pages=_jump_pages("__SUBMIT__", "billing"))
    assert reached_ending_id(form, _answers(_picked("c-billing"))) == "billing"
    assert reached_ending_id(form, _answers(_picked("c-tech"))) == "thanks"


def _group(logic=None):
    group = {
        "id": "g",
        "type": "group",
        "title": "People",
        "properties": {
            "repeat": {"minItems": 1, "maxItems": 3, "itemLabel": "Person"},
            "fields": [
                {
                    "id": "role",
                    "type": "dropdown",
                    "title": "Role",
                    "properties": {
                        "choices": [
                            {"id": "r-guest", "value": "Guest"},
                            {"id": "r-host", "value": "Host"},
                        ]
                    },
                },
                {
                    "id": "phone",
                    "type": "short_text",
                    "title": "Phone",
                    "validations": {"required": True},
                    "properties": {
                        "logic": {
                            "action": "SHOW",
                            "operator": "AND",
                            "conditions": [_cond("Host", field_id="role")],
                        }
                    },
                },
            ],
        },
    }
    if logic:
        group["properties"]["logic"] = logic
    return group


def test_group_items_and_hidden_groups_follow_option_texts():
    role = lambda choice_id: {
        "role": {"type": "choice", "choice": {"value": choice_id}}
    }  # noqa: E731
    items = {"type": "group", "items": [role("r-guest"), role("r-host")]}
    form = _form([_group()])
    assert validate_group_answers(form, _answers({"g": items})) == [
        "Person 2: 'Phone' is required."
    ]
    logic = {"action": "SHOW", "operator": "AND", "conditions": [_cond("Billing")]}
    form = _form([TOPIC, _group(logic)])
    hidden = _answers({**_picked("c-tech"), "g": items})
    assert "g" not in drop_hidden_group_answers(form, hidden)
    assert validate_group_answers(form, hidden) == []
    shown = _answers({**_picked("c-billing"), "g": items})
    assert "g" in drop_hidden_group_answers(form, shown)


def test_a_date_rule_skips_a_date_hidden_by_an_option_text():
    start = {
        "id": "start",
        "type": "date",
        "title": "Start date",
        "properties": {
            "logic": {
                "action": "SHOW",
                "operator": "AND",
                "conditions": [_cond("Billing")],
            }
        },
    }
    end = {
        "id": "end",
        "type": "date",
        "title": "End date",
        "properties": {
            "dateRules": [
                {"comparison": "after", "target": "field", "fieldId": "start"}
            ]
        },
    }
    form = _form([TOPIC, start, end])
    dates = {
        "start": {"type": "date", "date": "2026-03-12"},
        "end": {"type": "date", "date": "2026-03-01"},
    }
    today = today_range(dt.date(2026, 3, 12))
    assert (
        validate_date_rule_answers(form, {**_picked("c-tech"), **dates}, today=today)
        == []
    )
    assert validate_date_rule_answers(
        form, {**_picked("c-billing"), **dates}, today=today
    ) == ["'End date' must be after 'Start date' (12 Mar 2026)."]


# ---------------------------------------------------------------------------
# The seeded "Support triage" template
# ---------------------------------------------------------------------------


def test_the_support_triage_template_routes_each_topic():
    payload = support_triage()
    form = StandardForm(
        builder_version="v2", title=payload["title"], fields=payload["fields"]
    )
    intro, billing, technical, contact = (str(page.id) for page in form.fields)
    topic = form.fields[0].properties.fields[0]
    by_text = {choice.value: choice.id for choice in topic.properties.choices}

    def route(label):
        steps, ended, _ = submission_path(
            form, _answers(_picked(by_text[label], topic.id))
        )
        assert ended
        return [page for page, _ in steps]

    assert route("Billing") == [intro, billing, contact]
    assert route("Technical issue") == [intro, technical, contact]
    assert route("Something else") == [intro, contact]
    # Only the reply address is required on the "Something else" route.
    reply = form.fields[3].properties.fields[0]
    problems = validate_answers(
        form, _answers(_picked(by_text["Something else"], topic.id))
    )
    assert [(p.field_id, p.rule) for p in problems] == [(str(reply.id), "required")]
