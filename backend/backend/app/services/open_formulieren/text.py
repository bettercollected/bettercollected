"""Plain text from the file's strings.

Every text that comes out of an archive (labels, help, option texts, html
blocks, names) is reduced to plain text here before it is used for anything:
tags and attributes are dropped, entities decoded, control and formatting
characters removed, lengths capped. Nothing is ever stored or sent as markup,
and template syntax is left as the literal text it is (never rendered).
"""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from typing import Any, List, Tuple

_BLOCK = {
    "p", "div", "br", "li", "ul", "ol", "tr", "table", "h1", "h2", "h3", "h4",
    "h5", "h6", "blockquote", "section", "article", "hr", "pre",
}
_SKIP = {"script", "style", "template", "iframe", "object", "embed", "noscript"}
# unicode categories that never belong in a label: control (but newline),
# format (zero width, bidi override), surrogates, private use, unassigned
_DROP_CATEGORIES = {"Cc", "Cf", "Cs", "Co", "Cn"}


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip = 0
        self.markup = False

    def handle_starttag(self, tag, attrs):
        self.markup = True
        if tag in _SKIP:
            self._skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        self.markup = True
        if tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        self.markup = True
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _clean(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    out = []
    for ch in text:
        if ch == "\n":
            out.append("\n")
        elif ch in "\t\r\f\v  ":
            out.append(" ")
        elif unicodedata.category(ch) not in _DROP_CATEGORIES:
            out.append(ch)
    text = "".join(out)
    text = re.sub(r"[  ]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def plain_text(value: Any, limit: int) -> Tuple[str, bool]:
    """``(text, had_markup)``: ``value`` as plain text of at most ``limit``
    characters. ``had_markup`` tells that html tags were removed (so the
    report can say the text was simplified). Non-strings give ``""``."""
    if not isinstance(value, str) or not value:
        return "", False
    # a huge string is cut before the parser sees it
    value = value[: max(limit * 8, 4096)]
    markup = False
    if "<" in value or "&" in value:
        collector = _Collector()
        try:
            collector.feed(value)
            collector.close()
            value = "".join(collector.parts)
            markup = collector.markup
        except Exception:  # noqa: BLE001 — malformed markup: keep the text as it is
            markup = True
            value = re.sub(r"<[^>]*>", " ", value)
    text = _clean(value)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text, markup


def label_text(value: Any, limit: int) -> str:
    """A single-line label: plain text with line breaks as spaces."""
    text, _ = plain_text(value, limit)
    return re.sub(r"\s+", " ", text).strip()


def for_report(value: Any, limit: int) -> str:
    """Text for a report entry (a key or a label): single line, plain."""
    return label_text(value, limit)
