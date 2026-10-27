"""Export a form as an Open Formulieren import archive.

``export`` authorises first (the form-read permission of the form's own
workspace), loads the form's draft through the form spec service (a form of
another workspace is a 404) and builds the archive in a thread: the work is
CPU bound and the archive is made in memory. Responses are never read: the
service has no access to them, and the exporter only sees the form
definition. See docs/open-formulieren.md.
"""

from __future__ import annotations


from common.ids import RecordId
from common.models.user import User
from loguru import logger
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.services.open_formulieren.errors import ImportRefused
from backend.app.services.open_formulieren.exporter import ExportResult, build_export
from backend.app.services.open_formulieren_mode import refuse_open_formulieren_export


class OpenFormulierenExportService:
    def __init__(self, authorization_service, form_spec_service):
        self._authorization = authorization_service
        self._forms = form_spec_service

    async def export(
        self, workspace_id: RecordId, form_id: str, user: User
    ) -> ExportResult:
        refuse_open_formulieren_export()
        await self._authorization.authorize(user, Permission.FORM_READ, workspace_id)
        form, _ = await self._forms.load(workspace_id, form_id)
        try:
            result = await run_in_threadpool(build_export, form)
        except ImportRefused as refused:
            raise HTTPException(refused.status, content=refused.content()) from None
        # counts only: never a title, a question or a person
        logger.info(
            "open formulieren export: {pages} pages, {questions} questions, "
            "{unmapped} unmapped",
            pages=result.pages,
            questions=result.questions,
            unmapped=result.unmapped,
        )
        return result


