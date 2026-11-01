"""An address answer in the export: one cell, one line (street, number and
addition, then postcode and city, and the country code unless it is NL), the
same in every language and in a repeating group's items; the cell goes through
the formula guard like any text."""

import pytest

from backend.app.services.response_export.table import answer_value, build_plan

FIELD = {"id": "home", "index": 0, "type": "address", "title": "Home"}
FORM = {
    "form_id": "addr",
    "builder_version": "v2",
    "title": "Addresses",
    "fields": [{"id": "p1", "index": 0, "type": "slide", "properties": {"fields": [FIELD]}}],
}


def _answer(**parts):
    return {"home": {"type": "address", "address": parts}}


def test_one_cell_one_line():
    answers = _answer(street="Keizersgracht", house_number="12", house_number_addition="A", postcode="1015 CS", city="Amsterdam", country="NL")
    assert answer_value(answers, FIELD) == "Keizersgracht 12 A, 1015 CS Amsterdam"


def test_the_country_code_is_added_unless_it_is_nl():
    answers = _answer(street="Rue Neuve", house_number="5", postcode="1000", city="Bruxelles", country="BE")
    assert answer_value(answers, FIELD) == "Rue Neuve 5, 1000 Bruxelles, BE"


@pytest.mark.parametrize(
    "answers, line",
    [
        ({}, ""),
        ({"home": {}}, ""),
        ({"home": {"address": {}}}, ""),
        ({"home": {"address": {"country": "BE"}}}, ""),
        ({"home": {"address": "not an object"}}, ""),
        (_answer(postcode="1015 CS", city="Amsterdam"), "1015 CS Amsterdam"),
        (_answer(street="Keizersgracht", house_number="12"), "Keizersgracht 12"),
    ],
)
def test_parts_that_are_missing_are_left_out(answers, line):
    assert answer_value(answers, FIELD) == line


def test_a_plan_has_one_column_for_the_question():
    plan = build_plan(FORM)
    titles = [getattr(column, "title", None) or getattr(column, "header", None) for column in plan.columns]
    assert titles.count("Home") == 1


async def test_the_formula_guard_covers_the_cell():
    import io  # noqa: F401

    from backend.app.services.response_export.table import ExportResponse
    from backend.app.services.response_export.writer import BOM, RowCount, write_export

    response = ExportResponse(
        response_id="r1",
        responder="a@example.org",
        created_at=None,
        answers=_answer(street="=HYPERLINK(1)", house_number="1", postcode="1015 CS", city="Amsterdam", country="NL"),
        internal_answers={},
        hidden_fields={},
    )

    async def source():
        yield response

    out = b""
    async for piece in write_export(build_plan(FORM), "Addresses", source, RowCount()):
        out += piece
    lines = out.decode("utf-8").removeprefix(BOM).split("\r\n")
    assert lines[0].startswith("Responder ID,Home,")
    # the guard prefixes a quote; the comma makes the cell quoted
    assert lines[1].startswith('a@example.org,"\'=HYPERLINK(1) 1, 1015 CS Amsterdam"')
