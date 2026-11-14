"""A report's card as a CSV file: the result table of one card.

``POST .../report/export`` takes ``{definition, card, format: "csv"}`` and answers
the table the screen shows for that card: one row per group (its label, how many
responses are in it, its share of the answered ones and one column per measure
that is not a plain count). It is built from the same result a query gives
(``ReportService._compute``), so the file can never differ from the screen, and it
is built in memory and handed to the requester: nothing is stored.

* **A few lines of context come first** (``key,value`` rows, then an empty row and
  the table): the form's title, what the card is, how many responses it covers, the
  filters in words, the time zone the days follow and when the figures were made.
  A condition on an answer is mentioned by its count only, not by what was asked:
  a value asked about is an answer.
* **Every cell goes through the export's CSV writer** (``response_export.table.
  csv_line``): a cell that a spreadsheet would read as a formula (a leading ``=``,
  ``+``, ``-``, ``@``, tab or carriage return) gets an apostrophe in front. Group
  labels are option labels and bucket names the form's author typed, so they are
  guarded like any other text. UTF-8 with a byte order mark, as the responses
  export.
* **Words are English**, the language of the server's labels; the group ``key``
  is not in the file, the label is.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from http import HTTPStatus

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from backend.app.services.reporting import limits
from backend.app.services.reporting.catalogue import (
    COUNT,
    DATE,
    SUBMITTED_AT,
    Catalogue,
)
from backend.app.services.reporting.definition import Definition, error, invalid
from backend.app.services.response_export.table import csv_line, export_file_name
from backend.app.services.response_export.writer import BOM, LINE_BREAK

# the channel an audit entry names for a report file (``export_channel``)
CHANNEL = "report"
# what a request may ask for: the one format there is today
FORMAT = "csv"
CONTENT_TYPE = "text/csv; charset=utf-8"

_AGG_WORDS = {"count": "Count", "avg": "Average", "sum": "Sum", "min": "Lowest", "max": "Highest"}
_BUILTIN_WORDS = {
    "submitted_at": "Submission date",
    "form_version": "Form version",
    "respondent": "Respondent",
    "ending": "Ending reached",
    "status": "Deletion request",
    "feedback_status": "Feedback status",
    "source": "Source",
}


class ExportRequest(BaseModel):
    """``definition``: the report's; ``card``: the id of the card whose table is
    wanted; ``format``: ``csv``."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, alias_generator=to_camel)

    definition: Dict[str, Any]
    card: str = Field(min_length=1, max_length=limits.CARD_ID_MAX)
    format: Literal["csv"] = FORMAT


def parse(body: bytes) -> ExportRequest:
    """The request, or 422 ``invalid_definition`` naming where it went wrong,
    never what was sent."""
    cap = limits.DEFINITION_MAX_BYTES + 2048
    if len(body) > cap:
        raise error(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_definition",
            f"A request here is at most {cap} bytes.",
        )
    try:
        return ExportRequest.model_validate_json(body)
    except ValidationError as problem:
        first = problem.errors(include_url=False, include_context=False, include_input=False)[0]
        where = ".".join(str(part) for part in first["loc"]) or "body"
        raise invalid(f"{where}: {first['msg']}") from None


@dataclass
class ReportFile:
    """The file to hand out: its bytes, its name and how many groups it holds
    (what the audit entry counts)."""

    content: bytes
    file_name: str
    groups: int
    content_type: str = CONTENT_TYPE


def _field_label(catalogue: Catalogue, key: Optional[str]) -> str:
    if key is None:
        return ""
    found = catalogue.get(key)
    if found is not None:
        return found.label
    return _BUILTIN_WORDS.get(key, key)


def _filter_lines(definition: Definition) -> List[str]:
    """The filters of the report, in words. Dates and versions are as typed; a
    condition on an answer is only counted."""
    filters = definition.filters
    lines: List[str] = []
    if filters.submitted_from is not None:
        lines.append(f"Submitted from {filters.submitted_from.isoformat()}")
    if filters.submitted_to is not None:
        lines.append(f"Submitted before {filters.submitted_to.isoformat()}")
    if filters.form_version:
        lines.append("Form versions " + ", ".join(str(v) for v in sorted(set(filters.form_version))))
    if filters.respondent is not None:
        lines.append(f"Respondents: {getattr(filters.respondent, 'value', filters.respondent)}")
    if filters.status:
        lines.append(
            "Deletion request: "
            + ", ".join(str(getattr(s, "value", s)) for s in filters.status)
        )
    if filters.where:
        lines.append(f"Conditions on answers: {len(filters.where)}")
    return lines


def build_csv(
    *,
    form_title: str,
    catalogue: Catalogue,
    definition: Definition,
    result: Dict[str, Any],
    now: Optional[dt.datetime] = None,
) -> ReportFile:
    """The CSV of the one card in ``definition`` (``result``: what a query of that
    definition answered)."""
    card = definition.cards[0]
    figures = result["cards"][0]
    dimension = card.dimension
    measures = card.measures
    extra = [(i, m) for i, m in enumerate(measures) if m.agg != COUNT]

    title = card.title or (
        f"{_field_label(catalogue, dimension.field)}" if dimension is not None else "All responses"
    )
    context: List[List[Any]] = [
        ["Report", form_title],
        ["Card", title],
        ["Grouped by", _field_label(catalogue, dimension.field) if dimension is not None else "None"],
        ["Responses in the card", figures["n"]],
        ["Answered", figures["answered"]],
    ]
    filter_lines = _filter_lines(definition)
    context.append(["Filters", "; ".join(filter_lines) if filter_lines else "None"])
    asked = catalogue.get(dimension.field) if dimension is not None else None
    time_based = dimension is not None and (
        dimension.field == SUBMITTED_AT or (asked is not None and asked.kind == DATE)
    )
    context.append(
        ["Time zone", definition.tz + (" (days and weeks start at midnight there)" if time_based else "")]
    )
    context.append(["Generated at (UTC, ISO 8601)", result["generatedAt"]])
    if figures.get("multiple"):
        context.append(
            [
                "Note",
                "Respondents could pick several options, so the counts add up to more than the number of responses.",
            ]
        )
    if figures.get("truncated") or figures["otherGroups"]["count"]:
        context.append(["Note", "Only the largest groups are listed; the rest are in the last row."])

    headers = ["Group", "Responses", "Share of answered (%)"]
    for _, measure in extra:
        label = _field_label(catalogue, measure.field)
        headers.append(f"{_AGG_WORDS[measure.agg]} of {label}")
    rows: List[List[Any]] = []
    answered = figures["answered"]
    for group in figures["groups"]:
        share = round(100 * group["n"] / answered, 1) if dimension is not None and answered else None
        label = group["label"] if dimension is not None else "All responses"
        row: List[Any] = [label, group["n"], share]
        for index, _ in extra:
            row.append(group["values"][index])
        rows.append(row)
    others = figures["otherGroups"]
    if others["count"]:
        row = ["Other groups", others["n"], None]
        row.extend(None for _ in extra)
        rows.append(row)

    lines = [csv_line(cells) for cells in context]
    lines.append("")
    lines.append(csv_line(headers))
    lines.extend(csv_line(cells) for cells in rows)
    text = BOM + LINE_BREAK.join(lines) + LINE_BREAK
    return ReportFile(
        content=text.encode("utf-8"),
        file_name=export_file_name(form_title, "report"),
        groups=len(rows),
    )
