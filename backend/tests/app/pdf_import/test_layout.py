"""Layout primitives on a generated form containing one of each element."""

import io

import pdfplumber
import pytest

from backend.app.services.pdf_import.layout import extract_layout, page_layout
from tests.app.pdf_import import documents


@pytest.fixture(scope="module")
def layout():
    with pdfplumber.open(io.BytesIO(documents.form_pdf())) as pdf:
        page = pdf.pages[0]
        from backend.app.services.pdf_import.text_layer import page_words

        words = page_words(page)["words"]
        return page_layout(page, words), words


def of(layout, kind):
    return [p for p in layout[0]["primitives"] if p["kind"] == kind]


def text(layout, primitive):
    words = layout[1]
    return " ".join(words[i]["text"] for i in primitive["words"])


def test_section_bars_carry_their_headings(layout):
    assert [b["title"] for b in of(layout, "section_bar")] == [
        "Personal details",
        "For office use only",
    ]


def test_answer_boxes_underlines_and_leader_dots(layout):
    slots = of(layout, "answer_slot")
    assert sorted(s["slot"] for s in slots) == ["box", "box", "dots", "underline"]


def test_character_and_date_cells(layout):
    runs = {r["cell_kind"]: r for r in of(layout, "cell_run")}
    assert (
        runs["characters"]["cells"] == 10 and runs["characters"]["placeholder"] is None
    )
    assert runs["date"]["cells"] == 3 and runs["date"]["placeholder"] == "DD MM YYYY"
    # the cells themselves are not reported again as checkboxes or slots
    assert len(of(layout, "checkbox")) == 4


def test_checkboxes_from_squares_and_parentheses(layout):
    sources = sorted(c["source"] for c in of(layout, "checkbox"))
    assert sources == ["box", "box", "parens", "parens"]


def test_data_table_with_header_and_empty_rows(layout):
    [table] = of(layout, "table")
    assert (table["rows"], table["cols"]) == (3, 3)
    assert table["header"] == ["Name", "Relation", "Account"]
    assert table["empty_cells"] == 4  # two empty rows, row labels excluded


def test_photo_signature_staff_region_and_paragraph(layout):
    [photo] = of(layout, "photo_box")
    assert "Photo" in text(layout, photo)
    [signature] = of(layout, "signature")
    dots = next(s for s in of(layout, "answer_slot") if s["slot"] == "dots")
    assert signature["slot"] == dots["id"]
    [staff] = of(layout, "staff_region")
    assert staff["heading"] == "For office use only"
    assert "Reviewed" in text(layout, staff)
    [paragraph] = of(layout, "paragraph")
    assert paragraph["word_count"] >= 60


def test_primitives_reference_words_and_have_stable_ids(layout):
    ids = [p["id"] for p in layout[0]["primitives"]]
    assert len(ids) == len(set(ids)) and all(i.startswith("p1-") for i in ids)
    words = layout[1]
    for p in layout[0]["primitives"]:
        assert all(0 <= i < len(words) for i in p["words"])


def test_placeholders_are_recognised_by_colour_and_shape(layout):
    words = layout[1]
    placeholders = {words[i]["text"] for i in layout[0]["placeholder_words"]}
    assert {"DD", "MM", "YYYY"} <= placeholders and "Full" not in placeholders


def test_skipped_pages_have_no_primitives():
    result = extract_layout(documents.text_pdf(pages=2), skip_pages={1})
    assert result["pages"][0]["skipped"] and result["pages"][0]["primitives"] == []
    assert not result["pages"][1]["skipped"]
