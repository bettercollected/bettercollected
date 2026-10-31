"""What an export holds: its columns, in their order, and how each answer is
written as a cell.

This is the rule the webapp used to apply in the browser
(``webapp/src/utils/response-export.ts`` and the helpers behind it), moved
here so a form's responses never have to travel to the browser as one JSON
document. ``tests/app/response_export/test_table.py`` pins it with the
output of that TypeScript on the same data. The Google Sheets action keeps its
own, older formatting (``temporal/actions-executor/utilities/form.py``).

Layout of the main table, left to right: the responder, one column per
answered question (a repeating group expands to columns per item, or, when it
exports as ``rows``, to an item count and a table of its own), the form's
internal (staff) fields, then, at the END so the columns scripts read by
position do not move: the response id, the submission time and one column per
declared hidden field.

A column has a stable ``key`` that a request may name to export only some:
``responder``, ``q:<field id>`` (a repeating group included), ``internal:<field
id>``, ``response_id``, ``submitted_at``, ``hidden:<name>``. A group exported as
``rows`` needs ``response_id`` to join its table to the main one, so choosing
it brings the response id along.
"""

from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

CellValue = Any  # str | int | float

RESPONDER_ID_COLUMN = "Responder ID"
RESPONSE_ID_COLUMN = "Response ID"
SUBMITTED_AT_COLUMN = "Submitted at (UTC, ISO 8601)"
HIDDEN_COLUMN_PREFIX = "Hidden: "
INTERNAL_COLUMN_PREFIX = "Internal: "
ANONYMOUS_LABEL = "Anonymous"
# a multi-select inside one cell: a comma would read as a column break
LIST_SEPARATOR = "; "

REPEAT_COLUMNS_EXPORT_MAX = 5
REPEAT_MAX_ITEMS_LIMIT = 50

KEY_RESPONDER = "responder"
KEY_RESPONSE_ID = "response_id"
KEY_SUBMITTED_AT = "submitted_at"
QUESTION_PREFIX = "q:"
INTERNAL_PREFIX = "internal:"
HIDDEN_PREFIX = "hidden:"

_IGNORED_TYPES = (None, "text", "IMAGE_CONTENT", "VIDEO_CONTENT")
_UUID = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_PLACEHOLDERS = {
    "email": "Enter Your Email Address",
    "number": "Enter Number",
    "short_text": "Enter Question",
    "url": "Enter Link",
    "phone_number": "Enter Your Phone Number",
    "file_upload": "Upload Your File",
    "yes_no": "Are you sure?",
    "dropdown": "Select an option",
    "multiple_choice": "Select from list below.",
    "text": "Add Text",
    "rating": "Rate from 1 to 5",
    "date": "Select a date",
    "linear_rating": "Rate from 1 to 10",
    "matrix": "Matrix Field",
    "tabular_input": "Tabular Input Field",
    "group": "Repeating group",
    "calculated": "Calculation",
}


class UnknownColumn(ValueError):
    """A requested column key the form does not have."""


# ---------------------------------------------------------------- small helpers


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _get(mapping: Any, snake: str, camel: Optional[str] = None) -> Any:
    """A value stored under its snake_case key (a camelCase one is read too)."""
    mapping = _dict(mapping)
    if snake in mapping:
        return mapping[snake]
    return mapping.get(camel) if camel else None


def _truthy(value: Any) -> bool:
    """JavaScript truthiness for the values answers hold."""
    if value is None or value is False or value == "" or value == 0:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    return True


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def cell(value: Any) -> CellValue:
    """A cell: nothing is empty, numbers stay numbers, the rest is text."""
    if value is None:
        return ""
    if _is_number(value):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def number_text(value: CellValue) -> str:
    """A number as JavaScript prints it (``5``, never ``5.0``)."""
    if isinstance(value, float):
        if math.isfinite(value) and value == int(value) and abs(value) < 1e21:
            return str(int(value))
        return repr(value)
    return str(value)


def _join(values: Iterable[Any], separator: str) -> str:
    """``Array.prototype.join``: a missing value is an empty string."""
    return separator.join("" if v is None else _text(v) for v in values)


