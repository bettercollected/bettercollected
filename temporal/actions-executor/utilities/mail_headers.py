"""Header values of the mails actions send (the From display name and the
subject): one line, no control or invisible formatting characters, capped.
A workspace or form title is free text a workspace member typed, so it can
never add a header line or reorder what a mail client shows."""

import unicodedata
from typing import Any, Optional

# RFC 5322 recommends lines of at most 78 characters; a display name longer
# than that is cut by most clients anyway.
FROM_NAME_MAX = 78
SUBJECT_MAX = 120


def one_line(value: Optional[Any], limit: int) -> str:
    """``value`` as one header-safe line: line breaks, tabs and other control
    characters become spaces, invisible formatting characters (bidi overrides,
    zero-width characters) are dropped, runs of whitespace are collapsed, and
    the result is capped at ``limit`` characters."""
    if value is None:
        return ""
    kept = []
    for char in str(value):
        category = unicodedata.category(char)
        if category == "Cc" or category in ("Zl", "Zp"):
            kept.append(" ")
        elif category.startswith("C"):
            continue
        else:
            kept.append(char)
    text = " ".join("".join(kept).split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


# the longest " via <instance>" tail kept whole; the workspace gets the rest
INSTANCE_NAME_MAX = 40
FALLBACK_INSTANCE_NAME = "BetterCollected"


def _squashed(value: str) -> str:
    return "".join(value.split()).casefold()


def respondent_from_name(
    workspace_title: Optional[Any], instance_name: Optional[Any]
) -> str:
    """The From display name of a respondent's copy: "<workspace> via
    <instance>", as the sign-in code mail names a workspace. The instance is
    the sender (its ``ORGANIZATION_NAME``); the workspace title is free text a
    member typed, so it is folded to one line and cut to fit ``FROM_NAME_MAX``
    with the tail. A workspace that is no one, or just the instance's own
    name, leaves the instance alone."""
    instance = one_line(instance_name, INSTANCE_NAME_MAX) or FALLBACK_INSTANCE_NAME
    tail = f" via {instance}"
    title = one_line(workspace_title, FROM_NAME_MAX - len(tail))
    if not title or _squashed(title) == _squashed(instance):
        return instance
    return title + tail
