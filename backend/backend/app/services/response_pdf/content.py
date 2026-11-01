"""What the PDF of one submission says: the form's title, when and by whom it
was answered, and every question of the form version the response was made
against with its answer, in the text the CSV export uses (``response_export/table.py``
is the single reading of an answer).

Not printed: the form's internal (staff-only) fields and staff feedback, the
image of a drawn signature (the API process never decodes images:
``services/signatures.py``) and any link to a stored file. A file is listed by
name and size.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

from backend.app.services.response_export.table import (
    ExportResponse,
    _dict,
    _exportable_children,
    _group_items,
    answer_value,
    calculated_value,
    column_title,
    form_fields,
    is_repeating_group,
    number_text,
    repeat_settings,
)
from backend.app.services.response_pdf import labels
from backend.app.services.response_pdf.render import (
    MAX_VALUE_CHARS,
    Entry,
    PdfDocument,
    Section,
)

# one answer per line for the choices of a multiple-choice question and the like
LIST_LINES = "\n"
_FILE_TYPES = ("input_file_upload", "file_upload")


def _size(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return ""
    if value < 1000:
        return f"{int(value)} B"
    for unit, step in (("KB", 1e3), ("MB", 1e6), ("GB", 1e9)):
        if value < step * 1000 or unit == "GB":
            number = value / step
            return f"{number:.0f} {unit}" if number >= 10 else f"{number:.1f} {unit}"
    return ""


def _parse_time(value: Any) -> Optional[dt.datetime]:
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _text_of(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return number_text(value)
    return str(value)


def answer_text(field_: Dict[str, Any], answers: Dict[str, Any], lang: str, tz: dt.tzinfo) -> str:
    """The answer to one question as text ("" when there is none)."""
    words = labels.LABELS[lang]
    kind = field_.get("type")
    answer = _dict(_dict(answers).get(field_.get("id")))
    if kind == "calculated":
        value = calculated_value(answer)
        return words["yes" if value else "no"] if isinstance(value, bool) else _text_of(value)
    if kind == "yes_no":
        flag = answer.get("boolean")
        return words["yes"] if flag is True else words["no"] if flag is False else ""
    if kind == "signature":
        signature = _dict(answer.get("signature"))
        if signature.get("method") == "typed":
            name = signature.get("name")
            return f"{name}\n{words['typed_signature']}" if isinstance(name, str) and name else ""
        if signature.get("method") == "drawn":
            text = words["drawn_signature"]
            signed = _parse_time(signature.get("signed_at") or signature.get("signedAt"))
            if signed is not None:
                text += "\n" + words["signed_at"].format(time=labels.when(signed, lang, tz))
            return text
        return ""
    if kind in _FILE_TYPES:
        meta = _dict(answer.get("file_metadata") or answer.get("fileMetadata"))
        name = meta.get("name")
        if not isinstance(name, str) or not name:
            return ""
        size = _size(meta.get("size"))
        return f"{name} ({size})" if size else name
    return _text_of(answer_value(answers, field_, LIST_LINES))


def _capped(text: str, lang: str) -> str:
    if len(text) <= MAX_VALUE_CHARS:
        return text
    return text[:MAX_VALUE_CHARS] + "\n" + labels.LABELS[lang]["shortened"]


def question_entry(
    field_: Dict[str, Any], answers: Dict[str, Any], form: Dict[str, Any], lang: str, tz: dt.tzinfo
) -> Optional[Entry]:
    """One question with its answer; ``None`` for what holds no answer (a group
    that is not repeating)."""
    words = labels.LABELS[lang]
    title = column_title(field_, form).strip() or words["untitled"]
    if field_.get("type") == "group" and not is_repeating_group(field_):
        return None
    if is_repeating_group(field_):
        settings = repeat_settings(field_)
        items = _group_items(answers, field_.get("id"))
        if not items:
            return Entry(title, words["no_answer"], muted=True)
        children = _exportable_children(field_)
        nested: List[Entry] = []
        for index, item in enumerate(items):
            parts = [e for e in (question_entry(c, item, form, lang, tz) for c in children) if e is not None]
            nested.append(Entry(f"{settings.item_label} {index + 1}", parts))
        return Entry(title, nested)
    text = answer_text(field_, answers, lang, tz)
    if not text.strip():
        return Entry(title, words["no_answer"], muted=True)
    return Entry(title, _capped(text, lang))


def build_document(
    form: Dict[str, Any],
    response: ExportResponse,
    language: Optional[str] = None,
    time_zone: Optional[str] = None,
) -> PdfDocument:
    """The document for one decrypted response of ``form`` (the version it was
    answered on), in the viewer's language and time zone."""
    lang = labels.language(language)
    tz = labels.zone(time_zone)
    words = labels.LABELS[lang]
    title = str(form.get("title") or "").strip() or words["untitled"]
    facts = [
        Entry(words["submitted"], labels.when(response.created_at, lang, tz)),
        Entry(words["responder"], response.responder or words["anonymous"]),
        Entry(words["response_id"], str(response.response_id or "")),
    ]
    if response.form_version is not None:
        facts.append(Entry(words["form_version"], str(response.form_version)))
    hidden = _dict(response.hidden_fields)
    for name in dict.fromkeys(form.get("hidden_fields") or []):
        value = hidden.get(name) if isinstance(name, str) else None
        if isinstance(name, str) and isinstance(value, (str, int, float)) and not isinstance(value, bool) and value != "":
            facts.append(Entry(name, _capped(_text_of(value), lang)))
    entries = [
        e
        for e in (question_entry(f, response.answers, form, lang, tz) for f in form_fields(form))
        if e is not None
    ]
    return PdfDocument(
        lang=lang,
        title=words["response_to"].format(title=title),
        facts=facts,
        sections=[Section(words["answers"], entries)],
        footer=title,
        page_label=words["page"],
        info_title=f"{words['response']}: {title}",
    )
