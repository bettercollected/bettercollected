"""Time, day and currency answers in action payloads (sheet rows, mails): the
same text as the CSV export: HH:MM, YYYY-MM-DD, "EUR 12.50"."""

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
