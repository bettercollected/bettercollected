"""Reading an uploaded file: encodings, separators, quoting, caps, refusals."""

import pytest

from backend.app.services.response_import import limits
from backend.app.services.response_import.parser import CsvRefused, parse


def refused(data: bytes) -> str:
    with pytest.raises(CsvRefused) as caught:
        parse(data)
    return caught.value.code


def test_utf8_with_and_without_a_byte_order_mark():
    plain = parse("Name,Age\r\nÀda,30\r\n".encode("utf-8"))
    bom = parse("Name,Age\r\nÀda,30\r\n".encode("utf-8-sig"))
    assert plain.headers == bom.headers == ["Name", "Age"]
    assert plain.rows == bom.rows == [(2, ["Àda", "30"])]
    assert (plain.encoding, bom.encoding) == ("utf-8", "utf-8-bom")


def test_windows_1252_is_the_fallback():
    parsed = parse("Naam;Stad\r\nZoë;Genève\r\n".encode("cp1252"))
    assert parsed.encoding == "cp1252"
    assert parsed.rows[0][1] == ["Zoë", "Genève"]


def test_a_byte_cp1252_does_not_define_is_refused():
    assert refused(b"a,b\r\n\x81,\x8d\r\n") == "unreadable_encoding"


@pytest.mark.parametrize("separator", [",", ";"])
def test_the_separator_is_detected_from_the_header_line(separator):
    text = separator.join(["A", "B", "C"]) + "\r\n" + separator.join(["1", "2", "3"]) + "\r\n"
    parsed = parse(text.encode())
    assert parsed.separator == separator
    assert parsed.rows == [(2, ["1", "2", "3"])]


def test_a_separator_inside_quotes_does_not_count():
    parsed = parse(b'"a;b;c",d\r\n1,2\r\n')
    assert parsed.separator == ","
    assert parsed.headers == ["a;b;c", "d"]


def test_an_excel_sep_line_names_the_separator_and_is_not_data():
    parsed = parse(b"sep=;\r\nA;B\r\n1;2\r\n")
    assert (parsed.separator, parsed.headers, parsed.rows) == (";", ["A", "B"], [(2, ["1", "2"])])


def test_quoted_fields_hold_separators_quotes_and_line_breaks():
    parsed = parse(b'A,B\r\n"x, y","line one\r\nline two ""q"""\r\n')
    assert parsed.rows == [(2, ["x, y", 'line one\r\nline two "q"'])]


def test_blank_rows_are_skipped_and_the_row_numbers_stay():
    parsed = parse(b"A\r\n1\r\n\r\n3\r\n")
    assert [number for number, _ in parsed.rows] == [2, 4]


def test_short_rows_are_padded_and_extra_cells_are_flagged():
    parsed = parse(b"A,B\r\n1\r\n2,3,4\r\n")
    assert parsed.rows == [(2, ["1", ""]), (3, ["2", "3"])]
    assert parsed.ragged == {3}


def test_empty_cells_beyond_the_header_are_not_flagged():
    parsed = parse(b"A,B\r\n1,2,\r\n")
    assert parsed.ragged == set()


@pytest.mark.parametrize(
    "data, code",
    [
        (b"", "empty_file"),
        (b"\r\n\r\n", "no_header"),
        (b"A,B\r\n", "no_rows"),
        (b"PK\x03\x04" + b"\x00" * 30, "unsupported_format"),
        (b"%PDF-1.7\n", "unsupported_format"),
        (b"A,B\r\n1,\x00\r\n", "unsupported_format"),
        ("A,B\r\n1,2\r\n".encode("utf-16"), "unreadable_encoding"),
        (b'A,B\r\n"unterminated,2\r\n', "unreadable_file"),
    ],
)
def test_files_that_cannot_be_imported_are_refused_with_a_code(data, code):
    assert refused(data) == code


def test_the_caps(monkeypatch):
    monkeypatch.setattr(limits, "MAX_FILE_BYTES", 40)
    assert refused(b"A\r\n" + b"x" * 60) == "too_large"
    monkeypatch.setattr(limits, "MAX_FILE_BYTES", 5 * 1024 * 1024)
    monkeypatch.setattr(limits, "MAX_ROWS", 3)
    assert refused(b"A\r\n1\r\n2\r\n3\r\n4\r\n") == "too_many_rows"
    assert len(parse(b"A\r\n1\r\n2\r\n3\r\n").rows) == 3
    monkeypatch.setattr(limits, "MAX_COLUMNS", 2)
    assert refused(b"A,B,C\r\n1,2,3\r\n") == "too_many_columns"
    monkeypatch.setattr(limits, "MAX_CELL_CHARS", 5)
    with pytest.raises(CsvRefused) as caught:
        parse(b"A\r\nabcdefgh\r\n")
    assert (caught.value.code, caught.value.row) == ("cell_too_long", 2)
    monkeypatch.setattr(limits, "MAX_HEADER_CHARS", 3)
    assert refused(b"abcdef\r\n1\r\n") == "header_too_long"


def test_nothing_is_evaluated_and_formulas_are_plain_text():
    parsed = parse(b"A\r\n=HYPERLINK(\"http://x\")\r\n@SUM(1)\r\n")
    assert parsed.rows[0][1] == ['=HYPERLINK("http://x")']
    assert parsed.rows[1][1] == ["@SUM(1)"]
