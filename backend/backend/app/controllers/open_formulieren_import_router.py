"""Import a form exported from Open Formulieren into a draft form.

POST uploads the exported archive (multipart, one ``file`` part) and answers
with the finished import: the draft's id and the report of what was dropped,
changed or flagged. GET reads an import again; POST ``.../review`` marks it
reviewed (or not). Everything is off (410 ``open_formulieren_off``) unless
``OPEN_FORMULIEREN_IMPORT=on``; see docs/open-formulieren.md.
"""

import datetime as dt
import io
from http import HTTPStatus
from typing import Any, Dict, List, Optional, Tuple

from classy_fastapi import Routable, get, post
from common.ids import RecordId
from common.models.user import User
from fastapi import Depends, Request
from fastapi_camelcase import CamelModel
from python_multipart.multipart import create_form_parser

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.router import router
from backend.app.schemas.form_import import FormImportDocument
from backend.app.services.open_formulieren import limits
from backend.app.services.open_formulieren_mode import refuse_open_formulieren_import
from backend.app.services.user_service import get_full_user

# room for the multipart framing around the file
_FRAMING_BYTES = 64 * 1024


class OpenFormulierenReportDto(CamelModel):
    truncated: bool = False
    items: List[Dict[str, Any]] = []


class OpenFormulierenImportDto(CamelModel):
    id: str
    # None once the draft was deleted
    form_id: Optional[str] = None
    status: str
    needs_review: bool
    source_kind: str
    source_version: Optional[str] = None
    file_name: str
    size_bytes: int
    created_at: Optional[dt.datetime] = None
    summary: Dict[str, int] = {}
    report: OpenFormulierenReportDto

    @classmethod
    def of(cls, record: FormImportDocument) -> "OpenFormulierenImportDto":
        stored = record.report or {}
        return cls(
            id=str(record.id),
            form_id=record.form_id,
            status=record.status,
            needs_review=bool(stored.get("needsReview")),
            source_kind=record.source_kind or "",
            source_version=stored.get("sourceVersion"),
            file_name=record.file_name,
            size_bytes=record.size_bytes,
            created_at=record.created_at,
            summary=stored.get("summary") or {},
            report=OpenFormulierenReportDto(
                truncated=bool(stored.get("truncated")),
                items=stored.get("items") or [],
            ),
        )


class ReviewBody(CamelModel):
    reviewed: bool


def _too_large() -> HTTPException:
    return HTTPException(
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        content={
            "code": "file_too_large",
            "message": "The file is too large.",
            "maxBytes": limits.MAX_UPLOAD_BYTES,
        },
    )


def _no_file() -> HTTPException:
    return HTTPException(
        HTTPStatus.BAD_REQUEST,
        content={
            "code": "file_missing",
            "message": "Upload the exported archive as the 'file' part.",
        },
    )


async def read_upload(request: Request) -> Tuple[bytes, Optional[str]]:
    """The ``file`` part of a multipart request, read with a hard cap: the
    declared length is refused early, and the body is counted as it arrives
    (never trusted), so nothing past the cap is ever kept or spooled."""
    cap = limits.MAX_UPLOAD_BYTES + _FRAMING_BYTES
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > cap:
        raise _too_large()
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith("multipart/form-data"):
        raise _no_file()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > cap:
            raise _too_large()
    files: list = []
    parts = [0]

    def counted(handler):
        # one file part is all we need: a body of thousands of tiny parts is
        # stopped here instead of being parsed to the end
        def call(part):
            parts[0] += 1
            if parts[0] > limits.MAX_UPLOAD_PARTS:
                raise ValueError("too many parts")
            return handler(part)

        return call

    try:
        parser = create_form_parser(
            {"Content-Type": content_type.encode("latin-1", "replace")},
            counted(lambda field: None),
            counted(files.append),
            config={"MAX_MEMORY_FILE_SIZE": cap},
        )
        parser.write(bytes(body))
        parser.finalize()
    except Exception:  # noqa: BLE001 — a malformed body is "no file"
        raise _no_file() from None
    for part in files:
        name = part.field_name
        name = name.decode("utf-8", "replace") if isinstance(name, bytes) else name
        if name != "file":
            continue
        stream: io.IOBase = part.file_object
        stream.seek(0)
        data = stream.read(cap + 1)
        if len(data) > limits.MAX_UPLOAD_BYTES:
            raise _too_large()
        file_name = part.file_name
        if isinstance(file_name, bytes):
            file_name = file_name.decode("utf-8", "replace")
        return data, file_name
    raise _no_file()


@router(
    prefix="/workspaces/{workspace_id}/open-formulieren-imports",
    tags=["Open Formulieren import"],
)
class OpenFormulierenImportRouter(Routable):
    @post("", response_model=OpenFormulierenImportDto, status_code=201)
    async def start_import(
        self,
        request: Request,
        workspace_id: RecordId,
        # first: the switch answers before anything else, the body included
        _on: None = Depends(refuse_open_formulieren_import),
        user: User = Depends(get_full_user),
    ):
        service = container.open_formulieren_import_service()
        # authorise before the body is read: a non-member's upload is never read
        await service.authorize_start(workspace_id, user)
        data, file_name = await read_upload(request)
        record = await service.start(workspace_id, data, file_name, user)
        return OpenFormulierenImportDto.of(record)

    @get("/{import_id}", response_model=OpenFormulierenImportDto)
    async def get_import(
        self,
        workspace_id: RecordId,
        import_id: RecordId,
        _on: None = Depends(refuse_open_formulieren_import),
        user: User = Depends(get_full_user),
    ):
        record = await container.open_formulieren_import_service().get(
            workspace_id, import_id, user
        )
        return OpenFormulierenImportDto.of(record)

    @post("/{import_id}/review", response_model=OpenFormulierenImportDto)
    async def review_import(
        self,
        workspace_id: RecordId,
        import_id: RecordId,
        body: ReviewBody,
        _on: None = Depends(refuse_open_formulieren_import),
        user: User = Depends(get_full_user),
    ):
        record = await container.open_formulieren_import_service().review(
            workspace_id, import_id, body.reviewed, user
        )
        return OpenFormulierenImportDto.of(record)
