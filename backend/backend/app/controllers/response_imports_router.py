"""Importing submissions from a CSV file (docs/response-import.md).

``POST .../imports`` takes the file itself as the request body (``text/csv``,
not a multipart form: the framework spools a form's files to disk, and an
uploaded file never touches disk here) and answers with what was found and the
mapping suggested. ``.../check`` runs the file through the respondent checks
and stores nothing; ``.../run`` imports it; both are background jobs to follow
with ``GET .../imports/{id}``. ``.../rollback`` deletes what a completed import
created. Every route needs ``response.import`` and ``CSV_IMPORT_ENABLED``
(off: 404).
"""

from typing import List

from classy_fastapi import Routable, delete, get, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Body, Depends, Request
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, Response

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_import_dto import ResponseImportRequest
from backend.app.router import router
from backend.app.services.response_import import limits
from backend.app.services.user_service import get_full_user
from http import HTTPStatus

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache", "X-Content-Type-Options": "nosniff"}
_ACCEPTED_TYPES = {
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
}
# the file's cap plus a little room, so a body only just over it is read far
# enough to be refused as ``too_large`` with the right code
_READ_LIMIT = limits.MAX_FILE_BYTES + 1


def _too_large() -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content={"code": "too_large", "message": "This file cannot be imported."},
    )


async def read_capped_body(request: Request) -> bytes:
    """The request body, read in pieces and refused (413) as soon as it passes
    the file cap: memory stays bounded and nothing is spooled to disk."""
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > _READ_LIMIT:
        raise _too_large()
    kind = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if kind not in _ACCEPTED_TYPES:
        raise HTTPException(
            status_code=HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            content={"code": "unsupported_format", "message": "Send the CSV file as the request body."},
        )
    chunks: List[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > _READ_LIMIT:
            raise _too_large()
        chunks.append(chunk)
    return b"".join(chunks)


@router(
    prefix="/workspaces/{workspace_id}/forms/{form_id}/imports",
    tags=["Response import"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "The caller lacks response.import."},
        404: {"description": "Not found (also while CSV_IMPORT_ENABLED is off)."},
    },
)
class ResponseImportsRouter(Routable):
    @get("")
    async def recent(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User = Depends(get_full_user),
    ):
        """The form's imports, newest first."""
        views = await container.response_import_service().recent(workspace_id, form_id, user)
        return JSONResponse(jsonable_encoder(views), headers=_NO_STORE)

    @post(
        "",
        status_code=201,
        responses={
            413: {"description": "too_large or too_many_rows"},
            415: {"description": "unsupported_format"},
            422: {"description": "A file that cannot be read (code)."},
            429: {"description": "rate_limited (Retry-After)"},
        },
    )
    async def upload(
        self,
        workspace_id: RecordId,
        form_id: str,
        request: Request,
        user: User = Depends(get_full_user),
    ):
        """Upload the CSV file (the request body, ``Content-Type: text/csv``)."""
        service = container.response_import_service()
        # the switch and the permission are asked before the body is read
        await service.ensure_allowed(workspace_id, user)
        data = await read_capped_body(request)
        view = await service.start(workspace_id, form_id, user, data)
        return JSONResponse(jsonable_encoder(view), status_code=201, headers=_NO_STORE)

    @get("/{import_id}")
    async def import_status(
        self,
        workspace_id: RecordId,
        form_id: str,
        import_id: str,
        user: User = Depends(get_full_user),
    ):
        view = await container.response_import_service().get(workspace_id, form_id, import_id, user)
        return JSONResponse(jsonable_encoder(view), headers=_NO_STORE)

    @post("/{import_id}/check", status_code=202)
    async def check(
        self,
        workspace_id: RecordId,
        form_id: str,
        import_id: str,
        body: ResponseImportRequest = Body(default_factory=ResponseImportRequest),
        user: User = Depends(get_full_user),
    ):
        """Queue a dry run: nothing is stored."""
        view = await container.response_import_service().check(
            workspace_id, form_id, import_id, user, body.mapping, {"skipInvalidRows": body.skip_invalid_rows}
        )
        return JSONResponse(jsonable_encoder(view), status_code=202, headers=_NO_STORE)

    @post("/{import_id}/run", status_code=202)
    async def run(
        self,
        workspace_id: RecordId,
        form_id: str,
        import_id: str,
        body: ResponseImportRequest = Body(default_factory=ResponseImportRequest),
        user: User = Depends(get_full_user),
    ):
        """Queue the import (needs ``confirmedLawfulBasis``)."""
        view = await container.response_import_service().run(
            workspace_id,
            form_id,
            import_id,
            user,
            body.mapping,
            {"skipInvalidRows": body.skip_invalid_rows},
            confirmed=body.confirmed_lawful_basis,
        )
        return JSONResponse(jsonable_encoder(view), status_code=202, headers=_NO_STORE)

    @post("/{import_id}/rollback")
    async def rollback(
        self,
        workspace_id: RecordId,
        form_id: str,
        import_id: str,
        user: User = Depends(get_full_user),
    ):
        """Delete the responses a completed import created (within 14 days)."""
        view = await container.response_import_service().rollback(workspace_id, form_id, import_id, user)
        return JSONResponse(jsonable_encoder(view), headers=_NO_STORE)

    @delete("/{import_id}", status_code=204)
    async def discard(
        self,
        workspace_id: RecordId,
        form_id: str,
        import_id: str,
        user: User = Depends(get_full_user),
    ):
        """Throw an unused upload away (its file is deleted)."""
        await container.response_import_service().discard(workspace_id, form_id, import_id, user)
        return Response(status_code=204, headers=_NO_STORE)
