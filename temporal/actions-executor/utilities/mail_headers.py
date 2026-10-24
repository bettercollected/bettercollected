"""Header values of the mails actions send (the From display name and the
subject): one line, no control or invisible formatting characters, capped.
A workspace or form title is free text a workspace member typed, so it can
never add a header line or reorder what a mail client shows."""

import unicodedata
from typing import Any, Dict, Iterable, Optional, Set

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


def _named_values(items: Optional[Iterable[Dict[str, Any]]]) -> Set[str]:
    names = set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name, value = item.get("name"), item.get("value")
        if name is not None and value is not None and value != "":
            names.add(name)
    return names


def set_by_workspace(
    action: Dict[str, Any], workspace: Dict[str, Any], form: Dict[str, Any]
) -> Set[str]:
    """The names of the action parameters the workspace configured itself (on
    the workspace or on the form), as opposed to the action's own defaults,
    which the instance's administrators set."""
    action_id = action.get("id")
    names: Set[str] = set()
    for owner in (workspace, form):
        overrides = (owner or {}).get("parameters") or {}
        if isinstance(overrides, dict):
            names |= _named_values(overrides.get(action_id))
    return names


# what makes a mail go through the workspace's own SMTP server, sent from its
# own address
OWN_SMTP_PARAMETERS = ("server", "Sender")


def uses_own_smtp(
    action: Dict[str, Any], workspace: Dict[str, Any], form: Dict[str, Any]
) -> bool:
    """Whether the workspace configured both the SMTP server and the From
    address of this action itself."""
    return set(OWN_SMTP_PARAMETERS) <= set_by_workspace(action, workspace, form)
