"""One cell read back as an answer: the inverse of the export's cell text."""

import datetime as dt

import pytest

from backend.app.services.response_export import table
from backend.app.services.response_import.convert import (
    CellProblem,
    clean,
    convert_cell,
    parse_address,
    parse_submitted_at,
)

NOW = "2026-11-01T10:00:00+00:00"
CHOICES = [
    {"id": "c1", "value": "Red"},
    {"id": "c2", "value": "Green; dark"},
    {"id": "c3", "value": "Blue"},
    {"id": "c4", "value": ""},
]


def field(kind, **properties):
    return {"id": "q", "type": kind, "properties": properties}


def slot(kind, text, **properties):
    return convert_cell(field(kind, **properties), text, NOW)


def problem(kind, text, **properties):
    with pytest.raises(CellProblem) as caught:
        slot(kind, text, **properties)
    return caught.value.code


def test_an_empty_cell_is_no_answer():
    assert slot("short_text", "   ") is None
    assert slot("number", "") is None


def test_the_formula_guard_is_taken_off_once():
    assert clean("'=SUM(1)") == "=SUM(1)"
    assert clean("'+31 6 1234") == "+31 6 1234"
    assert clean("'  =x") == "=x"
    # an apostrophe the export would not have added is data
    assert clean("'tis") == "'tis"
    assert clean("''=x") == "''=x"
    assert clean("plain") == "plain"


def test_text_like_questions():
    assert slot("short_text", " Ada ")["text"] == "Ada"
    assert slot("long_text", "a\nb")["text"] == "a\nb"
    assert slot("email", "a@b.nl") == {"field": {"id": "q"}, "type": "email", "email": "a@b.nl"}
    assert slot("url", "https://x.nl")["url"] == "https://x.nl"
    assert slot("phone_number", "'+31 6 1234")["phone_number"] == "+31 6 1234"


@pytest.mark.parametrize(
    "text, value",
    [("30", 30), ("-4", -4), ("12.5", 12.5), ("12,5", 12.5), ("0", 0), ("7.0", 7)],
)
def test_numbers(text, value):
    answer = slot("number", text)
    assert answer["number"] == value and isinstance(answer["number"], type(value))


@pytest.mark.parametrize("text", ["1,234.5", "abc", "1e5", "--1", "1 2", "٣"])
def test_a_number_that_is_not_plain_is_refused(text):
    assert problem("number", text) == "invalid_number"


@pytest.mark.parametrize(
    "text, iso",
    [("2026-11-05", "2026-11-05"), ("05-11-2026", "2026-11-05"), ("5/11/2026", "2026-11-05"), ("05.11.2026", "2026-11-05")],
)
def test_dates(text, iso):
    assert slot("date", text)["date"] == iso
    assert slot("day", text)["date"] == iso


@pytest.mark.parametrize("text", ["2026-02-31", "2026-13-01", "11/05/26", "yesterday", "2026-11-05T10:00"])
def test_a_date_that_is_not_one_is_refused(text):
    assert problem("date", text) == "invalid_date"


def test_times():
    assert slot("time", "9:05")["time"] == "09:05"
    assert slot("time", "09:05:59")["time"] == "09:05"
    assert problem("time", "24:00") == "invalid_time"
    assert problem("time", "9am") == "invalid_time"


def test_currency():
    assert slot("currency", "EUR 12.50")["currency"] == {"code": "EUR", "amount": "12.50"}
    assert slot("currency", "gbp 3")["currency"] == {"code": "GBP", "amount": "3"}
    assert slot("currency", "EUR 12,50")["currency"] == {"code": "EUR", "amount": "12.50"}
    assert slot("currency", "-4.5", currencies=["EUR"])["currency"] == {"code": "EUR", "amount": "-4.5"}
    assert problem("currency", "12.50") == "currency_missing"
    assert problem("currency", "12.50", currencies=["EUR", "GBP"]) == "currency_missing"
    assert problem("currency", "EUR twelve") == "invalid_amount"


def test_date_range():
    assert slot("date_range", "2026-11-03/2026-11-07")["date_range"] == {"start": "2026-11-03", "end": "2026-11-07"}
    assert slot("date_range", "2026-11-03/")["date_range"] == {"start": "2026-11-03"}
    assert slot("date_range", "/2026-11-07")["date_range"] == {"end": "2026-11-07"}
    assert problem("date_range", "2026-11-03") == "invalid_date_range"
    assert problem("date_range", "2026-11-03/2026-02-31") == "invalid_date_range"
    assert problem("date_range", "a/b/c") == "invalid_date_range"


def test_tags():
    assert slot("tags", "vegan; gluten free")["tags"] == ["vegan", "gluten free"]
    assert slot("tags", ";;") is None or slot("tags", ";;")["tags"] == []


def test_yes_no():
    assert slot("yes_no", "Yes")["boolean"] is True
    assert slot("yes_no", "no")["boolean"] is False
    assert slot("yes_no", "Ja")["boolean"] is True
    assert problem("yes_no", "maybe") == "invalid_yes_no"


