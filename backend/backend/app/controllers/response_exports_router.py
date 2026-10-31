"""Exporting a form's responses (docs/response-export.md).

``POST .../exports`` answers with the CSV itself (a ZIP when the form's
repeating groups export as tables) for a small set, or ``202`` and an export to
follow for a large one, built by a background job; ``GET .../exports/{id}``
reports it and, once ready, hands its requester a short-lived signed link to
``.../download``. Every route needs ``response.export``; an export is its
requester's alone. The old whole-set JSON route is gone.
"""

from typing import Any, Dict, List
from urllib.parse import quote

from classy_fastapi import Routable, get, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Body, Depends, Query
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, StreamingResponse

from backend.app.container import container
from backend.app.models.dtos.response_export_dto import ResponseExportRequest
from backend.app.router import router
from backend.app.services.response_export.service import StreamStart
from backend.app.services.user_service import get_full_user

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"}


def _attachment(file_name: str) -> str:
    """``Content-Disposition`` for a name made from a form title: a plain ASCII
    fallback and the full name percent-encoded (never a raw character of the
    title in the header)."""
    ascii_name = "".join(c if c.isascii() and c.isprintable() and c not in '"\;' else "_" for c in file_name)
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name, safe='')}"


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
            200: {"description": "The file (text/csv, or application/zip)."},
            202: {"description": "A large export: poll the export it names."},
            409: {"description": "export_in_progress"},
            413: {"description": "too_many_rows"},
            422: {"description": "unknown_column, no_columns, or an invalid filter."},
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
            workspace_id, form_id, user, body.columns, body.filters()
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

    @get("/{export_id}/download")
    async def download(
        self,
        workspace_id: RecordId,
        form_id: str,
        export_id: str,
        token: str = Query(..., max_length=200),
        user: User = Depends(get_full_user),
    ):
        """The file of a ready export, once: the caller's own, with the link
        the status gave them. The file is deleted when it has been sent."""
        export, body = await container.response_export_service().download(
            workspace_id, form_id, export_id, token, user
        )
        return StreamingResponse(
            body,
            media_type="application/zip" if export.format == "zip" else "text/csv; charset=utf-8",
            headers={**_NO_STORE, "Content-Disposition": _attachment(export.file_name or "export.csv")},
        )
