"""The export as an Excel workbook (``.xlsx``), written as a stream.

An ``.xlsx`` is a ZIP of XML parts. This module writes the five fixed parts and
then each table's ``<sheetData>`` one row at a time into a ZIP that is never
seekable, so, like the CSV archive, no table is held in memory and no answer
touches disk (a library would need a seekable file: XlsxWriter's
``constant_memory`` spools to temporary files and its ``in_memory`` mode holds
the workbook). Every table is written by a pass of its own over the responses
(``source()``), as in ``writer.py``.

What it writes, and nothing else: inline strings, numbers, date serials, one
small fixed style sheet. There is no way to emit a macro, a formula, a
defined name or an external link, so a workbook made here cannot run anything.

* **Text is text.** A string is an ``inlineStr`` cell: Excel and LibreOffice
  never evaluate it. The residual risk of the CSV, a cell that turns into a
  formula when the person edits it, is closed by the ``quotePrefix`` flag (the
  same thing as typing an apostrophe): a string ``formula_like`` selects gets
  the style that carries it, and its text stays as the respondent wrote it.
  The header row gets the same guard.
* **Real dates.** A column the plan marks ``datetime`` (the submission time) or
  ``date`` (a date question) is written as a date serial when the text is an
  ISO date, else it stays text. Excel has no zone on a serial: the submission
  time is UTC, which the column header says.
* **A file that opens.** Characters XML 1.0 forbids are removed, the
  ``_xHHHH_`` escape that Excel decodes inside strings is itself escaped, a text
  over Excel's 32,767 characters is cut, integers Excel could not hold exactly
  (16 digits or more) are written as text, sheet names follow Excel's rules (at most 31 UTF-16 units).
  More columns than Excel's 16,384 are refused (``TooManyColumns``); a sheet
  that would pass its 1,048,576 rows stops the file (``SheetFull``).
"""

from __future__ import annotations

import datetime as dt
import math
import re
import zipfile
from typing import AsyncIterator, Callable, Iterable, List, Optional, Sequence

from backend.app.services.response_export.table import (
    CellValue,
    ExportPlan,
    ExportResponse,
    formula_like,
    number_text,
)
from backend.app.services.response_export.writer import (
    RowCount,
    ResponseSource,
    _Sink,
)

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

MAX_COLUMNS = 16_384
MAX_ROWS_PER_SHEET = 1_048_576
MAX_CELL_CHARS = 32_767
SHEET_NAME_MAX = 31
# an integer of this size or more has digits Excel's numbers (15) would round off
_EXACT_LIMIT = 10**15

# cell styles (``styles.xml``, in this order)
STYLE_DEFAULT = 0
STYLE_HEADER = 1
STYLE_DATETIME = 2
STYLE_DATE = 3
STYLE_TEXT = 4  # quotePrefix: text even when edited
STYLE_HEADER_TEXT = 5

_EPOCH = dt.datetime(1899, 12, 30)
_FIRST_SAFE_SERIAL = 61.0  # 1900-03-01
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_ISO_DATETIME = re.compile(
    r"([0-9]{4}-[0-9]{2}-[0-9]{2})[T ]([0-9]{2}):([0-9]{2})(?::([0-9]{2}))?(?:\.[0-9]+)?(Z|[+-][0-9]{2}:?[0-9]{2})?"
)
# characters XML 1.0 cannot carry (control characters, lone surrogates, U+FFFE/F)
_XML_ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
# ``_x0041_``: Excel reads this as the character U+0041 inside a string. Every
# underscore that starts one (also overlapping ones, ``_x0041_x0042_``, and a
# capital ``X``: whether the reader is case-sensitive is not ours to bet on)
# is itself escaped
_X_ESCAPE = re.compile(r"_(?=[xX][0-9A-Fa-f]{4}_)")
_SHEET_NAME_BAD = re.compile(r"[\[\]:*?/\\\x00-\x1f]+")

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


