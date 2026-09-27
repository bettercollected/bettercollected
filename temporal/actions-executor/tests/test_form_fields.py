"""Internal ("for office use only") fields never reach action payloads — the
respondent's email copy, webhooks, Slack and Discord all read this list."""

from utilities.form import get_fields_from_v2_form, get_questions_and_answers


def _form():
    return {
        "fields": [
            {
                "id": "page-1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {"id": "name", "type": "short_text", "title": "Your name"},
                        {
                            "id": "risk",
                            "type": "short_text",
                            "title": "Risk rating",
                            "internal": True,
                        },
                        {
                            "id": "verdict",
                            "type": "multiple_choice",
                            "title": "Reviewer verdict",
                            "internal": True,
                            "properties": {"choices": [{"id": "c1", "value": "Ok"}]},
                        },
                    ]
                },
            }
        ]
    }


def test_internal_fields_are_not_listed():
    assert [f["id"] for f in get_fields_from_v2_form(_form())] == ["name"]


def test_questions_and_answers_have_no_internal_titles():
    response = {"answers": {"name": {"text": "Ada"}, "risk": {"text": "high"}}}
    rows = get_questions_and_answers(_form(), response)
    assert rows == [{"field_id": "name", "title": "Your name", "answer": "Ada"}]
    assert "Risk rating" not in str(rows)
    assert "Reviewer verdict" not in str(rows)
