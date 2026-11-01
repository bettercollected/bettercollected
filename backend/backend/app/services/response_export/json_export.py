"""The export as one JSON document, written as a stream.

::

    {"form": {"id", "title"},
     "questions": [{"key", "id", "title", "type", "choices": [{"id", "label"}], "fields": [...]}],
     "responses": [{"responseId", "submittedAt", "formVersion", "responder",
                    "answers": {"<question id>": <answer>},
                    "internalAnswers": {...}, "hiddenFields": {...}}]}

It is close to the REST API's representation of a response (``responseId``,
``submittedAt``, ``answers`` keyed by question id with the stored answer
objects, ``internalAnswers``): the same names and the same answer objects. The
differences: ``submittedAt`` ends in ``Z`` (the CSV's form) where the API writes
``+00:00``; ``responder``, ``internalAnswers`` and ``hiddenFields`` appear when
their columns are chosen (the API never returns who answered); ``formVersion``
and ``questions`` are added; links to stored files are removed.
``questions`` says what each id is (without it a choice answer is an opaque id);
a repeating group stays nested (``{"items": [{<child id>: <answer>}]}``), the
``rows``/``columns`` layout being a spreadsheet matter.

The selected columns decide what is written: a question, internal field or
hidden field only when its column is chosen, ``responder`` only with the
responder column. ``responseId`` and ``submittedAt`` always identify a row.

Links never leave, as in the CSV ("never the image or a link to it"): an
answer's ``file_url``, a file's ``url`` and a drawn signature's ``file_id`` and
``url`` are removed. The rest is the stored answer, without its empty values.

Memory stays at one response: the head, then each response after a comma, then
the tail, over the same pass over the responses as the other formats.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.app.services.response_export.table import (
    HIDDEN_PREFIX,
    INTERNAL_PREFIX,
    KEY_RESPONDER,
    QUESTION_PREFIX,
    Column,
    ExportPlan,
    ExportResponse,
    _dict,
    _exportable_children,
    column_title,
    field_title,
    is_repeating_group,
    submitted_at_cell,
)
from backend.app.services.response_export.writer import RowCount, ResponseSource

JSON_MEDIA_TYPE = "application/json; charset=utf-8"

# answer parts that point at stored files: never exported
_LINK_KEYS = ("file_url", "fileUrl")
_FILE_KEYS = ("file_metadata", "fileMetadata")
_FILE_LINK = ("url",)
_SIGNATURE_FILE = ("file_id", "fileId", "url")
_SURROGATES = {c: "�" for c in range(0xD800, 0xE000)}


def _text(value: str) -> str:
    """No lone surrogate (UTF-8 cannot encode one)."""
    return value.translate(_SURROGATES)


def clean_value(value: Any) -> Any:
    """JSON-safe data: text without lone surrogates, no ``NaN``/``Infinity``, no
    ``None`` in a mapping."""
    if isinstance(value, str):
        return _text(value)
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    if isinstance(value, dict):
        return {_text(str(k)): clean_value(v) for k, v in value.items() if v is not None}
    if isinstance(value, (list, tuple)):
        return [clean_value(v) for v in value]
    return value


def clean_answer(answer: Any) -> Any:
    """A stored answer as exported: without any link to a stored file."""
    if not isinstance(answer, dict):
        return clean_value(answer)
    out: Dict[str, Any] = {}
    for key, value in answer.items():
        if key in _LINK_KEYS or value is None:
            continue
        if key in _FILE_KEYS and isinstance(value, dict):
            value = {k: v for k, v in value.items() if k not in _FILE_LINK}
        elif key == "signature" and isinstance(value, dict):
            value = {k: v for k, v in value.items() if k not in _SIGNATURE_FILE}
        elif key == "items" and isinstance(value, list):
            value = [
                {str(k): clean_answer(v) for k, v in _dict(item).items()} for item in value
            ]
        out[key] = clean_value(value)
    return out


def _answers(selected: List[str], answers: Any) -> Dict[str, Any]:
    source = _dict(answers)
    return {
        _text(str(key)): clean_answer(source[key])
        for key in selected
        if key in source and source[key] is not None
    }


def question_description(field_: Dict[str, Any], form: Dict[str, Any], internal: bool = False) -> Dict[str, Any]:
    """What one question is: id, title, type and, for a choice question, its options."""
    described: Dict[str, Any] = {
        "id": field_.get("id"),
        "title": _text(column_title(field_, form) if not internal else field_title(field_)),
        "type": field_.get("type"),
    }
    if internal:
        described["internal"] = True
    choices = _dict(field_.get("properties")).get("choices")
    if isinstance(choices, list):
        described["choices"] = [
            {"id": _dict(c).get("id"), "label": _text(str(_dict(c).get("value") or ""))}
            for c in choices
            if isinstance(c, dict)
        ]
    if is_repeating_group(field_):
        described["fields"] = [question_description(child, form) for child in _exportable_children(field_)]
    return clean_value(described)


class JsonPlan:
    """What the selected columns ask of every response."""

    def __init__(self, plan: ExportPlan, form: Dict[str, Any]):
        self.form = form
        self.responder = any(c.key == KEY_RESPONDER for c in plan.columns)
        self.question_ids = [
            str(c.source_field.get("id")) for c in plan.columns if c.key.startswith(QUESTION_PREFIX) and c.source_field
        ]
        self.internal_ids = [
            str(c.source_field.get("id")) for c in plan.columns if c.key.startswith(INTERNAL_PREFIX) and c.source_field
        ]
        self.hidden_names = [c.key[len(HIDDEN_PREFIX) :] for c in plan.columns if c.key.startswith(HIDDEN_PREFIX)]
        self.questions: List[Dict[str, Any]] = [
            *(
                question_description(c.source_field, form)
                for c in plan.columns
                if c.key.startswith(QUESTION_PREFIX) and c.source_field
            ),
            *(
                question_description(c.source_field, form, internal=True)
                for c in plan.columns
                if c.key.startswith(INTERNAL_PREFIX) and c.source_field
            ),
        ]

    def head(self) -> str:
        form = {
            "id": _text(str(self.form.get("form_id") or self.form.get("id") or "")),
            "title": _text(str(self.form.get("title") or "")),
        }
        return (
            '{"form":'
            + _dumps(form)
            + ',"questions":'
            + _dumps(self.questions)
            + ',"responses":['
        )

    def response(self, response: ExportResponse) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "responseId": response.response_id,
            "submittedAt": submitted_at_cell(response.created_at) or None,
            "formVersion": response.form_version,
        }
        if self.responder:
            item["responder"] = _text(response.responder) if response.responder else None
        if self.question_ids:
            item["answers"] = _answers(self.question_ids, response.answers)
        if self.internal_ids:
            item["internalAnswers"] = _answers(self.internal_ids, response.internal_answers)
        if self.hidden_names:
            hidden = _dict(response.hidden_fields)
            item["hiddenFields"] = {
                _text(n): clean_value(hidden[n]) for n in self.hidden_names if n in hidden and hidden[n] is not None
            }
        return item


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


async def write_json(
    plan: ExportPlan,
    form: Dict[str, Any],
    source: ResponseSource,
    counter: Optional[RowCount] = None,
    piece_bytes: int = 64 * 1024,
) -> AsyncIterator[bytes]:
    """The document's bytes. ``counter`` counts the responses written."""
    shape = JsonPlan(plan, form)
    buffered: List[str] = [shape.head()]
    size = len(buffered[0])
    first = True
    async for response in source():
        text = ("" if first else ",") + _dumps(shape.response(response))
        first = False
        buffered.append(text)
        size += len(text)
        if counter is not None:
            counter.rows += 1
        if size >= piece_bytes:
            yield "".join(buffered).encode("utf-8")
            buffered, size = [], 0
    buffered.append("]}")
    yield "".join(buffered).encode("utf-8")
