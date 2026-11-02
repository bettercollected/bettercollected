"""The audit entries of the response history: a staff edit of answers, and
every read of an entry's previous values. One entry in the workspace's audit
log (``workspace_audit_events``, the table the single sign-on break-glass log
uses): who, when, which form and response, and the entry's number. **Never a
value** (not an answer, a previous answer or a question's title), never an
address or a name.

A staff edit is audited after it is stored and the audit never fails it (the
revision log is its own record); a read of previous values is audited before
the values are opened and is refused (503 ``audit_unavailable``) when the entry
cannot be stored: values do not leave unrecorded.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Optional

from common.ids import RecordId
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_audit_event import (
    RESPONSE_REVISION_READ,
    RESPONSE_STAFF_EDIT,
    WorkspaceAuditEventDocument,
)

__all__ = ["RESPONSE_REVISION_READ", "RESPONSE_STAFF_EDIT", "record", "record_or_refuse"]


def _entry(event, workspace_id, user, form_id, response_id, revision):
    return WorkspaceAuditEventDocument(
        id=RecordId(),
        workspace_id=RecordId(str(workspace_id)),
        user_id=str(getattr(user, "id", "") or ""),
        session_id=str(getattr(user, "sid", "") or "") or None,
        event=event,
        form_id=str(form_id),
        response_id=str(response_id),
        revision=revision,
    )


async def record(
    repo,
    event: str,
    workspace_id,
    user,
    *,
    form_id,
    response_id,
    revision: Optional[int] = None,
) -> bool:
    """Store the entry; a failure is logged (ids only) and never raised."""
    if repo is None:
        return False
    try:
        await repo.record(_entry(event, workspace_id, user, form_id, response_id, revision))
        return True
    except Exception as error:  # noqa: BLE001 - the edit is stored; this is its trail
        logger.bind(audit=True).error(
            "AUDIT {} NOT STORED workspace={} user={} form={} response={} revision={} ({})",
            event,
            workspace_id,
            getattr(user, "id", None),
            form_id,
            response_id,
            revision,
            type(error).__name__,
        )
        return False


async def record_or_refuse(
    repo,
    event: str,
    workspace_id,
    user,
    *,
    form_id,
    response_id,
    revision: Optional[int] = None,
) -> None:
    """Store the entry or refuse the request: 503 ``audit_unavailable``."""
    if not await record(
        repo,
        event,
        workspace_id,
        user,
        form_id=form_id,
        response_id=response_id,
        revision=revision,
    ):
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            content={
                "code": "audit_unavailable",
                "message": "The access could not be recorded, so it was not allowed. Try again.",
            },
        )