def _text(value: Any) -> str:
    if _is_number(value):
        return number_text(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# ----------------------------------------------------------------- field titles


def _walk_title(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        text = node.get("text")
        return text if isinstance(text, str) else ""
    if node.get("type") == "answerPipe":
        attrs = _dict(node.get("attrs"))
        return str(attrs.get("label") or attrs.get("pipeKey") or "")
    return "".join(_walk_title(child) for child in _list(node.get("content")))


def field_title(field_: Dict[str, Any]) -> str:
    """The question as a column title (``extractTextfromJSON``): a plain-text
    version of a rich title, answer pipes as their label, else the legacy
    ``value``, else the type's placeholder."""
    title = field_.get("title")
    kind = field_.get("type") or "text"
    placeholder = _PLACEHOLDERS.get(kind, "No Field Selected")
    if not title:
        value = field_.get("value")
        return value if isinstance(value, str) and value else placeholder
    if isinstance(title, str):
        return title
    text = " ".join(_walk_title(node) for node in _list(_dict(title).get("content"))).strip()
    return text or placeholder


# --------------------------------------------------------------- form structure


def _is_internal(field_: Any) -> bool:
    return bool(_dict(field_).get("internal"))


def is_repeating_group(field_: Any) -> bool:
    field_ = _dict(field_)
    return field_.get("type") == "group" and _dict(field_.get("properties")).get("repeat") is not None


def _clamp_int(value: Any, low: int, high: int, fallback: int) -> int:
    if value is None or value == "" or isinstance(value, bool):
        return fallback
    try:
        number = math.floor(float(value))
    except (TypeError, ValueError, OverflowError):
        return fallback
    return min(high, max(low, number))


@dataclass(frozen=True)
class RepeatSettings:
    max_items: int
    item_label: str
    export_layout: str


def repeat_settings(field_: Dict[str, Any]) -> RepeatSettings:
    repeat = _dict(_dict(field_.get("properties")).get("repeat"))
    max_items = _clamp_int(_get(repeat, "max_items", "maxItems"), 1, REPEAT_MAX_ITEMS_LIMIT, 3)
    layout = _get(repeat, "export_layout", "exportLayout")
    if layout not in ("columns", "rows"):
        layout = "columns" if max_items <= REPEAT_COLUMNS_EXPORT_MAX else "rows"
    label = _get(repeat, "item_label", "itemLabel")
    label = label.strip() if isinstance(label, str) else ""
    return RepeatSettings(max_items=max_items, item_label=label or "Item", export_layout=layout)


def _group_children(group: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [c for c in _list(_dict(group.get("properties")).get("fields")) if isinstance(c, dict)]


def _exportable_children(group: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        c
        for c in _group_children(group)
        if c.get("type") not in ("text", "IMAGE_CONTENT", "VIDEO_CONTENT")
    ]


def form_fields(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The answered questions of the form in page order (``getFormFields``).
    A matrix contributes one field per row, titled ``Matrix[Row]``."""
    provider = _dict(form.get("settings")).get("provider")
    if form.get("builder_version") != "v2":
        if provider == "google":
            return [f for f in _list(form.get("fields")) if isinstance(f, dict) and f.get("type") is not None]
        return []
    fields: List[Dict[str, Any]] = []
    for slide in _list(form.get("fields")):
        for field_ in _list(_dict(_dict(slide).get("properties")).get("fields")):
            if not isinstance(field_, dict):
                continue
            if field_.get("type") in _IGNORED_TYPES or _is_internal(field_):
                continue
            if field_.get("type") != "matrix":
                fields.append(field_)
                continue
            for row in _group_children(field_):
                row_title = row.get("title")
                index = row.get("index")
                label = row_title if _truthy(row_title) else f"Row {(index or 0) + 1}"
                fields.append({**row, "title": f"{field_title(field_)}[{label}]"})
    return fields


def internal_fields(form: Dict[str, Any]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    for slide in _list(form.get("fields")):
        slide = _dict(slide)
        if slide.get("type") == "slide":
            found.extend(f for f in _list(_dict(slide.get("properties")).get("fields")) if _is_internal(f))
        elif _is_internal(slide):
            found.append(slide)
    return found


def column_title(field_: Dict[str, Any], form: Dict[str, Any]) -> str:
    """``getTitleForHeader``."""
    if form.get("builder_version") == "v2":
        return field_title(field_)
    if _dict(form.get("settings")).get("provider") == "google":
        return str(field_.get("title") or "")
    return str(field_.get("value") or "")


# ----------------------------------------------------------------------- answers


def _choice_text(choices: List[Any], chosen: List[Any], other: Any, separator: str) -> str:
    texts = []
    for choice in chosen:
        choice = _dict(choice)
        if _truthy(choice.get("value")):
            texts.append(choice["value"])
            continue
        index = next((i for i, item in enumerate(choices) if _dict(item).get("id") == choice.get("id")), -1)
        texts.append("" if index == -1 else f"Item {index + 1}")
    if _truthy(other):
        texts.append(other)
    return _join(texts, separator)


def _includes(container: Any, item: Any) -> bool:
    """``container.includes(item)`` for a string (a substring) or a list."""
    if isinstance(container, str):
        return isinstance(item, str) and item in container
    if isinstance(container, list):
        return item in container
    return False


def _choices_value(field_: Dict[str, Any], answer: Dict[str, Any], separator: str) -> str:
    properties = _dict(field_.get("properties"))
    choices = properties.get("choices")
    if choices is None:
        return ""
    choices = _list(choices)
    multiple = _truthy(_get(properties, "allow_multiple_selection", "allowMultipleSelection"))
    if multiple:
        values = _dict(answer.get("choices")).get("values")
        chosen = [c for c in choices if _includes(values, _dict(c).get("id"))]
        other = _dict(answer.get("choices")).get("other")
    else:
        value = _dict(answer.get("choice")).get("value")
        chosen = [c for c in choices if _includes(value, _dict(c).get("id"))]
        other = _dict(answer.get("choice")).get("other")
    return _choice_text(choices, chosen, other, separator)


def answer_value(answers: Dict[str, Any], field_: Dict[str, Any], separator: Optional[str] = None) -> Any:
    """What one answer reads as, per question type (``getAnswerForField``).
    ``None`` is an empty cell."""
    answer = _dict(_dict(answers).get(field_.get("id")))
    kind = field_.get("type")
    if kind in ("input_rating", "input_number", "linear_rating", "rating", "number"):
        return answer.get("number")
    if kind in ("short_text", "long_text", "input_short_text", "input_long_text"):
        return answer.get("text")
    if kind in ("url", "input_link"):
        return answer.get("url")
    if kind in ("email", "input_email"):
        return answer.get("email")
    if kind in ("date", "input_date"):
        return answer.get("date")
    if kind == "yes_no":
        flag = answer.get("boolean")
        return "Yes" if flag is True else "No" if flag is False else ""
    if kind in ("multiple_choice", "dropdown"):
        return _choices_value(field_, answer, separator if separator is not None else ",")
    if kind in ("input_multiple_choice", "input_dropdown"):
        choices = _list(_dict(field_.get("properties")).get("choices"))
        value = _dict(answer.get("choice")).get("value")
        if not (isinstance(value, str) and _UUID.fullmatch(value)):
            found = next((c for c in choices if _dict(c).get("value") == value), None)
        else:
            found = next((c for c in choices if _dict(c).get("id") == value), None)
        return _dict(found).get("value") if found is not None else None
    if kind == "input_checkboxes":
        values = _dict(answer.get("choices")).get("values")
        choices = _list(_dict(field_.get("properties")).get("choices"))
        by_id = (
            isinstance(values, list)
            and len(values) > 0
            and all(isinstance(v, str) and _UUID.fullmatch(v) for v in values)
        )
        key = "id" if by_id else "value"
        chosen = [c for c in choices if _includes(values, _dict(c).get(key))]
        return _join((_dict(c).get("value") for c in chosen), separator if separator is not None else ", ")
    if kind in ("phone_number", "input_phone_number"):
        return _get(answer, "phone_number", "phoneNumber")
    if kind == "tabular_input":
        rows = _get(answer, "tabular_value", "tabularValue")
        if isinstance(rows, list):
            return " | ".join(_join(_list(row), ", ") for row in rows)
        return ""
    if kind == "input_ranking":
        values = _dict(answer.get("choices")).get("values")
        if not isinstance(values, list):
            return None
        return _join((_dict(v).get("value") if isinstance(v, dict) else None for v in values), separator if separator is not None else ", ")
    if kind in ("input_file_upload", "file_upload"):
        return _dict(_get(answer, "file_metadata", "fileMetadata")).get("name")
    if kind == "group":
        return ""
    return ""


def calculated_value(answer: Any) -> Any:
    """The value the server computed and stored (``calculatedAnswerValue``)."""
    answer = _dict(answer)
    if _is_number(answer.get("number")):
        return answer["number"]
    if isinstance(answer.get("boolean"), bool):
        return answer["boolean"]
    text = answer.get("text")
    if isinstance(text, str) and text != "":
        return text
    return None


def _group_items(answers: Dict[str, Any], group_id: Any) -> List[Dict[str, Any]]:
    items = _dict(_dict(answers).get(group_id)).get("items")
    if not isinstance(items, list):
        return []
    return [i if isinstance(i, dict) else {} for i in items]


# --------------------------------------------------------------------- the plan


@dataclass
class ExportResponse:
    """One response, decrypted, as the export reads it."""

    response_id: Optional[str]
    responder: Optional[str]
    created_at: Optional[dt.datetime]
    answers: Dict[str, Any]
    internal_answers: Dict[str, Any]
    hidden_fields: Dict[str, Any]


def submitted_at_cell(value: Optional[dt.datetime]) -> str:
    """UTC, ISO 8601, to the second: ``2026-10-01T10:00:00Z``."""
    if not isinstance(value, dt.datetime):
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hidden_value(values: Any, name: str) -> CellValue:
    if not isinstance(values, dict) or name not in values:
        return ""
    value = values[name]
    return value if isinstance(value, str) or _is_number(value) else ""


@dataclass
class Column:
    key: str
    header: str
    kind: str  # responder | question | internal | meta | hidden
    cells: Callable[[ExportResponse], List[CellValue]] = field(repr=False, compare=False)
    # the headers this column writes when it is not just ``header`` (a repeating
    # group writes one per item and question, possibly none)
    headers: Optional[List[str]] = None

    @property
    def all_headers(self) -> List[str]:
        return self.headers if self.headers is not None else [self.header]


@dataclass
class GroupTable:
    """A repeating group exported as a table of its own: one row per item."""

    key: str
    name: str
    headers: List[str]
    rows: Callable[[ExportResponse], List[List[CellValue]]] = field(repr=False, compare=False)


@dataclass
class ExportPlan:
    columns: List[Column]
    group_tables: List[GroupTable]

    @property
    def headers(self) -> List[str]:
        return [h for column in self.columns for h in column.all_headers]

    def row(self, response: ExportResponse) -> List[CellValue]:
        return [value for column in self.columns for value in column.cells(response)]

    def table_names(self) -> List[str]:
        return ["Responses", *(t.name for t in self.group_tables)]


def catalogue(form: Dict[str, Any]) -> List[Column]:
    """Every column of the form's main table, in order."""
    fields = form_fields(form)
    columns: List[Column] = [
        Column(
            key=KEY_RESPONDER,
            header=RESPONDER_ID_COLUMN,
            kind="responder",
            cells=lambda r: [r.responder or ANONYMOUS_LABEL],
        )
    ]
    for field_ in fields:
        columns.append(_question_column(form, field_))
    for field_ in internal_fields(form):
        title = field_title(field_).strip() or "Untitled field"
        header = INTERNAL_COLUMN_PREFIX + title
        columns.append(
            Column(
                key=INTERNAL_PREFIX + str(field_.get("id")),
                header=header,
                kind="internal",
                cells=lambda r, f=field_: [cell(answer_value(r.internal_answers, f, LIST_SEPARATOR))],
            )
        )
    # The response's own data goes at the END of the row. A new header that a
    # question title already uses gets " (2)", so two columns never share a
    # name (computed once, over the headers written so far).
    taken = {h for column in columns for h in column.all_headers}

    def unique(header: str) -> str:
        return f"{header} (2)" if header in taken else header

    hidden_names = list(dict.fromkeys(n for n in _list(form.get("hidden_fields")) if isinstance(n, str)))
    columns.append(
        Column(
            key=KEY_RESPONSE_ID,
            header=unique(RESPONSE_ID_COLUMN),
            kind="meta",
            cells=lambda r: [cell(r.response_id)],
        )
    )
    columns.append(
        Column(
            key=KEY_SUBMITTED_AT,
            header=unique(SUBMITTED_AT_COLUMN),
            kind="meta",
            cells=lambda r: [submitted_at_cell(r.created_at)],
        )
    )
    for name in hidden_names:
        columns.append(
            Column(
                key=HIDDEN_PREFIX + name,
                header=unique(HIDDEN_COLUMN_PREFIX + name),
                kind="hidden",
                cells=lambda r, n=name: [_hidden_value(r.hidden_fields, n)],
            )
        )
    return columns


def _question_column(form: Dict[str, Any], field_: Dict[str, Any]) -> Column:
    key = QUESTION_PREFIX + str(field_.get("id"))
    title = column_title(field_, form)
    if field_.get("type") == "calculated":

        def calculated(r: ExportResponse, f=field_) -> List[CellValue]:
            value = calculated_value(_dict(r.answers).get(f.get("id")))
            return [cell(("Yes" if value else "No") if isinstance(value, bool) else value)]

        return Column(key=key, header=title, kind="question", cells=calculated)
    if not is_repeating_group(field_):
        return Column(
            key=key,
            header=title,
            kind="question",
            cells=lambda r, f=field_: [cell(answer_value(r.answers, f, LIST_SEPARATOR))],
        )
    settings = repeat_settings(field_)
    children = _exportable_children(field_)
    if settings.export_layout == "rows":
        return Column(
            key=key,
            header=f"{title} ({settings.item_label} count)",
            kind="question",
            cells=lambda r, f=field_: [len(_group_items(r.answers, f.get("id")))],
        )
    headers = [
        f"{settings.item_label} {i + 1} – {column_title(child, form)}"
        for i in range(settings.max_items)
        for child in children
    ]

    def per_item(r: ExportResponse, f=field_, kids=children, s=settings) -> List[CellValue]:
        items = _group_items(r.answers, f.get("id"))
        return [
            cell(answer_value(items[i] if i < len(items) else {}, child, LIST_SEPARATOR))
            for i in range(s.max_items)
            for child in kids
        ]

    return Column(key=key, header=headers[0] if headers else title, kind="question", cells=per_item, headers=headers)


def _group_table(form: Dict[str, Any], group: Dict[str, Any]) -> GroupTable:
    settings = repeat_settings(group)
    children = _exportable_children(group)

    def rows(r: ExportResponse) -> List[List[CellValue]]:
        return [
            [
                cell(r.response_id),
                index + 1,
                *(cell(answer_value(item, child, LIST_SEPARATOR)) for child in children),
            ]
            for index, item in enumerate(_group_items(r.answers, group.get("id")))
        ]

    return GroupTable(
        key=QUESTION_PREFIX + str(group.get("id")),
        name=column_title(group, form),
        headers=[RESPONSE_ID_COLUMN, settings.item_label, *(column_title(c, form) for c in children)],
        rows=rows,
    )


def build_plan(form: Dict[str, Any], chosen: Optional[Sequence[str]] = None) -> ExportPlan:
    """The columns (all, or only the ``chosen`` keys, in their usual order) and
    the group tables of a form. ``UnknownColumn`` for a key the form lacks."""
    catalog = catalogue(form)
    tables = {
        QUESTION_PREFIX + str(f.get("id")): _group_table(form, f)
        for f in form_fields(form)
        if is_repeating_group(f) and repeat_settings(f).export_layout == "rows"
    }
    if chosen is None:
        return ExportPlan(columns=catalog, group_tables=list(tables.values()))
    wanted = set(chosen)
    known = {c.key for c in catalog}
    unknown = sorted(wanted - known)
    if unknown:
        raise UnknownColumn(unknown[0])
    if wanted & set(tables):
        wanted.add(KEY_RESPONSE_ID)  # the key a group table joins on
    return ExportPlan(
        columns=[c for c in catalog if c.key in wanted],
        group_tables=[t for k, t in tables.items() if k in wanted],
    )


def column_catalogue(form: Dict[str, Any]) -> List[Dict[str, str]]:
    """The columns a request may choose from: key, label and kind."""
    return [{"key": c.key, "label": c.header, "kind": c.kind} for c in catalogue(form)]


# ------------------------------------------------------------------------- CSV

# JavaScript's ``\s``: Python's differs (it adds the C0 separators and leaves out the BOM)
_JS_SPACE = "\t\n\x0b\x0c\r    -     　﻿"
_NEGATIVE_NUMBER = re.compile(r"-[0-9]+(?:\.[0-9]+)?")
_FORMULA_START = re.compile(rf"[\t\r]|[{_JS_SPACE}]*[=+\-@]")


def formula_safe_cell(value: CellValue) -> CellValue:
    """Spreadsheet apps run cells starting with = + - @ (also after leading
    whitespace) or a tab / CR as formulas. Respondent text must never become
    one: such string cells get a leading ``'``, which spreadsheets treat as
    "this is text". Numbers, and plain negative decimals, are left alone.
    Everything else is prefixed, phone numbers starting with ``+`` included: a
    visible apostrophe keeps the data intact, while a phone number a
    spreadsheet evaluates (``+31-6-1234-5678`` is a subtraction) is corrupted."""
    if not isinstance(value, str):
        return value
    if _NEGATIVE_NUMBER.fullmatch(value):
        return value
    return f"'{value}" if _FORMULA_START.match(value) else value


def csv_line(cells: Iterable[CellValue]) -> str:
    """One RFC 4180 row (no line break), every formula-like cell neutralised."""
    parts = []
    for value in cells:
        text = _text(formula_safe_cell(value)) if value is not None else ""
        if any(ch in text for ch in '",\r\n'):
            text = '"' + text.replace('"', '""') + '"'
        parts.append(text)
    return ",".join(parts)


def export_file_name(form_title: str, table_name: Optional[str] = None, extension: str = "csv") -> str:
    """A file-name-safe name made from the form title (and a table's name)."""

    def safe(text: str) -> str:
        return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", text or "").strip() or "export"

    base = f"{safe(form_title)} - {safe(table_name)}" if table_name else safe(form_title)
    return f"{base}.{extension}"
