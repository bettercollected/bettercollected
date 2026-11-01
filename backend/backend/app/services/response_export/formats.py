"""The file formats of a responses export, and how each is written.

``csv`` (a ZIP of CSVs when a repeating group exports as tables), ``xlsx`` and
``json`` are written from the same plan (columns, filters, order) over the same
pass over the responses, and go through the same request, job, limits and audit
(``service.py``): the format is a parameter, not a path. ``stored_format`` is
what the audit entry and the file name say (``zip`` for a CSV archive).
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Optional

from backend.app.services.response_export.json_export import JSON_MEDIA_TYPE, write_json
from backend.app.services.response_export.table import ExportPlan
from backend.app.services.response_export.writer import (
    ResponseSource,
    RowCount,
    write_export,
)
from backend.app.services.response_export.xlsx import XLSX_MEDIA_TYPE, write_xlsx

REQUESTABLE = ("csv", "xlsx", "json")
DEFAULT_FORMAT = "csv"

MEDIA_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "zip": "application/zip",
    "xlsx": XLSX_MEDIA_TYPE,
    "json": JSON_MEDIA_TYPE,
}


def stored_format(requested: Optional[str], plan: ExportPlan) -> str:
    """The format the file has: the requested one, except that a CSV export of a
    form with group tables is a ``zip``."""
    requested = requested or DEFAULT_FORMAT
    if requested == "csv":
        return "zip" if plan.group_tables else "csv"
    return requested


def media_type(stored: Optional[str]) -> str:
    return MEDIA_TYPES.get(stored or "csv", MEDIA_TYPES["csv"])


def write_file(
    stored: str,
    plan: ExportPlan,
    form: Dict[str, Any],
    source: ResponseSource,
    counter: Optional[RowCount] = None,
) -> AsyncIterator[bytes]:
    """The bytes of the export in the ``stored`` format."""
    title = str(form.get("title") or "")
    if stored == "xlsx":
        return write_xlsx(plan, title, source, counter)
    if stored == "json":
        return write_json(plan, form, source, counter)
    return write_export(plan, title, source, counter)