class TooManyColumns(ValueError):
    """The table has more columns than a worksheet can hold."""


class SheetFull(Exception):
    """A table has more rows than a worksheet can hold."""


# --------------------------------------------------------------------- text


def column_letters(index: int) -> str:
    """``0`` -> ``A``, ``25`` -> ``Z``, ``26`` -> ``AA`` (zero-based)."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def xml_text(value: str) -> str:
    """``value`` as XML character data that Excel reads back as the same text:
    illegal characters dropped, ``&``/``<``/``>`` escaped, the ``_xHHHH_``
    escape itself escaped, cut at Excel's cell limit."""
    value = _XML_ILLEGAL.sub("", value)
    if len(value) > MAX_CELL_CHARS:
        value = value[:MAX_CELL_CHARS]
    value = _X_ESCAPE.sub("_x005F_", value)
    # a carriage return as a character reference: a bare one is read back as a line feed
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\r", "&#13;")


def xml_attribute(value: str) -> str:
    """``value`` for an XML attribute (a sheet name may hold a quote)."""
    return xml_text(value).replace('"', "&quot;").replace("\t", "&#9;").replace("\n", "&#10;")


def _cut_utf16(text: str, units: int) -> str:
    """The longest start of ``text`` of at most ``units`` UTF-16 code units (what
    Excel counts in a sheet name), never half of a pair."""
    used = 0
    for index, ch in enumerate(text):
        step = 2 if ord(ch) > 0xFFFF else 1
        if used + step > units:
            return text[:index]
        used += step
    return text


def sheet_name(name: str, taken: Iterable[str]) -> str:
    """A worksheet name Excel accepts: at most 31 characters, none of
    ``[]:*?/\\``, not empty, not starting or ending with an apostrophe, not the
    reserved ``History``, unique among ``taken`` ignoring case."""
    # characters XML cannot carry go first: the name must stay unique once they are gone
    cleaned = _SHEET_NAME_BAD.sub(" ", _XML_ILLEGAL.sub("", name or "")).strip().strip("'").strip()
    cleaned = _cut_utf16(cleaned, SHEET_NAME_MAX).strip().strip("'").strip() or "Sheet"
    if cleaned.lower() == "history":
        cleaned = "History (2)"
    used = {t.lower() for t in taken}
    candidate, n = cleaned, 2
    while candidate.lower() in used:
        suffix = f" ({n})"
        candidate = _cut_utf16(cleaned, SHEET_NAME_MAX - len(suffix)).rstrip() + suffix
        n += 1
    return candidate


def date_serial(text: str, kind: str) -> Optional[float]:
    """The Excel serial of an ISO date (``date``) or date-time (``datetime``,
    converted to UTC), or None when ``text`` is neither."""
    text = text.strip()
    try:
        if kind == "date":
            if not _ISO_DATE.fullmatch(text):
                return None
            serial = float((dt.datetime.fromisoformat(text) - _EPOCH).days)
            # before 1900-03-01 Excel's calendar disagrees with the real one
            return serial if serial >= _FIRST_SAFE_SERIAL else None
        match = _ISO_DATETIME.fullmatch(text)
        if not match:
            return None
        day, hour, minute, second, zone = match.groups()
        value = dt.datetime.fromisoformat(f"{day}T{hour}:{minute}:{second or '00'}")
        if zone and zone != "Z":
            sign = 1 if zone[0] == "+" else -1
            digits = zone[1:].replace(":", "")
            value -= sign * dt.timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
        elapsed = value - _EPOCH
        serial = elapsed.days + elapsed.seconds / 86400
        return serial if serial >= _FIRST_SAFE_SERIAL else None
    except (ValueError, OverflowError):
        return None


def _serial_text(serial: float) -> str:
    return format(serial, ".10f").rstrip("0").rstrip(".")


# -------------------------------------------------------------------- cells


