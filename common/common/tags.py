"""What a ``tags`` answer may hold: short free-entry labels.

An answer is ``{"type": "tags", "tags": ["a", "b"]}``. A tag is stored the way
it is shown: trimmed and not empty, without ``,`` or ``;`` (they separate tags
in the input and in an export) or control characters, at most ``TAG_LENGTH_MAX``
characters, and no two tags are the same ignoring case. At most ``TAGS_MAX``
tags. The webapp keeps the same rules (``webapp/src/utils/tags.ts``).
"""

import re
from typing import Iterable, List, Optional

# Tags one answer may hold, and the characters of one tag (the hard caps: a
# question's own limits can only be lower).
TAGS_MAX = 30
TAG_LENGTH_MAX = 40

_FORBIDDEN = re.compile(r"[,;\x00-\x1f\x7f-\x9f  ]")


def is_tag(value: object) -> bool:
    """Is ``value`` a well-formed tag (not looking at its length or at the
    other tags)?"""
    return (
        isinstance(value, str)
        and value != ""
        and value == value.strip()
        and _FORBIDDEN.search(value) is None
    )


def tag_key(value: str) -> str:
    """What two tags are compared by: the text without case."""
    return value.lower()


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
