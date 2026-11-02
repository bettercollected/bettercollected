"""The audit log for staff holding ``audit.read`` (docs/audit-log.md): the
workspace's entries and a form's, newest first, read only. Both behind
``AUDIT_LOG_UI_ENABLED`` (422 ``audit_log_off`` while off). Reading the log is
not itself audited. The workspace's retention (how long entries are kept) is read
here too and changed by an owner."""

import datetime as dt
from typing import List, Optional

from classy_fastapi import Routable, get, put
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query

from backend.app.container import container
from backend.app.models.dtos.audit_log_dto import (
    AuditPageDto,
    AuditRetentionDto,
    SetAuditRetentionDto,
)
from backend.app.router import router
from backend.app.services.sso.policy import AUDIT_PAGE_MAX, AUDIT_PAGE_SIZE
from backend.app.services.user_service import get_full_user

# an id of a person or a form (the ids the log holds), checked before it is used
_ID = r"^[A-Za-z0-9_.:-]{1,128}$"
_MAX_CHOICES = 40


@router(
    prefix="/workspaces/{workspace_id}",
    tags=["Audit log"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "audit.read is missing."},
        404: {"description": "Not Found"},
        422: {"description": "The audit log is switched off, or a filter is not valid."},
    },
)
class AuditLogRouter(Routable):
    @get("/audit-log", response_model=AuditPageDto)
    async def workspace_audit_log(
        self,
        workspace_id: RecordId,
        cursor: Optional[str] = Query(None, max_length=200),
        limit: int = Query(AUDIT_PAGE_SIZE, ge=1, le=AUDIT_PAGE_MAX),
        area: List[str] = Query([], max_length=_MAX_CHOICES),
        event: List[str] = Query([], max_length=_MAX_CHOICES),
        actor: Optional[str] = Query(None, pattern=_ID),
        target: Optional[str] = Query(None, pattern=_ID),
        involving: Optional[str] = Query(None, pattern=_ID),
        form_id: Optional[str] = Query(None, pattern=_ID),
        from_time: Optional[dt.datetime] = Query(None, alias="from"),
        to_time: Optional[dt.datetime] = Query(None, alias="to"),
        user: User = Depends(get_full_user),
    ):
        """The workspace's audit entries, newest first (``audit.read``: Owner,
        Admin, Privacy officer). ``area`` and ``event`` (repeatable) choose
        kinds of entry; ``actor`` who did it, ``target`` who it was done to,
        ``involving`` either; ``form_id``; ``from``/``to`` a range. ``nextCursor``
        asks for the next, older page. Codes, ids and the current names of the
        ids of the page: never an answer or an address."""
        return await container.audit_log_reader().workspace_page(
            workspace_id,
            user,
            cursor=cursor,
            limit=limit,
            areas=area,
            events=event,
            actor=actor,
            target=target,
            involving=involving,
            form_id=form_id,
            since=from_time,
            until=to_time,
        )

    @get("/forms/{form_id}/audit-log", response_model=AuditPageDto)
    async def form_audit_log(
        self,
        workspace_id: RecordId,
        form_id: str,
        cursor: Optional[str] = Query(None, max_length=200),
        limit: int = Query(AUDIT_PAGE_SIZE, ge=1, le=AUDIT_PAGE_MAX),
        area: List[str] = Query([], max_length=_MAX_CHOICES),
        event: List[str] = Query([], max_length=_MAX_CHOICES),
        actor: Optional[str] = Query(None, pattern=_ID),
        target: Optional[str] = Query(None, pattern=_ID),
        involving: Optional[str] = Query(None, pattern=_ID),
        from_time: Optional[dt.datetime] = Query(None, alias="from"),
        to_time: Optional[dt.datetime] = Query(None, alias="to"),
        user: User = Depends(get_full_user),
    ):
        """The entries about one form (``audit.read``; 404 for a form that is
        not this workspace's). The same filters, with the form fixed."""
        return await container.audit_log_reader().form_page(
            workspace_id,
            form_id,
            user,
            cursor=cursor,
            limit=limit,
            areas=area,
            events=event,
            actor=actor,
            target=target,
            involving=involving,
            since=from_time,
            until=to_time,
        )

    @get("/audit-log/retention", response_model=AuditRetentionDto)
    async def audit_retention(
        self, workspace_id: RecordId, user: User = Depends(get_full_user)
    ):
        """How long the workspace's entries are kept, the choices, and whether
        the caller may change it (``audit.read``)."""
        return await container.audit_retention().overview(workspace_id, user)

    @put("/audit-log/retention", response_model=AuditRetentionDto)
    async def set_audit_retention(
        self,
        workspace_id: RecordId,
        body: SetAuditRetentionDto,
        user: User = Depends(get_full_user),
    ):
        """Owners only: keep the entries 6, 12, 24 or 60 months (422
        ``retention_below_minimum`` under 6, ``invalid_retention`` for any other
        number). Recorded first; a shorter period applies at the next daily
        purge (``appliesAtNextPurge``)."""
        return await container.audit_retention().set_months(
            workspace_id, user, body.months
        )
