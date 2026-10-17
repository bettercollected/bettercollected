"""Style values in rich-text (TipTap) titles.

The title editor's ``textStyle`` mark carries a font size and a colour, and
respondent pages write both into an inline ``style`` attribute. Only the
formats the editor produces are kept:

- font size: a number of pixels, ``"24"`` or ``"24px"`` (the editor's steps
  are 12, 15, 16, 24 and 32), from FONT_SIZE_MIN to FONT_SIZE_MAX;
- colour: ``#rgb``, ``#rrggbb``, ``rgb(r, g, b)`` or ``rgba(r, g, b, a)``
  with numbers (a pasted colour reaches the editor as ``rgb()``).

The edit operations refuse a title with any other value (ops.py
``_rich_text_problem``). A whole-form save drops such a value instead of
refusing the save (``sanitise_form_titles``): a form stored before this check
may hold one, and the builder sends the whole form back on every save. The
webapp applies the same rule when it renders a title
(``utils/rich-text-style.ts``). Keep the three in step.
"""

import re
from typing import Any, Optional

FONT_SIZE_MIN = 8
FONT_SIZE_MAX = 96
# fullmatch with re.ASCII mirrors the webapp rule exactly: no trailing
# newline, ASCII digits, and plain spaces only inside rgb().
_FONT_SIZE = re.compile(r"(\d{1,3}(?:\.\d{1,2})?)(?:px)?", re.ASCII)
_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", re.ASCII)
_RGB = re.compile(
    r"rgba?\( *(\d{1,3}) *, *(\d{1,3}) *, *(\d{1,3}) *"
    r"(?:, *(\d(?:\.\d{1,3})?|\.\d{1,3}) *)?\)",
    re.ASCII,
)
STYLE_ATTRS = ("fontSize", "color")


def valid_font_size(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    match = _FONT_SIZE.fullmatch(value)
    return bool(match) and FONT_SIZE_MIN <= float(match.group(1)) <= FONT_SIZE_MAX


def valid_color(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if _HEX.fullmatch(value):
        return True
    match = _RGB.fullmatch(value)
    if not match:
        return False
    alpha = match.group(4)
    return all(int(match.group(i)) <= 255 for i in (1, 2, 3)) and (
        alpha is None or float(alpha) <= 1
    )


def style_value_problem(name: str, value: Any) -> Optional[str]:
    """Why a ``textStyle`` attribute value is not one the editor writes."""
    if value is None:
        return None
    if name == "fontSize" and not valid_font_size(value):
        return (
            f"A font size must be a number of pixels from {FONT_SIZE_MIN} to "
            f"{FONT_SIZE_MAX}, like '16px'."
        )
    if name == "color" and not valid_color(value):
        return "A colour must be #rgb, #rrggbb, rgb(r, g, b) or rgba(r, g, b, a)."
    return None


def sanitise_rich_text(document: Any) -> int:
    """Drop, in place, every ``textStyle`` font size or colour of a rich-text
    document that is not one the editor writes. Returns how many."""
    dropped = 0
    pending = [document]
    while pending:
        node = pending.pop()
        if isinstance(node, list):
            pending.extend(node)
            continue
        if not isinstance(node, dict):
            continue
        for mark in node.get("marks") or []:
            if not isinstance(mark, dict) or mark.get("type") != "textStyle":
                continue
            attrs = mark.get("attrs")
            if not isinstance(attrs, dict):
                continue
            for name in STYLE_ATTRS:
                if name in attrs and style_value_problem(name, attrs[name]):
                    del attrs[name]
                    dropped += 1
        content = node.get("content")
        if isinstance(content, list):
            pending.extend(content)
    return dropped


def sanitise_form_titles(form: Any) -> int:
    """sanitise_rich_text on the rich-text title of every field of a form
    (pages, questions, group questions). Returns how many values were
    dropped."""
    dropped = 0
    pending = list(getattr(form, "fields", None) or [])
    while pending:
        field = pending.pop()
        if field is None:
            continue
        if isinstance(field.title, dict):
            dropped += sanitise_rich_text(field.title)
        properties = getattr(field, "properties", None)
        pending.extend((properties.fields if properties else None) or [])
    return dropped
