"""The words of an email action: templates, placeholders and the rules that keep
what a respondent typed from ever becoming markup, a header or a template.

Pure functions. The mail is **plain text**, never HTML, so an answer is text
and nothing else. A template has ``{{key}}`` placeholders, no other syntax:

- ``{{key}}`` the answer to a mapped question (``key`` is the name the action
  gave it, ``^[A-Za-z_][A-Za-z0-9_]{0,63}$``);
- ``{{form_title}}``, ``{{submitted_at}}``, and in the body only ``{{answers}}``,
  one ``Question: answer`` line per mapped question.

A placeholder that is not one of those, or a ``{{`` / ``}}`` that is not part of
one, is refused when the action is saved. Rendering is **one pass**: a value
inserted is never read again, so an answer that contains ``{{...}}`` stays the
text it is. Every value is cleaned (control characters, line separators and
bidirectional overrides removed), capped, and for the **subject** collapsed to
one line, so no value can add a header line. Pure data in, text out: nothing
here logs, sends or keeps what it is given.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]{0,63})\s*\}\}")
BUILT_INS_SUBJECT = ("form_title", "submitted_at")
BUILT_INS_BODY = ("form_title", "submitted_at", "answers")

SUBJECT_MAX = 200
BODY_MAX = 10_000
# one inserted value, in the body and in the subject
VALUE_MAX = 2000
SUBJECT_VALUE_MAX = 200
# a whole message
MESSAGE_MAX = 20_000
TITLE_MAX = 120
LABEL_MAX = 200
LANGUAGES = ("en", "nl")
DEFAULT_LANGUAGE = "en"

_LINE_BREAKS = re.compile(r"\r\n|[\r  \u0085\u000b\u000c]")
_KEEP_FORMAT = {"‍"}  # zero width joiner: part of emoji sequences


def language_of(form: Any) -> str:
    """``nl`` for a form written in Dutch (``nl``, ``nl-BE``...), else ``en``."""
    settings = getattr(form, "settings", None)
    if isinstance(form, dict):
        settings = form.get("settings")
    tag = (
        settings.get("language")
        if isinstance(settings, dict)
        else getattr(settings, "language", None)
    )
    if isinstance(tag, str) and tag.strip().lower().split("-")[0] == "nl":
        return "nl"
    return DEFAULT_LANGUAGE


def clean(value: Any, *, multiline: bool) -> str:
    """``value`` as text with nothing that could break a line, a header or the
    reader's screen: line breaks become ``\\n`` (a space when not ``multiline``),
    tabs a space, other control characters, bidirectional overrides, zero width
    characters and unassigned or private code points are dropped."""
    text = "" if value is None else str(value)
    text = _LINE_BREAKS.sub("\n", text)
    out: List[str] = []
    for ch in text:
        if ch == "\n":
            out.append("\n" if multiline else " ")
        elif ch == "\t":
            out.append(" ")
        else:
            category = unicodedata.category(ch)
            if category in ("Cc", "Cs", "Co", "Cn"):
                continue
            if category == "Cf" and ch not in _KEEP_FORMAT:
                continue
            out.append(ch)
    return "".join(out)


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


def one_line(value: Any, limit: int) -> str:
    """One line: all whitespace runs (line breaks included) become one space."""
    return truncate(" ".join(clean(value, multiline=False).split()), limit)


def multi_line(value: Any, limit: int) -> str:
    """Several lines, no more than one blank line in a row, no trailing space."""
    text = "\n".join(line.rstrip() for line in clean(value, multiline=True).split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
    return truncate(text, limit)


# ------------------------------------------------------------------ checks


def placeholder_problem(
    text: str, allowed: Iterable[str]
) -> Optional[Tuple[str, Optional[str]]]:
    """``(code, name)`` of the first thing wrong with a template, or None:
    ``unknown_placeholder`` (a name that is not mapped nor built in) or
    ``invalid_placeholder`` (braces that are not a placeholder)."""
    known = set(allowed)
    for name in PLACEHOLDER.findall(text):
        if name not in known:
            return "unknown_placeholder", name
    rest = PLACEHOLDER.sub("", text)
    if "{{" in rest or "}}" in rest:
        return "invalid_placeholder", None
    return None


def used_placeholders(text: str) -> List[str]:
    return PLACEHOLDER.findall(text)


# ------------------------------------------------------------------ values

_YES = {"en": "Yes", "nl": "Ja"}
_NO = {"en": "No", "nl": "Nee"}


def format_value(value: Any, language: str = DEFAULT_LANGUAGE) -> str:
    """An answer as text: a list joined with ``, ``, the items of a repeating
    group one per line (``1. a / b``), a yes/no in the form's language."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return (_YES if value else _NO).get(language, _YES["en"] if value else _NO["en"])
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " / ".join(format_value(v, language) for v in value.values() if v not in (None, ""))
    if isinstance(value, (list, tuple)):
        if value and all(isinstance(item, dict) for item in value):
            return "\n".join(
                f"{n}. {format_value(item, language)}" for n, item in enumerate(value, 1)
            )
        return ", ".join(format_value(item, language) for item in value)
    return str(value)


