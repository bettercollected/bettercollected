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

_LINE_BREAKS = re.compile("\r\n|[\r\u2028\u2029\u0085\u000b\u000c]")
# zero width joiner (U+200D): part of emoji sequences, the one format character kept
_KEEP_FORMAT = {"\u200d"}


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
    format characters (zero width ones; not the zero width joiner of emoji
    sequences), surrogates and private-use code points are dropped. Unassigned
    code points are **kept**: the Unicode data of this Python can be older than
    the sender's emoji and scripts, and a code point it does not know is not
    one it can call dangerous (addresses are stricter, see
    ``copy_recipient.normalize_address``)."""
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
            if category in ("Cc", "Cs", "Co"):
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


def _row(row: Dict[str, Any], language: str) -> str:
    return " / ".join(
        format_value(v, language) for v in row.values() if v not in (None, "", [], {})
    )


def format_value(value: Any, language: str = DEFAULT_LANGUAGE) -> str:
    """An answer as text: a list joined with ``, ``, the items of a repeating
    group one per line (``1. a / b``), a yes/no in the form's language, a currency
    ``EUR 12.50`` and a date range ``2026-01-31/2026-02-03``."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return (_YES if value else _NO).get(language, _YES["en"] if value else _NO["en"])
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if set(value) == {"code", "amount"}:
            # a currency answer: "EUR 12.50", as the export writes it; no amount,
            # nothing to say (a code alone is not an answer)
            if value["amount"] in (None, ""):
                return ""
            return f"{value['code']} {value['amount']}" if value["code"] else str(value["amount"])
        if set(value) == {"start", "end"}:
            # a date range: an ISO 8601 interval, as the export writes it
            return f"{value['start'] or ''}/{value['end'] or ''}"
        return _row(value, language)
    if isinstance(value, (list, tuple)):
        if value and all(isinstance(item, dict) for item in value):
            # an item of a repeating group: a question may be called "start"
            # or "code", so a row is never read as a currency or a range
            return "\n".join(f"{n}. {_row(item, language)}" for n, item in enumerate(value, 1))
        return ", ".join(format_value(item, language) for item in value)
    return str(value)


Entry = Tuple[str, str, Any]  # key, label, value

# ---------------------------------------------- limits of the respondent's copy

# The copy goes to an address a respondent typed, with the creator's question
# labels and the respondent's answers as the only free text. So there it is
# short, and it holds no link: a label or an answer cannot carry a phishing
# page or an advertisement to someone who never asked for it. (The team's mail
# is not limited this way.)
COPY_ITEM_MAX = 200
COPY_ANSWERS_MAX = 2000
LINK_REMOVED = "[link removed]"
# whole email addresses are left alone (a respondent's own address in their own
# copy); then a scheme (``https://``, ``mailto:``...), ``www.``, or a bare
# ``name.tld`` with an optional path
_EMAIL = r"[\w.+-]+@(?:[\w-]+\.)+[A-Za-z]{2,}"
_LINK = re.compile(
    rf"(?P<email>{_EMAIL})"
    r"|(?P<link>\b(?:[A-Za-z][A-Za-z0-9+.-]*://|(?:mailto|tel|sms|javascript|data|file):)\S*"
    r"|\bwww\.\S*"
    r"|(?<![\w@.-])(?:[\w-]+\.)+[A-Za-z]{2,}(?:[/:?#]\S*)?)",
    re.IGNORECASE,
)


def defang_links(text: str) -> str:
    """``text`` with anything URL-like (``scheme://...``, ``www....``, a bare
    ``domain.tld/path``) replaced by ``[link removed]``. Email addresses stay."""
    return _LINK.sub(lambda m: m.group(0) if m.group("email") else LINK_REMOVED, text)


# NFKC turns the fullwidth full stop (U+FF0E), the small full stop (U+FE52) and the
# one-dot leader (U+2024) into ``.``, and the halfwidth ideographic full stop
# (U+FF61) into the ideographic one (U+3002), which it leaves alone: so that one,
# and its twin, are mapped by hand
_DOTS = {ord("\u3002"): ".", ord("\uff61"): "."}


