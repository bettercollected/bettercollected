"""Plain text from the file's strings.

Every text that comes out of an archive (labels, help, option texts, html
blocks, names) is reduced to plain text here before it is used for anything:
tags and attributes are dropped (by a linear scan, never an HTML parser), entities decoded, control and formatting
characters removed, lengths capped. Nothing is ever stored or sent as markup,
and template syntax is left as the literal text it is (never rendered).
"""

from __future__ import annotations

import html
import re
import unicodedata
from typing import Any, List, Tuple

from backend.app.services.open_formulieren import budget

_BLOCK = frozenset(
    {
        "p", "div", "br", "li", "ul", "ol", "tr", "table", "h1", "h2", "h3", "h4",
        "h5", "h6", "blockquote", "section", "article", "hr", "pre",
    }
)
# elements whose content is dropped with them
_SKIP = frozenset(
    {"script", "style", "template", "iframe", "object", "embed", "noscript"}
)
_TAG_NAME = re.compile(r"(/?)([A-Za-z][A-Za-z0-9]{0,15})")
# unicode categories that never belong in a label: control (but newline),
# format (zero width, bidi override), surrogates, private use, unassigned
_DROP_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn"}


def strip_tags(value: str) -> Tuple[str, bool]:
    """``value`` without markup, and whether there was any. One pass: every
    step moves past what it looked at, so the time is linear in the length
    whatever the input (an unterminated tag, comment or element ends the
    text instead of being searched for again at every ``<``)."""
    out: List[str] = []
    lower = value.lower()
    size = len(value)
    pos = 0
    markup = False
    while pos < size:
        start = value.find("<", pos)
        if start < 0:
            out.append(value[pos:])
            break
        out.append(value[pos:start])
        if value.startswith("<!--", start):
            markup = True
            end = value.find("-->", start + 4)
            if end < 0:
                break
            pos = end + 3
            continue
        match = _TAG_NAME.match(value, start + 1)
        if match is None:
            # "a < b", "<>", "<3": not a tag, kept as text
            out.append("<")
            pos = start + 1
            continue
        markup = True
        close = value.find(">", start)
        if close < 0:
            break  # an unterminated tag: nothing after it is text
        name = match.group(2).lower()
        if match.group(1):
            if name in _BLOCK:
                out.append("\n")
            pos = close + 1
        elif name in _SKIP:
            end = lower.find("</" + name, close)
            if end < 0:
                break
            after = value.find(">", end)
            if after < 0:
                break
            pos = after + 1
        else:
            if name in _BLOCK:
                out.append("\n")
            pos = close + 1
    return "".join(out), markup


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    out = []
    for ch in text:
        if ch == "\n":
            out.append("\n")
        elif ch in "\t\r\f\v\u2028\u2029":
            out.append(" ")
        elif unicodedata.category(ch) not in _DROP_CATEGORIES:
            out.append(ch)
    text = "".join(out)
    text = re.sub(r"[ \u00a0]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def plain_text(value: Any, limit: int) -> Tuple[str, bool]:
    """``(text, had_markup)``: ``value`` as plain text of at most ``limit``
    characters. ``had_markup`` tells that html tags were removed (so the
    report can say the text was simplified). Non-strings give ``""``. The
    input is cut to twice the limit before anything is done with it, and
    what is processed counts against the import's budget."""
    if not isinstance(value, str) or not value:
        return "", False
    value = value[: max(limit * 2, 64)]
    budget.charge(len(value))
    markup = False
    if "<" in value:
        value, markup = strip_tags(value)
    if "&" in value:
        value = html.unescape(value)
    text = _clean(value)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "\u2026"
    return text, markup


def label_text(value: Any, limit: int) -> str:
    """A single-line label: plain text with line breaks as spaces."""
    text, _ = plain_text(value, limit)
    return re.sub(r"\s+", " ", text).strip()


def for_report(value: Any, limit: int) -> str:
    """Text for a report entry (a key or a label): single line, plain."""
    return label_text(value, limit)
