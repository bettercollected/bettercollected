"""Reading an uploaded CSV file: encoding, separator, quoting and the caps.

Only the standard library's ``csv`` module reads the text: nothing is
evaluated, no formula is looked at, and the process-wide ``csv.field_size_limit``
is left alone (the file cap bounds every field; the cell cap is checked after
parsing). The file is refused, with a code the webapp translates, when it is a
ZIP or any binary (an XLSX is a ZIP), is not UTF-8 or Windows-1252 text, or
exceeds a cap; parsing stops at the first cap it meets.

Row numbers are record numbers with the header as row 1 (a spreadsheet's
numbering when no cell holds a line break).
"""

import csv
import io
from dataclasses import dataclass, field
from typing import List, Set, Tuple

from backend.app.services.response_import import limits

SEPARATORS = (",", ";")
_ZIP_MAGIC = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


class CsvRefused(Exception):
    """The file cannot be imported; ``code`` says why (never a value from it)."""

    def __init__(self, code: str, row: int = 0):
        super().__init__(code)
        self.code = code
        self.row = row


@dataclass
class ParsedCsv:
    headers: List[str]
    # (row number, cells padded to the header's width)
    rows: List[Tuple[int, List[str]]]
    encoding: str
    separator: str
    # rows that had a non-empty cell beyond the header's width
    ragged: Set[int] = field(default_factory=set)


def decode(data: bytes) -> Tuple[str, str]:
    """The text of the file and the name of the encoding it was read as:
    UTF-8 (with or without a byte order mark), else Windows-1252."""
    if data.startswith(_UTF16_BOMS):
        raise CsvRefused("unreadable_encoding")
    if any(data.startswith(magic) for magic in _ZIP_MAGIC) or data.startswith(b"%PDF"):
        raise CsvRefused("unsupported_format")
    if b"\x00" in data:
        raise CsvRefused("unsupported_format")
    try:
        text = data.decode("utf-8-sig")
        encoding = "utf-8-bom" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError:
            raise CsvRefused("unreadable_encoding") from None
        encoding = "cp1252"
    return text, encoding


def _first_record(text: str) -> str:
    """The first record's text (up to the first line break outside quotes)."""
    quoted = False
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif char in "\r\n" and not quoted:
            return text[:index]
    return text


def _sep_line(text: str) -> Tuple[str, str]:
    """An Excel ``sep=;`` first line names the separator and is not data."""
    first, _, rest = text.partition("\n")
    stripped = first.strip()
    if len(stripped) == 5 and stripped.lower().startswith("sep=") and stripped[4] in SEPARATORS:
        return stripped[4], rest
    return "", text


def detect_separator(text: str) -> str:
    """``;`` when the header line has more semicolons than commas outside
    quotes, else ``,``."""
    first = _first_record(text)
    counts = {sep: 0 for sep in SEPARATORS}
    quoted = False
    for char in first:
        if char == '"':
            quoted = not quoted
        elif not quoted and char in counts:
            counts[char] += 1
    return ";" if counts[";"] > counts[","] else ","


def parse(data: bytes) -> ParsedCsv:
    """The headers and rows of an uploaded file, or ``CsvRefused``."""
    if not data:
        raise CsvRefused("empty_file")
    if len(data) > limits.MAX_FILE_BYTES:
        raise CsvRefused("too_large")
    text, encoding = decode(data)
    named, text = _sep_line(text)
    separator = named or detect_separator(text)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=separator, strict=True)
    headers: List[str] = []
    rows: List[Tuple[int, List[str]]] = []
    ragged: Set[int] = set()
    number = 0
    try:
        for record in reader:
            number += 1
            if number == 1:
                if not any(cell.strip() for cell in record):
                    raise CsvRefused("no_header")
                if len(record) > limits.MAX_COLUMNS:
                    raise CsvRefused("too_many_columns")
                headers = [cell.strip() for cell in record]
                if any(len(h) > limits.MAX_HEADER_CHARS for h in headers):
                    raise CsvRefused("header_too_long")
                continue
            if not record or not any(cell.strip() for cell in record):
                continue
            if len(rows) >= limits.MAX_ROWS:
                raise CsvRefused("too_many_rows")
            if any(len(cell) > limits.MAX_CELL_CHARS for cell in record):
                raise CsvRefused("cell_too_long", number)
            width = len(headers)
            if len(record) > width and any(cell.strip() for cell in record[width:]):
                ragged.add(number)
            rows.append((number, (record[:width] + [""] * width)[:width]))
    except csv.Error:
        # an unterminated quote, or a field over the module's own limit
        raise CsvRefused("unreadable_file", number) from None
    if not headers:
        raise CsvRefused("empty_file")
    if not rows:
        raise CsvRefused("no_rows")
    return ParsedCsv(headers=headers, rows=rows, encoding=encoding, separator=separator, ragged=ragged)
