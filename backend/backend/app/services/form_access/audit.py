"""The audit entries of form-level access: a team created, renamed or deleted,
a person added to or removed from one, a grant added, changed or removed, a
form's access mode changed, a member's grants and teams removed with them.

One entry in the workspace's audit log (``workspace_audit_events``): who made
the change, when, and **ids and enum values only** (the form, the team, the
person it concerns, the role, the export flag, the new mode, a count), never a
team name, a form title, an address or a person's name.

The entry is stored **before** the change and the change is refused (503
``audit_unavailable``) when it cannot be stored: a change is never made
unrecorded. A change that then fails leaves an entry for something that did not
happen, which is the safe direction (a recorded attempt).
"""

from __future__ import annotations

from http import HTTPStatus

from common.ids import RecordId
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_audit_event import (
    ACCESS_EVENTS,
    API_KEY_EVENTS,
    WorkspaceAuditEventDocument,
)

__all__ = ["record", "record_or_refuse"]


def _entry(event: str, workspace_id, user, **ids) -> WorkspaceAuditEventDocument:
    return WorkspaceAuditEventDocument(
        id=RecordId(),
        workspace_id=RecordId(str(workspace_id)),
        user_id=str(getattr(user, "id", "") or ""),
        session_id=str(getattr(user, "sid", "") or "") or None,
        event=event,
        **{key: value for key, value in ids.items() if value is not None},
    )


async def record(repo, event: str, workspace_id, user, **ids) -> bool:
    """Store the entry; a failure is logged (ids only) and never raised."""
    assert event in ACCESS_EVENTS or event in API_KEY_EVENTS, event
    if repo is None:
        return False
    try:
        await repo.record(_entry(event, workspace_id, user, **ids))
        return True
    except Exception as error:  # noqa: BLE001 - the caller decides what a failure means
        logger.bind(audit=True).error(
            "AUDIT {} NOT STORED workspace={} user={} ({})",
            event,
            workspace_id,
            getattr(user, "id", None),
            type(error).__name__,
        )
        return False


async def record_or_refuse(repo, event: str, workspace_id, user, **ids) -> None:
    """Store the entry or refuse the request: 503 ``audit_unavailable``."""
    if not await record(repo, event, workspace_id, user, **ids):
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            content={
                "code": "audit_unavailable",
                "message": "The change could not be recorded, so it was not made. Try again.",
            },
        )

