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

from common.ids import RecordId
from loguru import logger

from backend.app.repositories.postgres.forms import (
    ImportLimitReached,
    check_import_limits,
)
from backend.app.exceptions import HTTPException
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.services.pdf_import.compile import clean_label
from backend.app.services.pdf_import.analysis import DocumentRefused
from backend.app.services.pdf_import.intake import inspect_upload
from backend.app.services.pdf_import.storage import source_key
from backend.app.models.enum.permission import Permission
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
        authorization_service,
        settings,
        flags=None,
        ai_admission=None,
    ):
        self._repo = repo
        # async (workspace id, user) -> None: the AI rate limits and daily
        # budget for an upload that asks for AI structuring (429 when over)
        self._ai_admission = ai_admission
        self._store = store
        self._pipeline = pipeline
        self._workspace_forms = workspace_form_service
        self._authorization = authorization_service
        self._settings = settings
        self._flags = flags
        self._running: Set[asyncio.Task] = set()

    @property
    def max_bytes(self) -> int:
        return self._settings.MAX_BYTES

    async def start(
        self,
        workspace_id: RecordId,
        data: bytes,
        file_name: Optional[str],
        user: User,
        ai_consent: bool = False,
    ) -> FormImportDocument:
        await self._authorization.authorize(user, Permission.FORM_CREATE, workspace_id)
        try:
            upload = inspect_upload(data, file_name, self._settings.MAX_BYTES)
        except DocumentRefused as refused:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST,
                {"code": refused.code, "message": refused.message},
            )
        # an import whose process died (e.g. in a deploy) must not hold the
        # slot forever: expire it first, under the limit check's lock
        try:
            await self.expire_stale(workspace_id)
        except ImportLimitReached as reached:
            raise self._limit_error(reached.code) from None
        # a cheap early look, so a refused upload creates nothing; the real
        # check is the atomic insert below
        await self._check_limits(workspace_id)
        if ai_consent is True and self._ai_admission is not None:
            await self._ai_admission(workspace_id, user)

        form = await self._workspace_forms.create_form(
            workspace_id=workspace_id,
            form=StandardForm(title=upload.title, fields=[]),
            user=user,
        )
        import_id = RecordId()
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

    def _stale_before(self) -> dt.datetime:
        return dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            seconds=self._settings.STALE_AFTER_S
        )

    async def expire_stale(self, workspace_id: RecordId) -> int:
        """Fail the workspace's imports that stopped making progress (no
        heartbeat for ``STALE_AFTER_S``: their job's process died) with
        ``interrupted``, under the lock the limit check takes, and remove
        their drafts like any failed import's (a draft the user already
        changed stays). Returns how many were expired."""
        expired = await self._repo.expire_stale(
            workspace_id, self._stale_before(), dt.datetime.now(dt.timezone.utc)
        )
        for record in expired:
            logger.warning(
                "form import {} expired as {}: no progress for {}s",
                record.id,
                record.error_code,
                self._settings.STALE_AFTER_S,
            )
            form_id = record.form_id
            await self._pipeline.discard_draft(record)
            if record.form_id != form_id:
                await self._repo.save(record)
        return len(expired)

    async def expire_stale_everywhere(self) -> int:
        """The periodic sweep: expire stale imports in every workspace (each
        under its own workspace's lock)."""
        total = 0
        for workspace_id in await self._repo.stale_workspaces(self._stale_before()):
            try:
                total += await self.expire_stale(workspace_id)
            except Exception:  # noqa: BLE001 — one workspace never stops the sweep
                logger.exception(
                    "could not expire stale form imports of workspace {}", workspace_id
                )
        return total

    async def _remove_draft(self, workspace_id, form_id: str) -> None:
        try:
            await self._workspace_forms.delete_draft_form(workspace_id, form_id)
        except Exception:  # noqa: BLE001 — never hide why the start failed
            logger.exception("could not remove the draft form of a refused import")

    async def _check_limits(self, workspace_id: RecordId) -> None:
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

    async def _dispatch(self, import_id: RecordId) -> None:
        if self._on_postgres():
            from backend.jobs import tasks

            await tasks.import_form.configure(
                queueing_lock=f"import_form:{import_id}"
            ).defer_async(import_id=str(import_id))
            return
        task = asyncio.create_task(self._run_in_process(import_id))
        self._running.add(task)
        task.add_done_callback(self._finished)

    def _finished(self, task: asyncio.Task) -> None:
        """Nothing awaits an in-process import, so its outcome is retrieved
        here: an exception left on a finished task is logged by asyncio only
        when the task is collected, with whatever its traceback holds.
        ``_run_in_process`` handles its own errors; this is the backstop."""
        self._running.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error(
                "a form import task ended with {}", type(task.exception()).__name__
            )

    async def _run_in_process(self, import_id: RecordId) -> None:
        try:
            # the heartbeat covers the retry waits too
            await self._pipeline.keep_alive(import_id, self._attempts(import_id))
        except Exception:  # noqa: BLE001 — recorded on the import below
            logger.exception("form import {} could not run", import_id)
            try:
                await self._pipeline.fail(import_id)
            except Exception:  # noqa: BLE001 — expired as interrupted later
                logger.exception("form import {} could not be marked failed", import_id)

    async def _attempts(self, import_id: RecordId) -> None:
        """The run, retried while the sandbox is unreachable. Any other error
        reaches ``_run_in_process``, which fails the import."""
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

    async def wait_for_background_imports(self) -> None:
        """Tests and shutdown: let in-process imports finish."""
        while self._running:
            await asyncio.gather(*list(self._running), return_exceptions=True)

    async def get(
        self, workspace_id: RecordId, import_id: RecordId, user: User
    ) -> FormImportDocument:
        await self._authorization.authorize(user, Permission.FORM_CREATE, workspace_id)
        record = await self._repo.get(import_id)
        if record is None or record.workspace_id != workspace_id or not record.is_pdf():
            raise HTTPException(HTTPStatus.NOT_FOUND, "Import not found.")
        if record.is_stale(self._stale_before()):
            # the progress screen polls this: an interrupted import says so
            # instead of running forever
            try:
                if await self.expire_stale(workspace_id):
                    record = await self._repo.get(import_id) or record
            except Exception:  # noqa: BLE001 — reading never fails on the expiry
                logger.exception("could not expire form import {}", import_id)
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

    async def list(self, workspace_id: RecordId, user: User):
        await self._authorization.authorize(user, Permission.FORM_CREATE, workspace_id)
        # imports of other products' forms (Open Formulieren) have their own
        # screens; the PDF list shows PDF imports only
        return [
            r for r in await self._repo.list_by_workspace(workspace_id) if r.is_pdf()
        ]

    async def delete_for_forms(self, form_ids) -> None:
        """Import records go with their forms (the stored originals are removed
        with the form's private folder)."""
        if form_ids:
            await self._repo.delete_by_form_ids(list(form_ids))

    async def ai_provider(self, workspace_id, user) -> dict:
        """The provider page text and images would go to with consent: its
        public name, whether this instance has it configured, and whether the
        workspace has opted in to AI (#715). Without the opt-in it names the
        instance default, which is what an admin would be asked to allow."""
        from backend.app.container import container
        from backend.app.services.ai.consent import (
            default_provider,
            provider_configured,
            provider_name,
        )

        await self._authorization.authorize(user, Permission.FORM_CREATE, workspace_id)
        consented = await container.ai_consent_service().consented_provider(
            workspace_id
        )
        provider = consented or default_provider()
        return {
            "provider": provider_name(provider),
            "available": provider_configured(provider),
            "enabled": consented is not None,
        }

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
