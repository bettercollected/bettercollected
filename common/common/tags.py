"""What a ``tags`` answer may hold: short free-entry labels.

An answer is ``{"type": "tags", "tags": ["a", "b"]}``. A tag is stored the way
it is shown: trimmed and not empty, without ``,`` or ``;`` (they separate tags
in the input and in an export), control characters or format characters
(zero-width and bidirectional marks), at most ``TAG_LENGTH_MAX``
characters, and no two tags are the same ignoring case. At most ``TAGS_MAX``
tags. The webapp keeps the same rules (``webapp/src/utils/tags.ts``).
"""

import unicodedata
from typing import Iterable, List, Optional

# Tags one answer may hold, and the characters of one tag (the hard caps: a
# question's own limits can only be lower).
TAGS_MAX = 30
TAG_LENGTH_MAX = 40

# ``,`` and ``;`` separate tags; control characters (Cc), format characters (Cf:
# zero-width and bidirectional marks, the byte order mark, the soft hyphen) and the
# line and paragraph separators (Zl, Zp) never belong in one: they reverse or hide
# text in a view and defeat the comparison of two tags.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})


def _has_forbidden(value: str) -> bool:
    return any(
        char in ",;" or unicodedata.category(char) in _FORBIDDEN_CATEGORIES
        for char in value
    )


def is_tag(value: object) -> bool:
    """Is ``value`` a well-formed tag (not looking at its length or at the
    other tags)?"""
    return (
        isinstance(value, str)
        and value != ""
        and value == value.strip()
        and not _has_forbidden(value)
    )


def tag_key(value: str) -> str:
    """What two tags are compared by: the text in Unicode form C (a precomposed
    and a decomposed letter are the same) and in lower case."""
    return unicodedata.normalize("NFC", value).lower()


def duplicate_index(tags: Iterable[str]) -> Optional[int]:
    """The position of the first tag that repeats an earlier one, or None."""
    seen = set()
    for index, tag in enumerate(tags):
        key = tag_key(tag)
        if key in seen:
            return index
        seen.add(key)
    return None


def joined(tags: List[str]) -> str:
    """The tags as one cell of an export (``; `` between them)."""
    return "; ".join(tags)