def cell_xml(ref: str, value: CellValue, kind: Optional[str] = None, header: bool = False) -> str:
    """One ``<c>`` element, or nothing for an empty value."""
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        value = "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            value = str(value)
        elif abs(value) >= _EXACT_LIMIT and (isinstance(value, int) or value == int(value)):
            # more digits than Excel keeps: text, so none is lost
            value = number_text(value)
        else:
            return f'<c r="{ref}"><v>{number_text(value)}</v></c>'
    # characters XML cannot carry go before the formula check: "\x00=1" is written as "=1"
    text = _XML_ILLEGAL.sub("", str(value))
    if text == "":
        return ""
    if kind in ("date", "datetime") and not header:
        serial = date_serial(text, kind)
        if serial is not None:
            style = STYLE_DATETIME if kind == "datetime" else STYLE_DATE
            return f'<c r="{ref}" s="{style}"><v>{_serial_text(serial)}</v></c>'
    if header:
        style = STYLE_HEADER_TEXT if formula_like(text) else STYLE_HEADER
    else:
        style = STYLE_TEXT if formula_like(text) else STYLE_DEFAULT
    attribute = f' s="{style}"' if style else ""
    return f'<c r="{ref}"{attribute} t="inlineStr"><is><t xml:space="preserve">{xml_text(text)}</t></is></c>'


def row_xml(number: int, values: Sequence[CellValue], kinds: Sequence[Optional[str]], header: bool = False) -> str:
    cells = "".join(
        cell_xml(f"{column_letters(i)}{number}", value, kinds[i] if i < len(kinds) else None, header)
        for i, value in enumerate(values)
    )
    return f'<row r="{number}">{cells}</row>'


# -------------------------------------------------------------------- parts


def content_types(sheets: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(1, sheets + 1)
    )
    return (
        XML_HEAD
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        + overrides
        + "</Types>"
    )


