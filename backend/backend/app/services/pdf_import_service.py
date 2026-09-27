"""Start and read imports of PDF (or photographed) forms.

Starting an import creates the draft form right away, so the uploaded
original is stored in the form's private folder and lives exactly as long as
the form. The pipeline runs as a job: on the Postgres job queue when
``JOBS_BACKEND__import_form=postgres``, otherwise as a background task in the
API process (resumable either way).
"""

from __future__ import annotations

import asyncio
import datetime as dt
from http import HTTPStatus
from typing import Optional, Set

from beanie import PydanticObjectId
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.intake import inspect_upload
from backend.app.services.pdf_import.storage import source_key
from common.db.flags import JobsBackend
from common.models.standard_form import StandardForm
from common.models.user import User

JOB_NAME = "import_form"
# waits before retrying an import whose sandbox was unreachable (in-process path)
RETRY_DELAYS_S = (5, 15, 30, 60, 120)


class PdfImportService:
    def __init__(
        self,
        repo,
        store,
        pipeline,
        workspace_form_service,
        workspace_user_service,
        settings,
        flags=None,
    ):
        self._repo = repo
        self._store = store
        self._pipeline = pipeline
        self._workspace_forms = workspace_form_service
        self._workspace_users = workspace_user_service
        self._settings = settings
        self._flags = flags
        self._running: Set[asyncio.Task] = set()

    @property
    def max_bytes(self) -> int:
        return self._settings.MAX_BYTES

    async def start(
        self,
        workspace_id: PydanticObjectId,
        data: bytes,
        file_name: Optional[str],
        user: User,
    ) -> FormImportDocument:
        await self._workspace_users.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        try:
            upload = inspect_upload(data, file_name, self._settings.MAX_BYTES)
        except DocumentRefused as refused:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST,
                {"code": refused.code, "message": refused.message},
            )
        await self._check_limits(workspace_id)

        form = await self._workspace_forms.create_form(
            workspace_id=workspace_id,
            form=StandardForm(title=upload.title, fields=[]),
            user=user,
        )
        import_id = PydanticObjectId()
        key = source_key(workspace_id, form.form_id, import_id, upload.extension)
        await self._store.put(key, data, upload.content_type)
        record = FormImportDocument(
            id=import_id,
            workspace_id=workspace_id,
            form_id=form.form_id,
            created_by=user.id,
            file_name=(file_name or upload.title)[:255],
            content_type=upload.content_type,
            size_bytes=upload.size_bytes,
            sha256=upload.sha256,
            source_key=key,
        )
        record = await self._repo.save(record)
        await self._dispatch(record.id)
        return record

    async def _check_limits(self, workspace_id: PydanticObjectId) -> None:
        s = self._settings
        if (
            await self._repo.count_active(workspace_id)
            >= s.CONCURRENT_IMPORTS_PER_WORKSPACE
        ):
            raise HTTPException(
                HTTPStatus.TOO_MANY_REQUESTS,
                {
                    "code": "import_in_progress",
                    "message": "Another import is still running in this workspace. Please wait for it to finish.",
                },
            )
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        if (
            await self._repo.count_created_since(workspace_id, since)
            >= s.IMPORTS_PER_WORKSPACE_PER_DAY
        ):
            raise HTTPException(
                HTTPStatus.TOO_MANY_REQUESTS,
                {
                    "code": "daily_limit",
                    "message": f"This workspace has reached {s.IMPORTS_PER_WORKSPACE_PER_DAY} imports in the last 24 hours. Please try again later.",
                },
            )

    def _on_postgres(self) -> bool:
        return (
            self._flags is not None
            and self._flags.jobs_backend(JOB_NAME) is JobsBackend.POSTGRES
        )

    async def _dispatch(self, import_id: PydanticObjectId) -> None:
        if self._on_postgres():
            from backend.jobs import tasks

            await tasks.import_form.configure(
                queueing_lock=f"import_form:{import_id}"
            ).defer_async(import_id=str(import_id))
            return
        task = asyncio.create_task(self._run_in_process(import_id))
        self._running.add(task)
        task.add_done_callback(self._running.discard)

    async def _run_in_process(self, import_id: PydanticObjectId) -> None:
        from backend.app.services.pdf_import.sandbox import SandboxUnavailable

        for delay in RETRY_DELAYS_S + (None,):
            try:
                await self._pipeline.run(import_id)
                return
            except SandboxUnavailable:
                if delay is None:
                    logger.error(
                        "form import {} gave up waiting for the sandbox", import_id
                    )
                    return
                await asyncio.sleep(delay)
            except Exception:  # noqa: BLE001 — the pipeline records its own failures
                logger.exception("form import {} could not run", import_id)
                return

    async def wait_for_background_imports(self) -> None:
        """Tests and shutdown: let in-process imports finish."""
        while self._running:
            await asyncio.gather(*list(self._running), return_exceptions=True)

    async def get(
        self, workspace_id: PydanticObjectId, import_id: PydanticObjectId, user: User
    ) -> FormImportDocument:
        await self._workspace_users.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        record = await self._repo.get(import_id)
        if record is None or record.workspace_id != workspace_id:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Import not found.")
        return record

    async def list(self, workspace_id: PydanticObjectId, user: User):
        await self._workspace_users.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        return await self._repo.list_by_workspace(workspace_id)

    async def delete_for_forms(self, form_ids) -> None:
        """Import records go with their forms (the stored originals are removed
        with the form's private folder)."""
        if form_ids:
            await self._repo.delete_by_form_ids(list(form_ids))
