"""Import a PDF (or a photo of a paper form) into a draft form.

POST uploads the file and starts the import; the response carries the import
id and the draft form id right away. GET returns progress and, once done,
the per-page analysis and the import report.
"""

import datetime as dt
from typing import Any, Dict, List, Optional

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, post
from fastapi import Depends, File, UploadFile
from fastapi_camelcase import CamelModel

from backend.app.container import container
from backend.app.router import router
from backend.app.schemas.form_import import FormImportDocument, PageAnalysis
from backend.app.services.user_service import get_logged_user
from common.models.user import User

# Starlette has already received and spooled the whole body before the handler
# runs; the proxy's body limit is the real guard. Reading in chunks only keeps
# us from copying more than the limit into memory here.
READ_CHUNK = 1024 * 1024


class PdfImportDto(CamelModel):
    id: str
    form_id: str
    status: str
    stage: Optional[str] = None
    error: Optional[str] = None
    file_name: str
    content_type: str
    size_bytes: int
    page_count: Optional[int] = None
    pages: List[PageAnalysis] = []
    report: Dict[str, Any] = {}
    created_at: Optional[dt.datetime] = None
    finished_at: Optional[dt.datetime] = None

    @classmethod
    def of(cls, record: FormImportDocument) -> "PdfImportDto":
        return cls(
            id=str(record.id),
            form_id=record.form_id,
            status=record.status,
            stage=record.stage,
            error=record.error,
            file_name=record.file_name,
            content_type=record.content_type,
            size_bytes=record.size_bytes,
            page_count=record.page_count,
            pages=record.pages,
            report=record.report,
            created_at=record.created_at,
            finished_at=record.finished_at,
        )


async def _read_capped(file: UploadFile, limit: int) -> bytes:
    chunks, total = [], 0
    while True:
        chunk = await file.read(READ_CHUNK)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > limit:
            break
    return b"".join(chunks)


@router(prefix="/workspaces/{workspace_id}/form-imports", tags=["Form import"])
class PdfImportRouter(Routable):
    @post("", response_model=PdfImportDto, status_code=202)
    async def start_import(
        self,
        workspace_id: PydanticObjectId,
        file: UploadFile = File(...),
        user: User = Depends(get_logged_user),
    ):
        service = container.pdf_import_service()
        limit = service.max_bytes
        data = await _read_capped(file, limit)
        record = await service.start(workspace_id, data, file.filename, user)
        return PdfImportDto.of(record)

    @get("", response_model=List[PdfImportDto])
    async def list_imports(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ):
        records = await container.pdf_import_service().list(workspace_id, user)
        return [PdfImportDto.of(r) for r in records]

    @get("/{import_id}", response_model=PdfImportDto)
    async def get_import(
        self,
        workspace_id: PydanticObjectId,
        import_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        record = await container.pdf_import_service().get(workspace_id, import_id, user)
        return PdfImportDto.of(record)
