"""The words and dates of the PDF of one submission, in the viewer's language
(``en`` or ``nl``) and time zone. The question titles and answers are the
form's own and are never translated."""

from __future__ import annotations

import datetime as dt
from typing import Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_LANG = "en"
LANGUAGES = ("en", "nl")
TZ_MAX_CHARS = 64

LABELS: Dict[str, Dict[str, str]] = {
    "en": {
        "response_to": "Response to {title}",
        "untitled": "Untitled form",
        "submitted": "Submitted",
        "responder": "Responder",
        "anonymous": "Anonymous",
        "response_id": "Response ID",
        "form_version": "Form version",
        "answers": "Answers",
        "no_answer": "No answer",
        "yes": "Yes",
        "no": "No",
        "typed_signature": "Typed signature",
        "drawn_signature": "Drawn signature (image not included)",
        "signed_at": "signed {time}",
        "shortened": "[shortened]",
        "page": "Page {n} of {total}",
        "response": "Response",
    },
    "nl": {
        "response_to": "Antwoord op {title}",
        "untitled": "Formulier zonder titel",
        "submitted": "Ingediend",
        "responder": "Respondent",
        "anonymous": "Anoniem",
        "response_id": "Antwoord-ID",
        "form_version": "Formulierversie",
        "answers": "Antwoorden",
        "no_answer": "Geen antwoord",
        "yes": "Ja",
        "no": "Nee",
        "typed_signature": "Getypte handtekening",
        "drawn_signature": "Getekende handtekening (afbeelding niet opgenomen)",
        "signed_at": "ondertekend {time}",
        "shortened": "[ingekort]",
        "page": "Pagina {n} van {total}",
        "response": "Antwoord",
    },
}

_MONTHS = {
    "en": [
        "January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December",
    ],
    "nl": [
        "januari", "februari", "maart", "april", "mei", "juni", "juli",
        "augustus", "september", "oktober", "november", "december",
    ],
}


def language(value: Optional[str]) -> str:
    """``en`` or ``nl``: the primary subtag of what the viewer sent, else ``en``."""
    primary = (value or "").strip().lower().replace("_", "-").split("-")[0]
    return primary if primary in LANGUAGES else DEFAULT_LANG


def zone(name: Optional[str]) -> dt.tzinfo:
    """The viewer's IANA time zone, UTC when it is missing, too long or unknown."""
    if not name or len(name) > TZ_MAX_CHARS or not all(c.isalnum() or c in "/_+-" for c in name):
        return dt.timezone.utc
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return dt.timezone.utc


def when(value: Optional[dt.datetime], lang: str, tz: dt.tzinfo) -> str:
    """``1 November 2026, 22:41 (CET)`` / ``1 november 2026 om 22:41 (CET)``."""
    if not isinstance(value, dt.datetime):
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.timezone.utc)
    local = value.astimezone(tz)
    month = _MONTHS[lang][local.month - 1]
    joiner = " om " if lang == "nl" else ", "
    name = local.tzname() or "UTC"
    return f"{local.day} {month} {local.year}{joiner}{local:%H:%M} ({name})"
