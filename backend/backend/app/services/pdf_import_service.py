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
from backend.app.repositories.form_import_repository import (
    ImportLimitReached,
    check_import_limits,
)
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.services.pdf_import.compile import clean_label
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.intake import inspect_upload
from backend.app.services.pdf_import.storage import source_key
from common.db.flags import JobsBackend
from common.models.standard_form import StandardForm
from common.models.user import User

JOB_NAME = "import_form"
# waits before retrying an import whose sandbox was unreachable (in-process path)
RETRY_DELAYS_S = (5, 15, 30, 60, 120)


def _day_ago() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)


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
        ai_consent: bool = False,
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
        # a cheap early look, so a refused upload creates nothing; the real
        # check is the atomic insert below
        await self._check_limits(workspace_id)

        form = await self._workspace_forms.create_form(
            workspace_id=workspace_id,
            form=StandardForm(title=upload.title, fields=[]),
            user=user,
        )
        import_id = PydanticObjectId()
        key = source_key(workspace_id, form.form_id, import_id, upload.extension)
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
            ai_consent=ai_consent is True,
            ai_consent_at=(
                dt.datetime.now(dt.timezone.utc) if ai_consent is True else None
            ),
            ai_consent_by=str(user.id) if ai_consent is True else None,
        )
        try:
            await self._store.put(key, data, upload.content_type)
            record = await self._repo.create_within_limits(
                record,
                self._settings.CONCURRENT_IMPORTS_PER_WORKSPACE,
                self._settings.IMPORTS_PER_WORKSPACE_PER_DAY,
                _day_ago(),
            )
        except BaseException as error:
            # nothing was imported: take the new draft (and the original in
            # its folder) away again
            await self._remove_draft(workspace_id, form.form_id)
            if isinstance(error, ImportLimitReached):
                raise self._limit_error(error.code) from None
            raise
        await self._dispatch(record.id)
        return record

    async def _remove_draft(self, workspace_id, form_id: str) -> None:
        try:
            await self._workspace_forms.delete_draft_form(workspace_id, form_id)
        except Exception:  # noqa: BLE001 — never hide why the start failed
            logger.exception("could not remove the draft form of a refused import")

    async def _check_limits(self, workspace_id: PydanticObjectId) -> None:
        s = self._settings
        try:
            check_import_limits(
                await self._repo.count_active(workspace_id),
                await self._repo.count_created_since(workspace_id, _day_ago()),
                s.CONCURRENT_IMPORTS_PER_WORKSPACE,
                s.IMPORTS_PER_WORKSPACE_PER_DAY,
            )
        except ImportLimitReached as reached:
            raise self._limit_error(reached.code) from None

    def _limit_error(self, code: str) -> HTTPException:
        if code == "daily_limit":
            message = f"This workspace has reached {self._settings.IMPORTS_PER_WORKSPACE_PER_DAY} imports in the last 24 hours. Please try again later."
        else:
            message = "Another import is still running in this workspace. Please wait for it to finish."
        return HTTPException(
            HTTPStatus.TOO_MANY_REQUESTS, {"code": code, "message": message}
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
                    await self._pipeline.give_up(import_id)
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

    async def _with_draft(self, workspace_id, import_id, user) -> FormImportDocument:
        """The import, if its draft form (and so its files) still exists: a
        failed import removes its empty draft together with the files."""
        record = await self.get(workspace_id, import_id, user)
        if not record.form_id:
            raise HTTPException(
                HTTPStatus.NOT_FOUND, "This import has no draft form any more."
            )
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

    async def ai_provider(self, workspace_id, user) -> dict:
        """The provider page text and images would go to with consent: its
        public name and whether this instance has it configured."""
        from backend.config import settings

        await self._workspace_users.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        default = (settings.ai.DEFAULT_PROVIDER or "openai").lower()
        if default == "google":
            name, available = "Google Gemini", bool(settings.google_ai.API_KEY)
        elif default == "compatible":
            name = "this instance's own AI model"
            available = bool(settings.ai.COMPAT_BASE_URL and settings.ai.COMPAT_MODEL)
        else:
            name, available = "OpenAI", bool(settings.open_ai.API_KEY)
        return {"provider": name, "available": available}

    async def page_image(self, workspace_id, import_id, number: int, user) -> bytes:
        """A rendered page, for the review screen (members of the workspace only)."""
        record = await self._with_draft(workspace_id, import_id, user)
        pages = {
            p["number"]: p["key"]
            for p in (record.stages.get("render") or {}).get("pages", [])
        }
        if number not in pages:
            raise HTTPException(HTTPStatus.NOT_FOUND, "No image for this page.")
        return await self._store.get(pages[number])

    async def review(self, workspace_id, import_id, user) -> dict:
        """What the review screen shows: per page its size, whether an image
        exists, and where each imported question came from."""
        import json

        from backend.app.services.pdf_import.storage import artifact_key

        record = await self._with_draft(workspace_id, import_id, user)

        async def load(name, stage):
            if stage not in record.stages:
                return {}  # that stage has not run (yet): no artifact
            key = artifact_key(record.source_key, name)
            try:
                return json.loads(await self._store.get(key))
            except Exception:
                # a finished stage's artifact must be there: a store outage or
                # a corrupt file is an error, not "no boxes" (key only, no content)
                logger.error("form import {} could not read {}", record.id, key)
                raise

        fdm = await load("fdm.json", "structure")
        layout = await load("layout.json", "layout")
        text = await load("text.json", "text")
        primitives = {
            p["id"]: p
            for page in layout.get("pages") or []
            for p in page.get("primitives") or []
        }
        words = {
            page["number"]: page.get("words") or [] for page in text.get("pages") or []
        }
        images = {
            p["number"] for p in (record.stages.get("render") or {}).get("pages", [])
        }
        pages = []
        for page in record.pages:
            boxes = []
            for e in fdm.get("elements") or []:
                if not isinstance(e, dict):
                    continue
                if e.get("page") != page.number or e.get("type") not in (
                    "question",
                    "staff_only",
                ):
                    continue
                parts = [
                    primitives[r]["bbox"]
                    for r in e.get("slot_refs") or e.get("refs") or []
                    if r in primitives
                ]
                for ref in e.get("label_refs") or []:
                    if ref.startswith("w") and ref[1:].isdigit():
                        i = int(ref[1:])
                        page_words = words.get(page.number) or []
                        if i < len(page_words):
                            w = page_words[i]
                            parts.append([w["x0"], w["top"], w["x1"], w["bottom"]])
                if not parts:
                    continue
                box = [
                    min(b[0] for b in parts),
                    min(b[1] for b in parts),
                    max(b[2] for b in parts),
                    max(b[3] for b in parts),
                ]
                boxes.append(
                    {
                        "id": e.get("id"),
                        "type": e.get("type"),
                        "kind": e.get("kind"),
                        "label": clean_label(e.get("label") or e.get("heading") or ""),
                        "confidence": e.get("confidence"),
                        # False: the wording is the model's, not found on the page
                        "grounded": e.get("grounded") is not False
                        and e.get("text_source") != "model",
                        "bbox": [round(v, 1) for v in box],
                    }
                )
            pages.append(
                {
                    "number": page.number,
                    "width": page.width,
                    "height": page.height,
                    "route": page.route,
                    "has_image": page.number in images,
                    "boxes": boxes,
                }
            )
        return {
            "id": str(record.id),
            "form_id": record.form_id,
            "status": record.status,
            "pages": pages,
            "report": record.report,
        }
