"""Writes an export as a stream of bytes: a CSV, or, when a repeating group
exports as a table of its own, a ZIP of one CSV per table.

Rows come from ``source()``, which returns a fresh async iterator of decrypted
responses each time it is called: every table is written by a pass of its own,
so no table is buffered and no answer is ever spooled to disk. Memory stays at
one batch of responses plus one output piece.
"""

from __future__ import annotations

import datetime as dt
import zipfile
from dataclasses import dataclass
from typing import AsyncIterator, Callable, List, Optional

from backend.app.services.response_export.table import (
    ExportPlan,
    ExportResponse,
    csv_line,
    export_file_name,
)

# so spreadsheet apps read UTF-8 (names with accents) correctly
BOM = "﻿"
LINE_BREAK = "\r\n"
# a piece of output is at least this large before it is handed on
PIECE_BYTES = 64 * 1024

ResponseSource = Callable[[], AsyncIterator[ExportResponse]]


@dataclass
class RowCount:
    """How many rows of the main table were written (the audit entry's count)."""

    rows: int = 0


class _Sink:
    """A write-only file that hands back what was written since the last take
    (``zipfile`` needs nothing more of an unseekable output)."""

    def __init__(self) -> None:
        self._parts: List[bytes] = []

    def write(self, data: bytes) -> int:
        self._parts.append(bytes(data))
        return len(data)

    def flush(self) -> None:  # pragma: no cover - required by the protocol
        pass

    def take(self) -> bytes:
        data = b"".join(self._parts)
        self._parts.clear()
        return data


async def _table_text(
    headers: List[str],
    rows: Callable[[ExportResponse], List[List]],
    source: ResponseSource,
    counter: Optional[RowCount],
) -> AsyncIterator[str]:
    """The text of one table in pieces: the header, then each row after a line break."""
    yield BOM + csv_line(headers)
    async for response in source():
        for cells in rows(response):
            yield LINE_BREAK + csv_line(cells)
        if counter is not None:
            counter.rows += 1


async def _pieces(text: AsyncIterator[str]) -> AsyncIterator[bytes]:
    buffered: List[str] = []
    size = 0
    async for part in text:
        buffered.append(part)
        size += len(part)
        if size >= PIECE_BYTES:
            yield "".join(buffered).encode("utf-8")
            buffered, size = [], 0
    if buffered:
        yield "".join(buffered).encode("utf-8")


def table_file_names(form_title: str, plan: ExportPlan) -> List[str]:
    """The CSV file name of each table, unique inside one archive."""
    names: List[str] = []
    for index, name in enumerate(plan.table_names()):
        candidate = export_file_name(form_title) if index == 0 else export_file_name(form_title, name)
        base, dot, extension = candidate.rpartition(".")
        n = 2
        while candidate in names:
            candidate = f"{base} ({n}){dot}{extension}"
            n += 1
        names.append(candidate)
    return names


async def write_export(
    plan: ExportPlan, form_title: str, source: ResponseSource, counter: Optional[RowCount] = None
) -> AsyncIterator[bytes]:
    """The export's bytes: one CSV, or a ZIP of CSVs when the plan has group
    tables. ``counter`` counts the rows of the main table."""
    main_rows = lambda response: [plan.row(response)]  # noqa: E731
    if not plan.group_tables:
        async for piece in _pieces(_table_text(plan.headers, main_rows, source, counter)):
            yield piece
        return

    names = table_file_names(form_title, plan)
    tables = [(plan.headers, main_rows, counter)] + [
        (t.headers, t.rows, None) for t in plan.group_tables
    ]
    sink = _Sink()
    archive = zipfile.ZipFile(sink, "w", zipfile.ZIP_DEFLATED)  # type: ignore[arg-type]
    now = dt.datetime.now(dt.timezone.utc)
    stamp = (max(now.year, 1980), now.month, now.day, now.hour, now.minute, now.second)
    try:
        for name, (headers, rows, table_counter) in zip(names, tables):
            info = zipfile.ZipInfo(name, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            with archive.open(info, "w") as entry:
                async for piece in _pieces(_table_text(headers, rows, source, table_counter)):
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
