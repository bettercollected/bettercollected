"""Taking the audit log out as a file: the workspace's entries, or one form's, as
CSV or JSON, with the same filters and the same permission (``audit.read``) as
the list. Behind ``AUDIT_LOG_UI_ENABLED`` (422 ``audit_log_off`` while off). The
export is recorded before it starts (docs/audit-log.md)."""

import datetime as dt
from typing import List, Optional

from classy_fastapi import Routable, get
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Query, Request
from starlette.responses import StreamingResponse

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.router import router
from backend.app.services.response_export.http import NO_STORE, attachment
from backend.app.services.user_service import get_full_user

# the same checks as the list routes (controllers/audit_log_router.py)
_ID = r"^[A-Za-z0-9_.:-]{1,128}$"
_MAX_CHOICES = 40
_FORMAT = r"^(csv|json)$"


def refuse_navigation(request: Request) -> None:
    """The export is a GET, and the session cookie is SameSite=Lax, which a link
    on another site (a top-level navigation) still carries. A browser says what
    kind of request it is making (``Sec-Fetch-Mode``): the dashboard asks with
    ``fetch`` (``cors``), a followed link, a form, an image or a frame does not.
    A browser request that is not a ``cors`` fetch is refused, so a page on
    another site cannot start an export (and its audit entry and budget) for
    whoever follows its link. Clients that send no such header (scripts, curl)
    are not browsers carrying an ambient cookie and are unaffected."""
    mode = request.headers.get("sec-fetch-mode")
    if mode is not None and mode.strip().lower() != "cors":
        raise HTTPException(
            403,
            {
                "code": "export_needs_fetch",
                "message": "The export can only be started from the dashboard.",
            },
        )


@router(
    prefix="/workspaces/{workspace_id}",
    tags=["Audit log"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "audit.read is missing, or the request is a browser navigation (export_needs_fetch)."},
        404: {"description": "Not Found"},
        413: {"description": "too_many_rows: narrow the filters."},
        422: {"description": "The audit log is switched off, or a filter is not valid."},
        429: {"description": "rate_limited (Retry-After)"},
        503: {"description": "audit_unavailable: the export could not be recorded, so it was not made."},
    },
)
class AuditLogExportRouter(Routable):
    @get("/audit-log/export")
    async def export_workspace_audit_log(
        self,
        request: Request,
        workspace_id: RecordId,
        format: str = Query("csv", pattern=_FORMAT),
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
        """The workspace's entries that match the filters, as a file
        (``audit.read``; at most 100 000 entries). The filters are those of
        the list. Recorded as ``audit_log_exported`` before the file starts."""
        refuse_navigation(request)
        started = await container.audit_log_export().start(
            workspace_id,
            user,
            format,
            areas=area,
            events=event,
            actor=actor,
            target=target,
            involving=involving,
            filter_form=form_id,
            since=from_time,
            until=to_time,
        )
        return _file(started)

    @get("/forms/{form_id}/audit-log/export")
    async def export_form_audit_log(
        self,
        request: Request,
        workspace_id: RecordId,
        form_id: str,
        format: str = Query("csv", pattern=_FORMAT),
        area: List[str] = Query([], max_length=_MAX_CHOICES),
        event: List[str] = Query([], max_length=_MAX_CHOICES),
        actor: Optional[str] = Query(None, pattern=_ID),
        target: Optional[str] = Query(None, pattern=_ID),
        involving: Optional[str] = Query(None, pattern=_ID),
        from_time: Optional[dt.datetime] = Query(None, alias="from"),
        to_time: Optional[dt.datetime] = Query(None, alias="to"),
        user: User = Depends(get_full_user),
    ):
        """The entries about one form (404 for a form that is not this
        workspace's), as a file. The same filters, with the form fixed."""
        refuse_navigation(request)
        started = await container.audit_log_export().start(
            workspace_id,
            user,
            format,
            form_id=form_id,
            areas=area,
            events=event,
            actor=actor,
            target=target,
            involving=involving,
            since=from_time,
            until=to_time,
        )
        return _file(started)


def _file(started) -> StreamingResponse:
    return StreamingResponse(
        started.body,
        media_type=started.media_type,
        headers={
            **NO_STORE,
            "Content-Disposition": attachment(started.file_name),
            "X-Export-Rows": str(started.rows),
        },
    )
