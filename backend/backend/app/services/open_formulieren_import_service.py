"""Import a form exported from Open Formulieren as a draft form.

``start`` reads the uploaded archive (untrusted: ``open_formulieren.archive``),
builds the draft in memory through the edit operations
(``open_formulieren.importer``) and saves it once as a draft of the workspace,
never published. The report of what was dropped, changed or flagged is stored
on a ``FormImportDocument`` (``source_kind = "open_formulieren"``, no
uploaded file kept) and the form's workspace settings carry the
"needs review" mark until its creator clears it.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
from http import HTTPStatus
from typing import Any, Dict, Optional

from common.ids import RecordId
from common.models.user import User
from loguru import logger
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.schemas.form_import import FormImportDocument, ImportStatus
from backend.app.services.open_formulieren.archive import read_archive
from backend.app.services.open_formulieren import budget, limits
from backend.app.services.open_formulieren.errors import ImportRefused, unexpected
from backend.app.services.open_formulieren.importer import Built, build_draft
from backend.app.services.open_formulieren.mapping import SOURCE_KIND
from backend.app.services.open_formulieren.text import label_text
from backend.app.services.open_formulieren_mode import refuse_open_formulieren_import
from backend.config import settings

NOT_FOUND_CODE = "import_not_found"
# the status of the stand-in answered for a report that is gone (never stored)
REPORT_REMOVED = "removed"
# how long the note of a refused attempt is kept (it is only counted per day)
ATTEMPT_RETENTION = dt.timedelta(days=2)


# Imports building at once in this process: decoding and building are
# CPU-bound, hold the interpreter lock and cannot be cancelled, so only a few
# run together; another gets 503 import_busy (retry later). Created on first
# use, so it belongs to the running event loop.
_SLOTS: Optional[asyncio.Semaphore] = None


def _slots() -> asyncio.Semaphore:
    global _SLOTS
    if _SLOTS is None:
        _SLOTS = asyncio.Semaphore(limits.MAX_CONCURRENT_IMPORTS)
    return _SLOTS


def _build(data: bytes) -> tuple:
    """CPU-bound: decode and build, within one work budget. Returns
    (archive version, Built). Anything unexpected from the file's content is a
    refusal of the archive."""
    with budget.scope():
        try:
            archive = read_archive(data)
            return archive.version, build_draft(archive)
        except ImportRefused:
            raise
        except Exception as error:  # noqa: BLE001
            raise unexpected(error) from None


def _refusal(error: ImportRefused) -> HTTPException:
    return HTTPException(error.status, content=error.content())


def _not_found() -> HTTPException:
    return HTTPException(
        HTTPStatus.NOT_FOUND,
        content={"code": NOT_FOUND_CODE, "message": "Import not found."},
    )


class OpenFormulierenImportService:
    def __init__(
        self,
        repo,
        workspace_form_service,
        workspace_form_repo,
        authorization_service,
    ):
        self._repo = repo
        self._workspace_forms = workspace_form_service
        self._workspace_form_repo = workspace_form_repo
        self._authorization = authorization_service

    async def authorize_start(self, workspace_id: RecordId, user: User) -> None:
        """Who may start an import: the same check as creating a form. Called
        before the upload is read."""
        refuse_open_formulieren_import()
        await self._authorization.authorize(user, Permission.FORM_CREATE, workspace_id)
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)

    async def start(
        self, workspace_id: RecordId, data: bytes, file_name: Optional[str], user: User
    ) -> FormImportDocument:
        await self.authorize_start(workspace_id, user)
        await self._check_daily_limit(workspace_id)
        slots = _slots()
        if slots.locked():
            raise HTTPException(
                HTTPStatus.SERVICE_UNAVAILABLE,
                content={
                    "code": "import_busy",
                    "message": "Other imports are running. Please try again in a moment.",
                },
                headers={"Retry-After": "5"},
            )
        try:
            async with slots:
                version, built = await run_in_threadpool(_build, data)
        except ImportRefused as refused:
            await self._record_refusal(workspace_id, data, file_name, user, refused.code)
            raise _refusal(refused) from None

        form = await self._workspace_forms.create_form(
            workspace_id=workspace_id, form=built.form, user=user
        )
        now = dt.datetime.now(dt.timezone.utc)
        record = FormImportDocument(
            id=RecordId(),
            workspace_id=workspace_id,
            form_id=form.form_id,
            created_by=str(user.id),
            status=ImportStatus.COMPLETED,
            source_kind=SOURCE_KIND,
            file_name=(label_text(file_name, 255) or "export.zip"),
            content_type="application/zip",
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            # the archive itself is never kept
            source_key="",
            report=_stored_report(version, built),
            started_at=now,
            finished_at=now,
        )
        try:
            await self._repo.save(record)
            await self._mark(workspace_id, form.form_id, record, needs_review=True)
        except BaseException:
            # nothing was imported: take the new draft (and the record) away
            await self._remove(workspace_id, form.form_id)
            raise
        # as stored (the database keeps milliseconds)
        return await self._repo.get(record.id) or record

    async def _check_daily_limit(self, workspace_id: RecordId) -> None:
        """Open Formulieren imports have limits of their own, not shared with
        the PDF import's: imports made per day, and attempts per day (refused
        archives count, so looping hostile ones does not hold the permits).
        A cheap look before any work: a burst of parallel uploads may pass it
        together by a few."""
        since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
        for limit, status in (
            (settings.open_formulieren.ATTEMPTS_PER_WORKSPACE_PER_DAY, None),
            (
                settings.open_formulieren.IMPORTS_PER_WORKSPACE_PER_DAY,
                ImportStatus.COMPLETED,
            ),
        ):
            done = await self._repo.count_created_since(
                workspace_id, since, kind=SOURCE_KIND, status=status
            )
            if done >= limit:
                raise HTTPException(
                    HTTPStatus.TOO_MANY_REQUESTS,
                    content={
                        "code": "import_limit",
                        "message": "This workspace has reached its limit of imports for the last 24 hours. Please try again later.",
                    },
                )

    async def expire_attempts(self) -> int:
        """Delete the notes of refused attempts older than ATTEMPT_RETENTION
        (the periodic sweep). Returns how many were deleted."""
        return await self._repo.delete_failed_attempts_before(
            dt.datetime.now(dt.timezone.utc) - ATTEMPT_RETENTION, kind=SOURCE_KIND
        )

    async def _record_refusal(
        self,
        workspace_id: RecordId,
        data: bytes,
        file_name: Optional[str],
        user: User,
        code: str,
    ) -> None:
        """A refused archive still counts as an attempt: a small record with
        no content (the reason, its size and hash; not its name). It is only
        needed for the daily count and expires after ATTEMPT_RETENTION."""
        now = dt.datetime.now(dt.timezone.utc)
        try:
            await self._repo.save(
                FormImportDocument(
                    id=RecordId(),
                    workspace_id=workspace_id,
                    form_id=None,
                    created_by=str(user.id),
                    status=ImportStatus.FAILED,
                    error_code=code,
                    source_kind=SOURCE_KIND,
                    # nothing from the file but its size and hash: not its name
                    # (it can hold a person's), not its content
                    file_name="",
                    content_type="application/zip",
                    size_bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    source_key="",
                    started_at=now,
                    finished_at=now,
                )
            )
        except Exception:  # noqa: BLE001 — the refusal itself is what is reported
            logger.error("could not record a refused Open Formulieren import")

    async def get(
        self, workspace_id: RecordId, import_id: RecordId, user: User
    ) -> FormImportDocument:
        refuse_open_formulieren_import()
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        return await self._record(workspace_id, import_id)

    async def review(
        self, workspace_id: RecordId, import_id: RecordId, reviewed: bool, user: User
    ) -> FormImportDocument:
        """Mark the import reviewed (or not). Not behind the import switch
        and not tied to the report: the mark lives on the forms (the draft
        and its copies) and publishing waits for it, so it can always be
        cleared by whoever may edit forms here, also when the import is
        switched off or the report is gone."""
        if not reviewed:
            # outside the switch the review call only clears the mark
            refuse_open_formulieren_import()
        await self._authorization.authorize(user, Permission.FORM_EDIT, workspace_id)
        if await self._repo.get(import_id) is None:
            return await self._review_without_report(
                workspace_id, import_id, reviewed, user
            )
        record = await self._record(workspace_id, import_id)
        needs_review = not reviewed
        if bool(record.report.get("needsReview")) != needs_review:
            record.report = {**record.report, "needsReview": needs_review}
            await self._repo.save(record)
        if record.form_id:
            await self._mark(workspace_id, record.form_id, record, needs_review)
        # a copy of the draft carries the same mark (duplicate_form): looking
        # over the report clears (or sets) it there too
        await self._workspace_form_repo.set_review_mark_by_import(
            workspace_id, str(record.id), needs_review
        )
        return record

    async def _review_without_report(
        self, workspace_id: RecordId, import_id: RecordId, reviewed: bool, user: User
    ) -> FormImportDocument:
        """The report is gone (deleted with the form it was made for) but
        copies of that form still carry its mark: clear it on the forms of
        this workspace that name the import. Nothing else can be said about
        the import, so only clearing is possible, and a mark that names no
        form here is a 404 like any unknown import."""
        if not reviewed:
            raise _not_found()
        named = await self._workspace_form_repo.set_review_mark_by_import(
            workspace_id, str(import_id), needs_review=False
        )
        if not named:
            raise _not_found()
        return FormImportDocument(
            id=import_id,
            workspace_id=workspace_id,
            created_by=str(user.id),
            status=REPORT_REMOVED,
            source_kind=SOURCE_KIND,
            file_name="",
            content_type="",
            size_bytes=0,
            sha256="",
            source_key="",
            report={"needsReview": False},
        )

    # ---------------------------------------------------------------- helpers

    async def _record(self, workspace_id, import_id) -> FormImportDocument:
        record = await self._repo.get(import_id)
        if (
            record is None
            # a refused attempt is a note for the daily count, not an import
            or (record.status == ImportStatus.FAILED and not record.form_id)
            or record.source_kind != SOURCE_KIND
            or str(record.workspace_id) != str(workspace_id)
        ):
            raise _not_found()
        return record

    async def _mark(
        self, workspace_id, form_id: str, record: FormImportDocument, needs_review: bool
    ) -> None:
        """The form's own mark, on its link to the workspace."""
        await self._workspace_form_repo.set_review_mark(
            workspace_id, str(form_id), needs_review, SOURCE_KIND, str(record.id)
        )

    async def _remove(self, workspace_id, form_id: str) -> None:
        try:
            await self._workspace_forms.delete_draft_form(workspace_id, form_id)
            await self._repo.delete_by_form_ids([form_id])
        except Exception:  # noqa: BLE001 — never hide why the import failed
            logger.exception("could not remove the draft of a failed import")


def _stored_report(version: str, built: Built) -> Dict[str, Any]:
    return {
        "sourceVersion": version,
        "needsReview": True,
        "summary": built.summary,
        "truncated": built.report.truncated,
        "items": built.report.items,
    }