def copy_item(text: str, *, multiline: bool) -> str:
    """One label or answer as the respondent's copy shows it: cut to
    ``COPY_ITEM_MAX``, normalised to NFKC (the copy is plain text, so
    compatibility forms such as fullwidth letters, dots and slashes become the
    plain ones a link search can see), links removed, cut again (the
    normalisation can lengthen a text, the replacement is longer than a dot)."""
    # the cut comes before everything else, so the search reads at most
    # COPY_ITEM_MAX characters (a long answer is not even cleaned whole)
    text = (multi_line if multiline else one_line)(str(text)[:VALUE_MAX], COPY_ITEM_MAX)
    text = unicodedata.normalize("NFKC", text).translate(_DOTS)
    return truncate(defang_links(text), COPY_ITEM_MAX)


def copy_answers_block(entries: Sequence[Entry], language: str = DEFAULT_LANGUAGE) -> str:
    """The respondent's copy of ``answers_block``: every label and answer cut
    to ``COPY_ITEM_MAX`` characters (with an ellipsis), normalised and
    link-free (``copy_item``), the whole block to ``COPY_ANSWERS_MAX``."""
    lines = []
    for _key, label, value in entries:
        name = copy_item(label, multiline=False)
        text = copy_item(format_value(value, language), multiline=True).replace("\n", "\n  ")
        lines.append(f"{name}: {text}".rstrip())
    return truncate("\n".join(lines), COPY_ANSWERS_MAX)


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
    if not subject:
        # a multi-line answer is indented after its first line, so no line of
        # it can pass for a line of the template or of the answers block
        values = {key: value.replace("\n", "\n  ") for key, value in values.items()}
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
        return subject_line(filled)
    return multi_line(filled, MESSAGE_MAX)


def subject_line(value: Any) -> str:
    """A subject: one line, capped, and no literal encoded word (``=?utf-8?q?..?=``)
    that a mail client could decode into something else than what was typed."""
    return one_line(value, SUBJECT_MAX).replace("=?", "= ?")


# ----------------------------------------------- the respondent's own copy

# Fixed wording: apart from the question labels, nothing a creator wrote goes to
# an address a respondent gave, and labels and answers are cut and link-free
# there (``copy_answers_block``).
RESPONDENT_TEXT = {
    "en": {
        "subject": "A copy of your submission",
        "intro": "This is the copy of your submission.",
        "why": (
            "You get this message because this address was entered in the form. "
            "If that was not you, you can ignore it: nothing else will be sent."
        ),
        "answers": "Your answers:",
        "when": "Submitted: {when}",
    },
    "nl": {
        "subject": "Een kopie van uw inzending",
        "intro": "Dit is de kopie van uw inzending.",
        "why": (
            "U ontvangt dit bericht omdat dit e-mailadres in het formulier is ingevuld. "
            "Was u dit niet, dan kunt u het negeren: er wordt verder niets gestuurd."
        ),
        "answers": "Uw antwoorden:",
        "when": "Ingediend: {when}",
    },
}


def render_respondent(
    entries: Sequence[Entry], *, submitted_at: str, language: str
) -> Tuple[str, str]:
    """``(subject, body)`` of the copy a respondent gets of their own
    submission: fixed wording in the form's language and the mapped questions'
    answers (their own, each capped) under their question labels. Nothing a
    creator wrote besides those labels: no template, **no form title**."""
    words = RESPONDENT_TEXT.get(language, RESPONDENT_TEXT[DEFAULT_LANGUAGE])
    parts = [words["intro"], "", words["why"]]
    if entries:
        parts += ["", words["answers"], copy_answers_block(entries, language)]
    if submitted_at:
        parts += ["", words["when"].format(when=one_line(submitted_at, 40))]
    return words["subject"], multi_line("\n".join(parts), MESSAGE_MAX)
