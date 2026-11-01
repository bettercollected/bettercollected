"""Time, day, currency, date range and tags answers in action payloads (sheet rows, mails): the
same text as the CSV export: HH:MM, YYYY-MM-DD, "EUR 12.50", YYYY-MM-DD/YYYY-MM-DD, "a; b"."""

from utilities.form import get_answer_for_field


def _answer(field_type, answer):
    return get_answer_for_field({"answers": {"q": answer}}, {"id": "q", "type": field_type})


def test_a_time_is_hh_mm():
    assert _answer("time", {"type": "time", "time": "09:05"}) == "09:05"


def test_a_day_is_its_date():
    assert _answer("day", {"type": "date", "date": "1990-11-05"}) == "1990-11-05"


def test_a_currency_is_its_code_and_a_dot_decimal():
    assert _answer("currency", {"type": "currency", "currency": {"code": "GBP", "amount": "1250.50"}}) == "GBP 1250.50"


def test_unanswered_ones_are_empty():
    assert _answer("time", {}) is None
    assert _answer("currency", {}) == ""
    assert _answer("currency", {"currency": {"code": "EUR", "amount": ""}}) == ""


def test_a_date_range_is_an_iso_interval():
    answer = {"type": "date_range", "date_range": {"start": "2026-11-03", "end": "2026-11-07"}}
    assert _answer("date_range", answer) == "2026-11-03/2026-11-07"
    assert _answer("date_range", {}) == ""


def test_tags_are_one_cell_joined_with_semicolons():
    assert _answer("tags", {"type": "tags", "tags": ["red", "blue sky"]}) == "red; blue sky"
    assert _answer("tags", {"type": "tags", "tags": []}) == ""
    assert _answer("tags", {}) == ""


def test_an_address_is_one_line_with_the_country_unless_nl():
    answer = {
        "type": "address",
        "address": {"street": "Keizersgracht", "house_number": "12", "house_number_addition": "A", "postcode": "1015 CS", "city": "Amsterdam", "country": "NL"},
    }
    assert _answer("address", answer) == "Keizersgracht 12 A, 1015 CS Amsterdam"
    belgian = {"type": "address", "address": {"street": "Rue Neuve", "house_number": "5", "postcode": "1000", "city": "Bruxelles", "country": "BE"}}
    assert _answer("address", belgian) == "Rue Neuve 5, 1000 Bruxelles, BE"
    assert _answer("address", {}) == ""