def test_a_single_choice_by_label_case_insensitively_or_id():
    assert slot("dropdown", "red", choices=CHOICES)["choice"] == {"value": "c1"}
    assert slot("multiple_choice", "  GREEN; DARK ", choices=CHOICES)["choice"] == {"value": "c2"}
    assert slot("dropdown", "c3", choices=CHOICES)["choice"] == {"value": "c3"}
    assert slot("dropdown", "Item 4", choices=CHOICES)["choice"] == {"value": "c4"}
    assert problem("dropdown", "Item 1", choices=CHOICES) == "unknown_option"
    assert problem("dropdown", "Purple", choices=CHOICES) == "unknown_option"


def test_a_choice_nobody_offered_is_other_only_when_the_question_allows_it():
    answer = slot("dropdown", "Purple", choices=CHOICES, allow_other_choice=True)
    assert answer["choice"] == {"other": "Purple"}


def test_several_choices_split_on_semicolons_but_a_label_may_hold_one():
    options = dict(choices=CHOICES, allow_multiple_selection=True)
    answer = slot("multiple_choice", "Red; Green; dark; Blue", **options)
    assert answer["type"] == "choices" and answer["choices"] == {"values": ["c1", "c2", "c3"]}
    assert slot("multiple_choice", "Blue; Blue", **options)["choices"] == {"values": ["c3"]}
    other = slot("multiple_choice", "Red; Something else", allow_other_choice=True, **options)
    assert other["choices"] == {"values": ["c1"], "other": "Something else"}
    assert problem("multiple_choice", "Red; Nope", **options) == "unknown_option"


def test_signature_typed_only():
    answer = slot("signature", "A. Lovelace")
    assert answer["signature"] == {"method": "typed", "name": "A. Lovelace", "signed_at": NOW}
    assert problem("signature", table_marker()) == "drawn_signature"


def table_marker():
    return "[drawn signature]"


def test_unsupported_types():
    assert problem("file_upload", "x.pdf") == "type_unsupported"
    assert problem("matrix_row_input", "x") == "type_unsupported"


@pytest.mark.parametrize(
    "line, parts",
    [
        (
            "Keizersgracht 12 A, 1015 CS Amsterdam",
            {"street": "Keizersgracht", "house_number": "12", "house_number_addition": "A", "postcode": "1015 CS", "city": "Amsterdam", "country": "NL"},
        ),
        (
            "Rue Neuve 5, 1000 Bruxelles, BE",
            {"street": "Rue Neuve", "house_number": "5", "postcode": "1000", "city": "Bruxelles", "country": "BE"},
        ),
        ("1015CS Amsterdam", {"postcode": "1015 CS", "city": "Amsterdam", "country": "NL"}),
        ("Keizersgracht 12", {"street": "Keizersgracht", "house_number": "12", "country": "NL"}),
        ("2e Hoofdstraat 7, 3511 AB Utrecht", {"street": "2e Hoofdstraat", "house_number": "7", "postcode": "3511 AB", "city": "Utrecht", "country": "NL"}),
    ],
)
def test_the_export_s_one_line_address_reads_back_into_parts(line, parts):
    assert parse_address(line) == parts


def test_an_address_is_the_inverse_of_what_the_export_writes():
    from common.address import one_line

    original = {"street": "Keizersgracht", "house_number": "12", "house_number_addition": "A", "postcode": "1015 CS", "city": "Amsterdam", "country": "NL"}
    assert parse_address(one_line(original)) == original


def test_an_address_that_does_not_fit_is_refused():
    with pytest.raises(CellProblem):
        parse_address("a, b, c, d, e")


NOW_DT = dt.datetime(2026, 11, 1, 10, 0, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize(
    "text, when",
    [
        ("2026-10-01T10:00:00Z", dt.datetime(2026, 10, 1, 10, 0, tzinfo=dt.timezone.utc)),
        ("2026-10-01T12:00:00+02:00", dt.datetime(2026, 10, 1, 10, 0, tzinfo=dt.timezone.utc)),
        ("2026-10-01 09:30", dt.datetime(2026, 10, 1, 9, 30, tzinfo=dt.timezone.utc)),
        ("2026-10-01", dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)),
        ("01-10-2026 09:30:15", dt.datetime(2026, 10, 1, 9, 30, 15, tzinfo=dt.timezone.utc)),
        ("1/10/2026", dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)),
    ],
)
def test_submission_times(text, when):
    assert parse_submitted_at(text, NOW_DT) == when


def test_a_blank_time_is_none_and_a_future_or_silly_one_is_refused():
    assert parse_submitted_at("", NOW_DT) is None
    for text in ("2027-01-01", "1985-01-01", "soon", "2026-13-40"):
        with pytest.raises(CellProblem):
            parse_submitted_at(text, NOW_DT)


def test_the_guard_pattern_is_the_exports():
    # the import takes off exactly what the export puts on
    for value in ("=1", "+1", "-a", "@a", "\tx", "\rx", "  =x"):
        assert table.formula_safe_cell(value) == f"'{value}"
        assert clean(table.formula_safe_cell(value)) == value.strip()
