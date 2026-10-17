"""Calculated fields in action payloads: shown with their format, and kept
out of the respondent's own copy when they are hidden from respondents."""

import pytest

from utilities.form import format_calculated_value, get_questions_and_answers


def _form():
    return {
        "fields": [
            {
                "id": "page-1",
                "type": "slide",
                "properties": {
                    "fields": [
                        {"id": "qty", "type": "number", "title": "Quantity"},
                        {
                            "id": "total",
                            "type": "calculated",
                            "title": "Total",
                            "properties": {"format": {"style": "currency", "decimals": 2}},
                        },
                        {
                            "id": "risk",
                            "type": "calculated",
                            "title": "Risk score",
                            "properties": {"hiddenFromRespondents": True},
                        },
                    ]
                },
            }
        ]
    }


RESPONSE = {
    "answers": {
        "qty": {"type": "number", "number": 3},
        "total": {"type": "number", "number": 1234.5},
        "risk": {"type": "number", "number": 7},
    }
}


def test_creator_payloads_show_every_calculation_formatted():
    answers = {e["field_id"]: e["answer"] for e in get_questions_and_answers(_form(), RESPONSE)}
    assert answers == {"qty": 3, "total": "€1,234.50", "risk": "7"}


def test_the_respondent_copy_leaves_out_hidden_calculations():
    entries = get_questions_and_answers(_form(), RESPONSE, respondent=True)
    assert [e["field_id"] for e in entries] == ["qty", "total"]


@pytest.mark.parametrize(
    "answer, fmt, expected",
    [
        ({"number": 0.256}, {"style": "percent"}, "26%"),
        ({"number": 0.256}, {"style": "percent", "decimals": 1}, "25.6%"),
        ({"number": -2.5}, {"style": "currency"}, "-€2.50"),
        ({"number": 12}, {"style": "currency", "currency": "USD"}, "USD 12.00"),
        ({"number": 1234.5678}, {"style": "number", "decimals": 2}, "1,234.57"),
        ({"number": 1234.5}, None, "1,234.5"),
        ({"number": 12}, {"style": "text"}, "12"),
        ({"boolean": True}, None, "Yes"),
        ({"text": "adult"}, {"style": "currency"}, "adult"),
        ({"type": "text"}, None, ""),
    ],
)
def test_formats(answer, fmt, expected):
    assert format_calculated_value(answer, fmt) == expected