Entry = Tuple[str, str, Any]  # key, label, value


def answers_block(entries: Sequence[Entry], language: str = DEFAULT_LANGUAGE) -> str:
    """One ``Label: answer`` line per question; the lines of a long answer are
    indented, so one answer is never read as two."""
    lines = []
    for _key, label, value in entries:
        text = multi_line(format_value(value, language), VALUE_MAX).replace("\n", "\n  ")
        lines.append(f"{one_line(label, LABEL_MAX)}: {text}".rstrip())
    return "\n".join(lines)


# ------------------------------------------------------------------- render


def _values_for(
    entries: Sequence[Entry],
    form_title: str,
    submitted_at: str,
    language: str,
    *,
    subject: bool,
) -> Dict[str, str]:
    limit = SUBJECT_VALUE_MAX if subject else VALUE_MAX
    cap = (lambda v: one_line(v, limit)) if subject else (lambda v: multi_line(v, limit))
    values = {key: cap(format_value(value, language)) for key, _label, value in entries}
    values["form_title"] = one_line(form_title, TITLE_MAX)
    values["submitted_at"] = one_line(submitted_at, 40)
    if not subject:
        values["answers"] = answers_block(entries, language)
    return values


def render(
    template: str,
    entries: Sequence[Entry],
    *,
    form_title: str,
    submitted_at: str,
    language: str,
    subject: bool,
) -> str:
    """The template with its placeholders filled in, in one pass. A placeholder
    with no value (a question the form no longer has) is empty."""
    values = _values_for(entries, form_title, submitted_at, language, subject=subject)
    filled = PLACEHOLDER.sub(lambda m: values.get(m.group(1), ""), template)
    if subject:
        return one_line(filled, SUBJECT_MAX)
    return multi_line(filled, MESSAGE_MAX)


# ----------------------------------------------- the respondent's own copy

# Fixed wording: nothing a creator wrote goes to an address a respondent gave.
RESPONDENT_TEXT = {
    "en": {
        "subject": "A copy of your submission",
        "intro": 'This is the copy of your submission to the form "{title}".',
        "why": (
            "You get this message because this address was entered in the form. "
            "If that was not you, you can ignore it: nothing else will be sent."
        ),
        "answers": "Your answers:",
        "when": "Submitted: {when}",
    },
    "nl": {
        "subject": "Een kopie van uw inzending",
        "intro": 'Dit is de kopie van uw inzending voor het formulier "{title}".',
        "why": (
            "U ontvangt dit bericht omdat dit e-mailadres in het formulier is ingevuld. "
            "Was u dit niet, dan kunt u het negeren: er wordt verder niets gestuurd."
        ),
        "answers": "Uw antwoorden:",
        "when": "Ingediend: {when}",
    },
}


def render_respondent(
    entries: Sequence[Entry], *, form_title: str, submitted_at: str, language: str
) -> Tuple[str, str]:
    """``(subject, body)`` of the copy a respondent gets of their own
    submission: fixed wording in the form's language, the form's title on one
    line, and the mapped questions' answers (their own, each capped)."""
    words = RESPONDENT_TEXT.get(language, RESPONDENT_TEXT[DEFAULT_LANGUAGE])
    title = one_line(form_title, TITLE_MAX)
    parts = [words["intro"].format(title=title), "", words["why"]]
    if entries:
        parts += ["", words["answers"], answers_block(entries, language)]
    if submitted_at:
        parts += ["", words["when"].format(when=one_line(submitted_at, 40))]
    return words["subject"], multi_line("\n".join(parts), MESSAGE_MAX)
