"""What a form's action entry says about the move of a built-in action (4.4).

Kept apart from the services so the form and action services can both use it."""

from __future__ import annotations

from typing import Any

# the built-in actions that become a webhook or an email action when moved
MOVABLE_BUILTINS = (
    "send_webhook",
    "send_to_slack",
    "send_to_discord",
    "creator_copy_mail",
    "responder_copy_mail",
)
MOVED_VIA = "migrated_builtin"


def executor_sources(actions: Any) -> set:
    """The ids of the form's on-submit entries the executor is given a run for
    in a submission that read ``actions`` (a form's actions as that submission
    saw them): on, and not moved. A moved action's webhook or email action skips
    a submission whose snapshot still had it here, or both would deliver."""
    from common.models.standard_form import Trigger

    entries = (actions or {}).get(Trigger.on_submit) or (actions or {}).get("on_submit") or []
    return {str(e.id) for e in entries if e.enabled and not entry_moved(e)}


def entry_moved(entry: Any) -> bool:
    """Whether the built-in action of this entry was moved to a webhook or an
    email action (``migrated_to``): the entry is then off for good, whatever its
    ``enabled`` says (a creator's switch cannot turn it back on next to its
    replacement), and only the runs queued before the move still count."""
    marker = getattr(entry, "migrated_to", None) or {}
    return marker.get("kind") in ("webhook", "email")
