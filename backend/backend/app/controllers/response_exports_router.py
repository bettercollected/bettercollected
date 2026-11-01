"""Exporting a form's responses (docs/response-export.md).

``POST .../exports`` answers with the file itself (CSV, a ZIP when the form's
repeating groups export as CSV tables, an Excel workbook or JSON, as asked in
``format``) for a small set, or ``202`` and an export to
follow for a large one, built by a background job; ``GET .../exports/{id}``
reports it and, once ready, hands its requester a short-lived signed link to
``.../download`` (as often as wanted until the file is deleted, 24 hours after it was
built or sooner by ``DELETE .../exports/{id}``). Every route needs ``response.export``; an export is its
requester's alone. The old whole-set JSON route is gone.
"""

from typing import Any, Dict, List

from classy_fastapi import Routable, delete, get, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Body, Depends, Query
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, Response, StreamingResponse

from backend.app.container import container
from backend.app.models.dtos.response_export_dto import ResponseExportRequest
from backend.app.router import router
from backend.app.services.response_export.formats import media_type
from backend.app.services.response_export.http import NO_STORE, attachment
from backend.app.services.response_export.service import StreamStart
from backend.app.services.user_service import get_full_user

_NO_STORE = NO_STORE
_attachment = attachment


@router(
    prefix="/workspaces/{workspace_id}/forms/{form_id}/exports",
    tags=["Response export"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The caller lacks response.export."},
        404: {"description": "Not found"},
    },
)
class ResponseExportsRouter(Routable):
    @get("/columns")
    async def columns(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ) -> List[Dict[str, str]]:
        """The columns an export may be limited to: key, label, kind."""
        return await container.response_export_service().columns(workspace_id, form_id, user)

    @get("")
    async def recent(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ):
        """The caller's own exports of this form that are running, ready or
        failed (so a page finds one again after a reload)."""
        views = await container.response_export_service().recent(workspace_id, form_id, user)
        return JSONResponse(jsonable_encoder(views), headers=_NO_STORE)

    @post(
        "",
        responses={
            200: {"description": "The file (text/csv, application/zip, the .xlsx or application/json, as asked in format)."},
            202: {"description": "A large export: poll the export it names."},
            409: {"description": "export_in_progress"},
            413: {"description": "too_many_rows"},
            422: {"description": "unknown_column, no_columns, too_many_columns (xlsx), or an invalid filter."},
            429: {"description": "rate_limited (Retry-After)"},
        },
    )
    async def start_export(
        self,
        workspace_id: RecordId,
        form_id: str,
        body: ResponseExportRequest = Body(default_factory=ResponseExportRequest),
        user: User = Depends(get_full_user),
    ):
        service = container.response_export_service()
        started: Any = await service.request(
            workspace_id, form_id, user, body.columns, body.filters(), body.format
        )
        if isinstance(started, StreamStart):
            return StreamingResponse(
                started.body,
                media_type=started.media_type,
                headers={
                    **_NO_STORE,
                    "Content-Disposition": _attachment(started.file_name),
                    "X-Export-Id": str(started.export.id),
                },
            )
        return JSONResponse(
            jsonable_encoder(service.present(started, user)),
            status_code=202,
            headers=_NO_STORE,
        )

    @get("/{export_id}")
    async def export_status(
        self,
        workspace_id: RecordId,
        form_id: str,
        export_id: str,
        user: User = Depends(get_full_user),
    ):
        """State of an export of the caller's; ``downloadUrl`` (a fresh signed
        link, valid for five minutes) once its file is ready."""
        view = await container.response_export_service().status(
            workspace_id, form_id, export_id, user
        )
        return JSONResponse(jsonable_encoder(view), headers=_NO_STORE)

    @delete(
        "/{export_id}",
        status_code=204,
        responses={409: {"description": "export_not_ready: still being prepared"}},
    )
    async def discard(
        self,
        workspace_id: RecordId,
        form_id: str,
        export_id: str,
        user: User = Depends(get_full_user),
    ):
        """Delete the file of a ready export now (its requester only), so a new
        export can be started without waiting for the file to expire. The audit
        entry stays."""
        await container.response_export_service().discard(workspace_id, form_id, export_id, user)
        return Response(status_code=204, headers=_NO_STORE)

    @get("/{export_id}/download")
    async def download(
        self,
        workspace_id: RecordId,
        form_id: str,
        export_id: str,
        token: str = Query(..., max_length=200),
        user: User = Depends(get_full_user),
    ):
        """The file of a ready export, as often as wanted until it is deleted: the
        caller's own, with the link the status gave them."""
        export, body = await container.response_export_service().download(
            workspace_id, form_id, export_id, token, user
        )
        return StreamingResponse(
            body,
            media_type=media_type(export.format),
            headers={**_NO_STORE, "Content-Disposition": _attachment(export.file_name or f"export.{export.format}")},
        )
