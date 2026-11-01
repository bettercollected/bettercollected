"""Everything that shows an answer to a sourced question shows the stored label,
never the id, and never a label a client could have forged for a static one."""

from backend.app.services.ai.insights import _answer_text
from backend.app.services.registration import body as registration
from backend.app.services.response_export import table

SOURCED = {
    "id": "who",
    "type": "dropdown",
    "title": "Who",
    "properties": {"option_source": {"kind": "list", "list_id": "x" * 24}},
}
SOURCED_MANY = {
    "id": "whom",
    "type": "multiple_choice",
    "title": "Whom",
    "properties": {
        "option_source": {"kind": "list", "list_id": "x" * 24},
        "allow_multiple_selection": True,
    },
}
STATIC = {
    "id": "plain",
    "type": "dropdown",
    "title": "Plain",
    "properties": {"choices": [{"id": "c1", "value": "Red"}]},
}
ONE = {"type": "choice", "choice": {"value": "li" + "1" * 22, "label": "Alice Example"}}
MANY = {
    "type": "choices",
    "choices": {
        "values": ["fa" + "1" * 22, "fa" + "2" * 22],
        "labels": {"fa" + "1" * 22: "Bob", "fa" + "2" * 22: "Carol"},
        "other": "Dave",
    },
}


def test_the_csv_export_writes_the_label_snapshot():
    assert table.answer_value({"who": ONE}, SOURCED) == "Alice Example"
    assert (
        table.answer_value(
            {"whom": MANY},
            {**SOURCED_MANY, "properties": {**SOURCED_MANY["properties"]}},
            "; ",
        )
        == "Bob; Carol; Dave"
    )
    # camelCase documents too
    camel = {
        "id": "who",
        "type": "dropdown",
        "properties": {"optionSource": {"kind": "list"}},
    }
    assert table.answer_value({"who": ONE}, camel) == "Alice Example"
    assert table.answer_value({}, SOURCED) == ""
    # an id is never written, and a label a client sent for a static question is not read
    assert "li1111" not in table.answer_value({"who": ONE}, SOURCED)
    forged = {"type": "choice", "choice": {"value": "c1", "label": "Forged"}}
    assert table.answer_value({"plain": forged}, STATIC) == "Red"


def test_the_email_webhook_and_registration_body_carry_labels_and_no_id():
    value, schema = registration.scalar(SOURCED, ONE)
    assert (
        value == "Alice Example" and schema["type"] == "string" and "enum" not in schema
    )
    value, schema = registration.scalar(SOURCED_MANY, MANY)
    assert (
        value == ["Bob", "Carol", "Dave"]
        and schema["type"] == "array"
        and "enum" not in schema["items"]
    )
    # as a set of booleans (a registration format) the list stays a list: there are no fixed options to name
    value, _ = registration.scalar(SOURCED_MANY, MANY, choices_as_list=False)
    assert value == ["Bob", "Carol", "Dave"]
    assert registration.scalar(SOURCED, None)[0] == ""
    assert registration.scalar(SOURCED_MANY, None)[0] == []
    assert registration.sourced_texts(
        {"choice": {"value": "li1", "other": "Else"}}
    ) == ["Else"]
    # a static question still reads its options
    assert registration.scalar(STATIC, {"choice": {"value": "c1"}})[0] == "Red"


def test_the_ai_insights_prompt_gets_a_lists_label_but_never_another_forms_answer():
    # a workspace list's label is reference data: sent
    assert _answer_text(ONE, {}, "list") == "Alice Example"
    # an option that is another form's answer is someone else's answer: never sent
    assert _answer_text(ONE, {}, "form_answers") == "[choice from another form]"
    assert _answer_text(MANY, {}, "form_answers") == "[choice from another form]"
    # a snapshot on a question this version does not know as a list: fail closed
    assert _answer_text(ONE, {}) == "[choice from another form]"
    assert _answer_text(MANY, {}) == "[choice from another form]"
    assert (
        _answer_text({"type": "choice", "choice": {"value": "c1"}}, {"c1": "Red"})
        == "Red"
    )


def test_a_projection_never_carries_another_forms_answers_to_the_model():
    from common.models.standard_form import StandardForm

    from backend.app.services.ai.insights import project_responses

    form = StandardForm(
        builder_version="v2",
        title="Consumer",
        fields=[
            {
                "id": "s1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {
                            "id": "fa_q",
                            "type": "dropdown",
                            "title": "Participant",
                            "properties": {
                                "option_source": {
                                    "kind": "form_answers",
                                    "form_id": "a" * 24,
                                    "question_id": "name",
                                }
                            },
                        },
                        {
                            "id": "ls_q",
                            "type": "dropdown",
                            "title": "City",
                            "properties": {
                                "option_source": {"kind": "list", "list_id": "b" * 24}
                            },
                        },
                    ]
                },
            }
        ],
    )

    class Row:
        form_id = "c" * 24
        answers = {
            "fa_q": {"type": "choice", "choice": {"value": "fa" + "1" * 22, "label": "Alice Secret"}},
            "ls_q": {"type": "choice", "choice": {"value": "li" + "1" * 22, "label": "Utrecht"}},
        }

    text, included = project_responses("d" * 24, form, [Row()])
    assert included == 1
    assert "Alice Secret" not in text
    assert "[choice from another form]" in text
    assert "Utrecht" in text
