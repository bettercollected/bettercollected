"""The text rules of an option label, a list name and a group key, and how two
of them are compared. One set of rules for a typed list item, a CSV row and an
answer of another form: stored text cannot hide characters, and two spellings
that look the same are the same option."""

import unicodedata
from typing import Optional

# Limits (docs/option-sources.md).
LISTS_PER_WORKSPACE = 100
ITEMS_PER_LIST = 2_000
LABEL_MAX = 200
GROUP_MAX = 200
NAME_MAX = 100
# options built from another form's answers, and responses read to build them
ANSWER_OPTIONS_MAX = 1_000
ANSWER_RESPONSES_MAX = 10_000

# Control (Cc), format (Cf: zero-width and bidirectional marks, the byte order
# mark, the soft hyphen) and line / paragraph separators (Zl, Zp).
_FORBIDDEN = frozenset({"Cc", "Cf", "Zl", "Zp"})


def has_forbidden(value: str) -> bool:
    return any(unicodedata.category(char) in _FORBIDDEN for char in value)


def clean(value: object, max_length: int) -> Optional[str]:
    """The text as stored: Unicode form C, whitespace runs collapsed to one
    space, trimmed. None when it is not text, is empty, is longer than
    ``max_length`` or holds a forbidden character (nothing is silently cut or
    repaired: the caller refuses or skips)."""
    if not isinstance(value, str):
        return None
    text = unicodedata.normalize("NFC", value)
    # line breaks and tabs are only spacing; every other control character
    # (and the invisible ones) is refused
    for spacing in "\t\n\r\v\f":
        text = text.replace(spacing, " ")
    if has_forbidden(text):
        return None
    text = " ".join(text.split())
    if not text or len(text) > max_length:
        return None
    return text


def fold(value: str) -> str:
    """What two labels, names or group keys are compared by."""
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())