def root_rels() -> str:
    return (
        XML_HEAD
        + f'<Relationships xmlns="{NS_PKG_REL}">'
        f'<Relationship Id="rId1" Type="{NS_REL}/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def workbook(names: Sequence[str]) -> str:
    sheets = "".join(
        f'<sheet name="{xml_attribute(name)}" sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(names, 1)
    )
    return (
        XML_HEAD
        + f'<workbook xmlns="{NS_MAIN}" xmlns:r="{NS_REL}">'
        '<bookViews><workbookView/></bookViews>'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def workbook_rels(sheets: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{i}" Type="{NS_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>'
        for i in range(1, sheets + 1)
    )
    styles = f'<Relationship Id="rId{sheets + 1}" Type="{NS_REL}/styles" Target="styles.xml"/>'
    return XML_HEAD + f'<Relationships xmlns="{NS_PKG_REL}">{rels}{styles}</Relationships>'


def styles() -> str:
    return (
        XML_HEAD
        + f'<styleSheet xmlns="{NS_MAIN}">'
        '<numFmts count="2">'
        '<numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd\\ hh:mm:ss"/>'
        '<numFmt numFmtId="165" formatCode="yyyy\\-mm\\-dd"/>'
        "</numFmts>"
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="6">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" quotePrefix="1"/>'
        '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" quotePrefix="1"/>'
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _widths(headers: Sequence[str]) -> str:
    cols = "".join(
        f'<col min="{i}" max="{i}" width="{min(40, max(12, len(h) + 4))}" customWidth="1"/>'
        for i, h in enumerate(headers, 1)
    )
    return f"<cols>{cols}</cols>" if cols else ""


def sheet_head(headers: Sequence[str]) -> str:
    return (
        XML_HEAD
        + f'<worksheet xmlns="{NS_MAIN}">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
        '<selection pane="bottomLeft"/></sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        + _widths(headers)
        + "<sheetData>"
    )


def sheet_tail(columns: int, rows: int) -> str:
    # the filter spans the table as written: known only now that every row is
    ref = f"A1:{column_letters(max(columns, 1) - 1)}{max(rows, 1)}"
    return f'</sheetData><autoFilter ref="{ref}"/></worksheet>'


# -------------------------------------------------------------------- writer


async def _sheet_text(
    headers: List[str],
    kinds: List[Optional[str]],
    rows: Callable[[ExportResponse], List[List[CellValue]]],
    source: ResponseSource,
    counter: Optional[RowCount],
) -> AsyncIterator[str]:
    yield sheet_head(headers)
    yield row_xml(1, headers, [], header=True)
    written = 1
    async for response in source():
        for cells in rows(response):
            written += 1
            if written > MAX_ROWS_PER_SHEET:
                raise SheetFull()
            yield row_xml(written, cells, kinds)
        if counter is not None:
            counter.rows += 1
    yield sheet_tail(len(headers), written)


async def _pieces(text: AsyncIterator[str], piece_bytes: int) -> AsyncIterator[bytes]:
    buffered: List[str] = []
    size = 0
    async for part in text:
        buffered.append(part)
        size += len(part)
        if size >= piece_bytes:
            yield "".join(buffered).encode("utf-8")
            buffered, size = [], 0
    if buffered:
        yield "".join(buffered).encode("utf-8")


def fits_a_sheet(plan: ExportPlan) -> bool:
    """Do the plan's tables have no more columns than a worksheet holds?"""
    return len(plan.headers) <= MAX_COLUMNS and all(len(t.headers) <= MAX_COLUMNS for t in plan.group_tables)


def sheet_names(plan: ExportPlan) -> List[str]:
    names: List[str] = []
    for name in plan.table_names():
        names.append(sheet_name(name, names))
    return names


async def write_xlsx(
    plan: ExportPlan,
    form_title: str,  # noqa: ARG001 - kept so every format takes the same arguments
    source: ResponseSource,
    counter: Optional[RowCount] = None,
    piece_bytes: int = 64 * 1024,
) -> AsyncIterator[bytes]:
    """The workbook's bytes: sheet ``Responses`` (the main table) and one sheet
    per repeating group exported as a table. ``counter`` counts the rows of the
    main table. Raises ``TooManyColumns`` before the first byte, ``SheetFull``
    when a table passes a worksheet's rows."""
    if not fits_a_sheet(plan):
        raise TooManyColumns()
    names = sheet_names(plan)
    tables = [
        (plan.headers, plan.kinds, lambda r: [plan.row(r)], counter),
        *((t.headers, t.all_kinds, t.rows, None) for t in plan.group_tables),
    ]
    sink = _Sink()
    archive = zipfile.ZipFile(sink, "w", zipfile.ZIP_DEFLATED)  # type: ignore[arg-type]
    now = dt.datetime.now(dt.timezone.utc)
    stamp = (max(now.year, 1980), now.month, now.day, now.hour, now.minute, now.second)

    def info(name: str) -> zipfile.ZipInfo:
        entry = zipfile.ZipInfo(name, date_time=stamp)
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o600 << 16
        return entry

    parts = [
        ("[Content_Types].xml", content_types(len(names))),
        ("_rels/.rels", root_rels()),
        ("xl/workbook.xml", workbook(names)),
        ("xl/_rels/workbook.xml.rels", workbook_rels(len(names))),
        ("xl/styles.xml", styles()),
    ]
    try:
        for name, text in parts:
            archive.writestr(info(name), text.encode("utf-8"))
            data = sink.take()
            if data:
                yield data
        for number, (headers, kinds, rows, table_counter) in enumerate(tables, 1):
            # a sheet's size is not known before it is written: ZIP64 sizes, so one past 4 GiB is still a valid archive
            with archive.open(info(f"xl/worksheets/sheet{number}.xml"), "w", force_zip64=True) as entry:
                async for piece in _pieces(_sheet_text(headers, kinds, rows, source, table_counter), piece_bytes):
                    entry.write(piece)
                    data = sink.take()
                    if data:
                        yield data
            data = sink.take()
            if data:
                yield data
    finally:
        archive.close()
    data = sink.take()
    if data:
        yield data
