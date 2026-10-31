"""The responses export: stream a CSV for a small set, or run a background job
for a large one, and keep an audit entry of each (docs/response-export.md).

* **Who may.** ``response.export`` on the workspace (never a Privacy officer;
  Reviewers and Viewers only with an export grant), asked again by the job and
  at download. An export is its requester's: nobody else reads its status or
  its file.
* **Small sets** (``STREAM_MAX_ROWS`` or fewer matching responses) stream in the
  response: nothing is stored, memory is one batch.
* **Large sets** become a job on the jobs worker (argument: the export id). Its
  file is stored as encrypted chunks and handed out, as often as its requester
  asks, through short-lived signed links until ``FILE_TTL`` after it was built;
  it is deleted sooner by its requester (``discard``) or as soon as responses of
  the form are deleted. The job reads the live rows when it
  runs, so a response deleted before then is never in it.
* **Audit.** One row per export: who, when, form, row count, columns, filters
  (the search text only as "a search was used"), kind, state. Never an answer.
* **Limits.** ``REQUESTS_PER_WINDOW`` requests per user and form per
  ``WINDOW_SECONDS`` (429 with ``Retry-After``), one unfinished job per user and
  form (409), at most ``MAX_ROWS`` responses.
"""

from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from backend.app.exceptions import HTTPException
from backend.app.models.enum.permission import Permission
from backend.app.models.filter_queries.response_export import ResponseExportFilters
from backend.app.repositories.postgres.response_exports import (
    CHUNK_INVALIDATED,
    CHUNK_LOST,
    OpenExportExists,
    PostgresResponseExportRepository,
    WorkspaceBusy,
)
from backend.app.repositories.postgres.responses import PostgresFormResponseRepository
from backend.app.schemas.response_export import (
    ExportKind,
    ExportStatus,
    ResponseExportChunkDocument,
    ResponseExportDocument,
)
from backend.app.services.authorization_service import AuthorizationService
from backend.app.services.rate_limiter import FixedWindowRateLimiter
from backend.app.services.response_export import limits, links
from backend.app.services.response_export.table import (
    ExportPlan,
    ExportResponse,
    UnknownColumn,
    build_plan,
    column_catalogue,
    export_file_name,
)
from backend.app.services.response_export.writer import (
    RowCount,
    ResponseSource,
    write_export,
)
from common.clock import utcnow
from common.ids import RecordId
from common.models.user import User

FORM_NOT_FOUND = "Form not found in the workspace."
GONE_CODE = "export_gone"


def _error(status: HTTPStatus, code: str, message: str, **headers) -> HTTPException:
    return HTTPException(
        status_code=status,
        content={"code": code, "message": message},
        headers=headers or None,
    )


class _Superseded(Exception):
    """Another claim of the job took over: this run stops without touching anything."""


async def _settle(awaitable) -> None:
    """Finish bookkeeping that must outlive a cancelled request (a client that
    went away): shielded, so the cancellation does not cut it short."""
    task = asyncio.ensure_future(awaitable)
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        pass


@dataclass
class StreamStart:
    """A request answered by streaming: the export row, the file name and type
    and the bytes to send."""

    export: ResponseExportDocument
    file_name: str
    media_type: str
    body: AsyncIterator[bytes]


def _plain(value: Any) -> Any:
    """Answers as plain JSON data (a stored answer may come back as a model)."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def to_export_response(response) -> ExportResponse:
    """A decrypted stored response, as the export reads it."""
    hidden = response.hidden_fields if isinstance(response.hidden_fields, dict) else {}
    return ExportResponse(
        response_id=response.response_id,
        responder=response.dataOwnerIdentifier,
        created_at=response.created_at,
        answers=_plain(response.answers) if isinstance(response.answers, dict) else {},
        internal_answers=(
            _plain(response.internal_answers)
            if isinstance(getattr(response, "internal_answers", None), dict)
            else {}
        ),
        hidden_fields=hidden,
    )


class ResponseExportService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        form_response_service,
        form_repo,
        response_repo: PostgresFormResponseRepository,
        export_repo: PostgresResponseExportRepository,
        crypto,
        rate_limiter: FixedWindowRateLimiter,
        defer: Optional[Callable[[str], Awaitable[None]]] = None,
        clock: Callable[[], dt.datetime] = utcnow,
    ):
        self._authorization = authorization_service
        self._responses = form_response_service
        self._forms = form_repo
        self._response_repo = response_repo
        self._exports = export_repo
        self._crypto = crypto
        self._limiter = rate_limiter
        self._defer = defer or _defer_job
        self._clock = clock

    # ------------------------------------------------------------------ helpers
    async def _authorize(self, user: User, workspace_id: RecordId, form_id: str) -> None:
        await self._authorization.authorize(
            user, Permission.RESPONSE_EXPORT, workspace_id, form_id=form_id
        )

    async def _form(self, form_id: str) -> Dict[str, Any]:
        document = await self._forms.get_form_document_by_id(form_id)
        if document is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, FORM_NOT_FOUND)
        return document.model_dump(mode="json", exclude_none=True)

    def _source(
        self, workspace_id: RecordId, scope, filters: Optional[ResponseExportFilters]
    ) -> ResponseSource:
        """A fresh pass over the matching responses, decrypted batch by batch."""

        async def rows() -> AsyncIterator[ExportResponse]:
            after: Optional[str] = None
            while True:
                batch = await self._response_repo.export_batch(
                    scope, filters, after_id=after, limit=limits.BATCH_SIZE
                )
                if not batch:
                    return
                after = str(batch[-1].id)
                decrypted = await run_in_threadpool(
                    lambda b=batch: [
                        to_export_response(
                            self._responses.decrypt_form_response(
                                workspace_id=workspace_id, response=r
                            )
                        )
                        for r in b
                        if r.answers is not None
                    ]
                )
                for response in decrypted:
                    yield response
                if len(batch) < limits.BATCH_SIZE:
                    return

        return rows

    def _seal(self, export: ResponseExportDocument, params: Dict[str, Any]) -> str:
        sealed = self._crypto_service().encrypt(
            export.workspace_id,
            export.form_id,
            json.dumps(params).encode(),
            context=b"export-params|" + str(export.id).encode(),
        )
        return base64.b64encode(sealed).decode()

    def _unseal(self, export: ResponseExportDocument) -> Dict[str, Any]:
        raw = base64.b64decode(export.params_sealed or "")
        plain = self._crypto_service().decrypt(
            export.workspace_id,
            export.form_id,
            raw,
            context=b"export-params|" + str(export.id).encode(),
        )
        return json.loads(plain)

    def _crypto_service(self):
        return self._crypto

    # --------------------------------------------------------------- the catalogue
    async def columns(self, workspace_id: RecordId, form_id: str, user: User) -> List[Dict[str, str]]:
        await self._authorize(user, workspace_id, form_id)
        return column_catalogue(await self._form(form_id))

    # ----------------------------------------------------------- the bulk JSON route
    async def bulk_read(self, workspace_id: RecordId, form_id: str, user: User):
        """``GET .../all-submissions``: every response of the form as decrypted
        JSON. It is an export like any other, so it takes the same permission,
        rate limit and audit entry (channel ``all_submissions``, one row per
        read, never an answer)."""
        await self._authorize(user, workspace_id, form_id)
        verdict = await self._limiter.hit(
            f"response-export:{workspace_id}:{form_id}",
            str(user.id),
            limits.REQUESTS_PER_WINDOW,
            limits.WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate_limited",
                f"Too many exports of this form. Try again in {verdict.retry_after} seconds.",
                **{"Retry-After": str(verdict.retry_after)},
            )
        now = self._clock()
        entry = ResponseExportDocument(
            workspace_id=workspace_id,
            form_id=form_id,
            actor_id=str(user.id),
            channel="all_submissions",
            kind=ExportKind.STREAM,
            status=ExportStatus.STREAMING,
            format="json",
            started_at=now,
        ).ensure_id()
        await self._exports.save(entry)
        try:
            responses = await self._responses.get_workspace_form_all_submissions(
                form_id, workspace_id, user
            )
        except BaseException:
            await _settle(self._finish_stream(entry, 0, False))
            raise
        await _settle(self._finish_stream(entry, len(responses), True))
        return responses

    # ------------------------------------------------------------------- request
    async def request(
        self,
        workspace_id: RecordId,
        form_id: str,
        user: User,
        columns: Optional[List[str]],
        filters: ResponseExportFilters,
    ):
        """Admit an export: a ``StreamStart`` to send, or the queued job's row.
        Raises 403/404, 422 (an unknown column), 429, 409 and 413."""
        await self._authorize(user, workspace_id, form_id)
        form = await self._form(form_id)
        try:
            plan = build_plan(form, columns)
        except UnknownColumn as unknown:
            raise _error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "unknown_column",
                f"This form has no column {str(unknown)!r}.",
            ) from None
        if not plan.columns:
            raise _error(HTTPStatus.UNPROCESSABLE_ENTITY, "no_columns", "Choose at least one column.")

        verdict = await self._limiter.hit(
            f"response-export:{workspace_id}:{form_id}",
            str(user.id),
            limits.REQUESTS_PER_WINDOW,
            limits.WINDOW_SECONDS,
        )
        if not verdict.allowed:
            raise _error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate_limited",
                f"Too many exports of this form. Try again in {verdict.retry_after} seconds.",
                **{"Retry-After": str(verdict.retry_after)},
            )

        scope = await self._responses.scope(workspace_id, [form_id])
        count = await self._response_repo.count_for_export(scope, filters)
        if count > limits.MAX_ROWS:
            raise _error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "too_many_rows",
                f"This export would hold {count} responses; at most {limits.MAX_ROWS} fit in one. "
                "Narrow it with filters (for example submittedFrom and submittedTo).",
            )
        file_format = "zip" if plan.group_tables else "csv"
        export = ResponseExportDocument(
            workspace_id=workspace_id,
            form_id=form_id,
            actor_id=str(user.id),
            kind=ExportKind.STREAM if count <= limits.STREAM_MAX_ROWS else ExportKind.JOB,
            status=ExportStatus.STREAMING,
            format=file_format,
            columns=[c.key for c in plan.columns],
            filters=filters.audit_summary(),
            expected_rows=count,
            started_at=self._clock(),
        ).ensure_id()
        title = form.get("title") or ""
        file_name = export_file_name(title, extension=file_format)

        if export.kind == ExportKind.STREAM:
            await self._exports.save(export)
            return StreamStart(
                export=export,
                file_name=file_name,
                media_type="application/zip" if file_format == "zip" else "text/csv; charset=utf-8",
                body=self._stream(export, plan, title, workspace_id, scope, filters),
            )

        export.status = ExportStatus.QUEUED
        export.started_at = None
        export.file_name = file_name
        export.params_sealed = self._seal(
            export,
            {
                "filters": json.loads(filters.model_dump_json()),
                "columns": columns,
            },
        )
        try:
            await self._exports.admit_job(export, limits.WORKSPACE_MAX_JOBS)
        except OpenExportExists:
            waiting = await self._exports.open_for(workspace_id, form_id, user.id)
            if waiting is not None and waiting.status == ExportStatus.READY:
                raise _error(
                    HTTPStatus.CONFLICT,
                    "export_ready",
                    "An export of this form is ready to download. Download it first.",
                ) from None
            raise _error(
                HTTPStatus.CONFLICT,
                "export_in_progress",
                "An export of this form is already being prepared.",
            ) from None
        except WorkspaceBusy:
            raise _error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "workspace_busy",
                "Several exports of this workspace are being prepared. Try again in a few minutes.",
                **{"Retry-After": "60"},
            ) from None
        await self._queue(export)
        return export

    async def _queue(self, export: ResponseExportDocument) -> bool:
        try:
            await self._defer(str(export.id))
            return True
        except Exception as error:  # noqa: BLE001 - the sweep queues it again
            logger.warning(
                "could not queue response export {} ({})", export.id, type(error).__name__
            )
            return False

    # ------------------------------------------------------------------ streaming
    async def _stream(
        self,
        export: ResponseExportDocument,
        plan: ExportPlan,
        title: str,
        workspace_id: RecordId,
        scope,
        filters: ResponseExportFilters,
    ) -> AsyncIterator[bytes]:
        counter = RowCount()
        finished = False
        try:
            async for piece in write_export(
                plan, title, self._source(workspace_id, scope, filters), counter
            ):
                yield piece
            finished = True
        finally:
            await _settle(self._finish_stream(export, counter.rows, finished))

    async def _finish_stream(self, export: ResponseExportDocument, rows: int, finished: bool) -> None:
        def done(document: ResponseExportDocument):
            document.row_count = rows
            document.finished_at = self._clock()
            document.status = ExportStatus.COMPLETED if finished else ExportStatus.CANCELLED
            document.error_code = None if finished else "interrupted"
            return document

        try:
            await self._exports.update_locked(export.id, done)
        except Exception as error:  # noqa: BLE001 - the audit row exists already
            logger.warning(
                "could not finish export {} ({})", export.id, type(error).__name__
            )

    # -------------------------------------------------------------------- the job
    async def run_job(self, export_id: str) -> str:
        """The job: build the file as encrypted chunks. Returns the status the
        export ended in. Never raises for a failed build: the row says so.

        A run owns the export only while its claim (``attempts``) is current:
        every chunk it stores and its final state are written under the row lock
        and refused once another claim has taken over (a worker presumed dead that
        was only slow), so two runs never mix chunks."""
        claimed = await self._exports.update_locked(export_id, self._claim)
        if claimed is None:
            found = await self._exports.get_by_id(export_id)
            return found.status.value if found else "missing"
        try:
            outcome = await self._build(claimed)
        except _Superseded:
            found = await self._exports.get_by_id(export_id)
            return found.status.value if found else "missing"
        except Exception as error:  # noqa: BLE001
            logger.warning("response export {} failed ({})", export_id, type(error).__name__)
            outcome = await self._end_owned(claimed, ExportStatus.FAILED, "build_failed")
        return outcome.value

    def _claim(self, document: ResponseExportDocument):
        stale = self._clock() - limits.STALE_RUNNING_AFTER
        if document.status == ExportStatus.QUEUED:
            pass
        elif (
            document.status == ExportStatus.RUNNING
            and document.started_at is not None
            and document.started_at < stale
        ):
            pass
        else:
            return None
        document.status = ExportStatus.RUNNING
        document.started_at = self._clock()
        document.attempts += 1
        return document

    async def _end(
        self, export_id, status: ExportStatus, error_code: Optional[str] = None
    ) -> ExportStatus:
        def change(document: ResponseExportDocument):
            document.status = status
            document.error_code = error_code
            document.finished_at = self._clock()
            document.params_sealed = None
            document.expires_at = None
            return document

        updated = await self._exports.update_locked(export_id, change)
        return updated.status if updated else status

    async def _end_owned(
        self, export: ResponseExportDocument, status: ExportStatus, error_code: Optional[str] = None
    ) -> ExportStatus:
        """End the export as ``status`` if this run still owns it, and delete the
        chunks it wrote (never those of a run that took over). Returns the state
        the export is in."""
        attempt = export.attempts

        def change(document: ResponseExportDocument):
            if document.status != ExportStatus.RUNNING or document.attempts != attempt:
                return None
            document.status = status
            document.error_code = error_code
            document.finished_at = self._clock()
            document.params_sealed = None
            document.expires_at = None
            return document

        updated = await self._exports.update_locked(export.id, change)
        if updated is None:
            found = await self._exports.get_by_id(export.id)
            return found.status if found else status
        await self._exports.delete_chunks(export.id)
        return updated.status

    async def _build(self, export: ResponseExportDocument) -> ExportStatus:
        workspace_id, form_id = export.workspace_id, export.form_id
        attempt = export.attempts
        params = self._unseal(export)
        filters = ResponseExportFilters.model_validate(params.get("filters") or {})
        actor = User(id=export.actor_id, sub=export.actor_id)
        # who asked may no longer be allowed (a role removed since)
        if not await self._authorization.has_permission(
            actor, Permission.RESPONSE_EXPORT, workspace_id, form_id=form_id
        ):
            return await self._end_owned(export, ExportStatus.CANCELLED, "permission_removed")
        document = await self._forms.get_form_document_by_id(form_id)
        if document is None:
            return await self._end_owned(export, ExportStatus.CANCELLED, "form_gone")
        form = document.model_dump(mode="json", exclude_none=True)
        try:
            plan = build_plan(form, params.get("columns"))
        except UnknownColumn:
            # the form changed between the request and the job
            return await self._end_owned(export, ExportStatus.FAILED, "columns_changed")
        scope = await self._responses.scope(workspace_id, [form_id])
        counter = RowCount()
        index = 0
        size = 0
        pending = bytearray()

        async def store(data: bytes) -> bool:
            """Encrypt and keep one chunk, if this run still owns the export (its
            heartbeat is written with it); False when the job must stop."""
            nonlocal index, size
            sealed = await run_in_threadpool(self._encrypt_chunk, export, index, data)
            result = await self._exports.add_chunk_if_owned(
                ResponseExportChunkDocument(
                    export_id=str(export.id),
                    workspace_id=workspace_id,
                    form_id=form_id,
                    index=index,
                    data=base64.b64encode(sealed).decode(),
                    attempt=attempt,
                ),
                attempt,
                self._clock(),
            )
            if result == CHUNK_LOST:
                raise _Superseded()
            index += 1
            size += len(data)
            return result != CHUNK_INVALIDATED

        stopped = False
        async for piece in write_export(
            plan, document.title or "", self._source(workspace_id, scope, filters), counter
        ):
            pending.extend(piece)
            if size + len(pending) > limits.MAX_FILE_BYTES:
                return await self._end_owned(export, ExportStatus.FAILED, "too_large")
            while len(pending) >= limits.CHUNK_BYTES:
                head, pending = bytes(pending[: limits.CHUNK_BYTES]), pending[limits.CHUNK_BYTES :]
                if not await store(head):
                    stopped = True
                    break
            if stopped:
                break
        if not stopped and pending:
            stopped = not await store(bytes(pending))
        if stopped:
            return await self._end_owned(export, ExportStatus.CANCELLED, "responses_deleted")

        ready_at = self._clock()
        outcome: List[str] = []

        def ready(row: ResponseExportDocument):
            if row.status != ExportStatus.RUNNING or row.attempts != attempt:
                outcome.append("lost")
                return None
            if row.invalidated_at is not None:
                outcome.append("invalidated")
                return None
            row.status = ExportStatus.READY
            row.row_count = counter.rows
            row.chunk_count = index
            row.file_size = size
            row.finished_at = ready_at
            row.expires_at = ready_at + limits.FILE_TTL
            row.params_sealed = None
            row.error_code = None
            return row

        if await self._exports.update_locked(export.id, ready) is None:
            if outcome and outcome[0] == "lost":
                raise _Superseded()
            # responses were deleted while the file was being finished
            return await self._end_owned(export, ExportStatus.CANCELLED, "responses_deleted")
        return ExportStatus.READY

    def _chunk_context(self, export: ResponseExportDocument, index: int) -> bytes:
        return f"export|{export.id}|{index}|{export.actor_id}".encode()

    def _encrypt_chunk(self, export: ResponseExportDocument, index: int, data: bytes) -> bytes:
        return self._crypto_service().encrypt(
            export.workspace_id, export.form_id, data, context=self._chunk_context(export, index)
        )

    def _decrypt_chunk(self, export: ResponseExportDocument, index: int, data: bytes) -> bytes:
        return self._crypto_service().decrypt(
            export.workspace_id, export.form_id, data, context=self._chunk_context(export, index)
        )

    # --------------------------------------------------------------------- status
    async def _mine(
        self, workspace_id: RecordId, form_id: str, export_id: str, user: User
    ) -> ResponseExportDocument:
        await self._authorize(user, workspace_id, form_id)
        export = await self._exports.get(workspace_id, form_id, export_id)
        # someone else's export is "not found", like an unknown one
        if export is None or export.actor_id != str(user.id):
            raise HTTPException(HTTPStatus.NOT_FOUND, "Export not found.")
        return await self._expire_if_due(export)

    async def _expire_if_due(self, export: ResponseExportDocument) -> ResponseExportDocument:
        if (
            export.status == ExportStatus.READY
            and export.expires_at is not None
            and export.expires_at <= self._clock()
        ):
            return await self._drop_file(export.id, ExportStatus.EXPIRED) or export
        return export

    async def _drop_file(self, export_id, status: ExportStatus) -> Optional[ResponseExportDocument]:
        def change(document: ResponseExportDocument):
            if document.status != ExportStatus.READY:
                return None
            document.status = status
            document.file_deleted_at = self._clock()
            document.expires_at = None
            return document

        updated = await self._exports.update_locked(export_id, change)
        if updated is not None:
            await self._exports.delete_chunks(export_id)
        return updated

    def present(self, export: ResponseExportDocument, user: User) -> Dict[str, Any]:
        """What the requester sees of an export: state, counts and, while the
        file is ready, a fresh signed link. Never anything of the answers."""
        view: Dict[str, Any] = {
            "id": str(export.id),
            "formId": str(export.form_id),
            "kind": export.kind.value,
            "status": export.status.value,
            "format": export.format,
            "createdAt": export.created_at,
            "rows": export.row_count if export.row_count is not None else export.expected_rows,
            "fileName": export.file_name,
            "fileSize": export.file_size,
            "expiresAt": export.expires_at,
            "downloadedAt": export.downloaded_at,
            "downloadCount": export.download_count,
            "errorCode": export.error_code,
        }
        if export.status == ExportStatus.READY:
            token = links.issue(export.id, export.workspace_id, export.form_id, user.id)
            view["downloadUrl"] = (
                f"/workspaces/{export.workspace_id}/forms/{export.form_id}"
                f"/exports/{export.id}/download?token={token}"
            )
            view["linkExpiresInSeconds"] = links.LINK_TTL_SECONDS
        return view

    async def status(self, workspace_id: RecordId, form_id: str, export_id: str, user: User):
        export = await self._mine(workspace_id, form_id, export_id, user)
        return self.present(export, user)

    async def recent(self, workspace_id: RecordId, form_id: str, user: User, limit: int = 5):
        """The requester's latest exports of the form that still matter to
        them: unfinished, with a file to fetch, or that ended without one in the
        last day."""
        await self._authorize(user, workspace_id, form_id)
        found = await self._exports.list_for_actor(workspace_id, form_id, user.id, limit=limit)
        views = []
        for export in found:
            export = await self._expire_if_due(export)
            if export.kind != ExportKind.JOB:
                continue
            if export.status in (ExportStatus.QUEUED, ExportStatus.RUNNING, ExportStatus.READY):
                views.append(self.present(export, user))
            elif export.status in (ExportStatus.FAILED, ExportStatus.CANCELLED):
                # a failure is news for a day, not on every visit for ever
                ended = export.finished_at or export.created_at
                if ended is not None and ended >= self._clock() - limits.FAILURE_NEWS_FOR:
                    views.append(self.present(export, user))
        return views

    # ------------------------------------------------------------------- download
    async def download(
        self,
        workspace_id: RecordId,
        form_id: str,
        export_id: str,
        token: str,
        user: User,
    ):
        """The ready file as ``(export, body)``, as often as its requester asks
        until it is deleted (24 hours after it was built, or sooner by
        ``discard`` or an erasure). 403 for a link that is not this user's or
        this export's, 410 for an expired link or a file that is gone."""
        await self._authorize(user, workspace_id, form_id)
        export = await self._exports.get(workspace_id, form_id, export_id)
        if export is None or export.actor_id != str(user.id):
            raise HTTPException(HTTPStatus.NOT_FOUND, "Export not found.")
        verdict = links.check(token, export.id, workspace_id, form_id, user.id)
        if verdict == links.INVALID:
            raise _error(HTTPStatus.FORBIDDEN, "invalid_link", "This download link is not valid.")
        if verdict == links.EXPIRED:
            raise _error(
                HTTPStatus.GONE,
                "link_expired",
                "This download link has expired. Open the export again for a new one.",
            )
        export = await self._expire_if_due(export)
        if export.status != ExportStatus.READY:
            raise _error(HTTPStatus.GONE, GONE_CODE, "This export is no longer available. Export again.")

        return export, self._file_body(export)

    async def _file_body(self, export: ResponseExportDocument) -> AsyncIterator[bytes]:
        complete = False
        try:
            for index in range(export.chunk_count or 0):
                chunk = await self._exports.get_chunk(export.id, index)
                if chunk is None or chunk.attempt != export.attempts:
                    # deleted under the reader (an erasure, or its time): the response breaks off
                    raise RuntimeError("export chunk missing")
                data = await run_in_threadpool(
                    self._decrypt_chunk, export, index, base64.b64decode(chunk.data)
                )
                yield data
            complete = True
        finally:
            if complete:
                await _settle(self._record_download(export))

    async def _record_download(self, export: ResponseExportDocument) -> None:
        """A complete download: when and how often, nothing else. The file stays."""
        now = self._clock()

        def done(document: ResponseExportDocument):
            if document.status != ExportStatus.READY:
                return None
            document.downloaded_at = now
            document.download_count += 1
            return document

        try:
            await self._exports.update_locked(export.id, done)
        except Exception as error:  # noqa: BLE001 - the file was sent; this is bookkeeping
            logger.warning(
                "could not record download of export {} ({})", export.id, type(error).__name__
            )

    async def discard(self, workspace_id: RecordId, form_id: str, export_id: str, user: User) -> None:
        """Delete a ready file now (its requester only), so a new export can be
        started without waiting for the 24 hours. The audit entry stays. A file
        that is already gone is already discarded; an export still being built
        is not a file (409)."""
        export = await self._mine(workspace_id, form_id, export_id, user)
        if export.status == ExportStatus.READY:
            await self._drop_file(export.id, ExportStatus.DISCARDED)
            return
        if export.status.unfinished:
            raise _error(
                HTTPStatus.CONFLICT,
                "export_not_ready",
                "This export is still being prepared; there is no file to delete yet.",
            )

    # ---------------------------------------------------------------------- sweeps
    async def purge_expired(self) -> int:
        """Delete the files that outlived ``FILE_TTL``."""
        now = self._clock()
        purged = 0
        for export in await self._exports.list_by_status([ExportStatus.READY]):
            if export.expires_at is not None and export.expires_at <= now:
                if await self._drop_file(export.id, ExportStatus.EXPIRED) is not None:
                    purged += 1
        return purged

    async def redefer_pending(self) -> Dict[str, int]:
        """Queue again exports whose job was never queued; rescue those whose
        worker died mid-build (their partial chunks are dropped); fail those
        that ran out of attempts; close streams that were cut off."""
        now = self._clock()
        queued = rescued = failed = 0
        for export in await self._exports.list_by_status([ExportStatus.STREAMING]):
            if export.created_at and export.created_at < now - limits.STALE_STREAMING_AFTER:
                # a streamed export whose process died: it was cut off
                await self._exports.update_locked(export.id, self._interrupted)
        for export in await self._exports.list_by_status([ExportStatus.QUEUED]):
            if export.created_at and export.created_at < now - limits.REDEFER_AFTER:
                queued += 1 if await self._queue(export) else 0
        cutoff = now - limits.STALE_RUNNING_AFTER
        for export in await self._exports.list_by_status([ExportStatus.RUNNING]):
            if export.started_at is None or export.started_at >= cutoff:
                continue

            def lose(document: ResponseExportDocument, cutoff=cutoff):
                # still the same silent claim: a run that stores chunks writes
                # its heartbeat with each, so this one is not alive
                if (
                    document.status != ExportStatus.RUNNING
                    or document.started_at is None
                    or document.started_at >= cutoff
                ):
                    return None
                if document.attempts >= limits.MAX_ATTEMPTS:
                    document.status = ExportStatus.FAILED
                    document.error_code = "worker_lost"
                    document.finished_at = self._clock()
                    document.params_sealed = None
                else:
                    document.status = ExportStatus.QUEUED
                return document

            updated = await self._exports.update_locked(export.id, lose)
            if updated is None:
                continue
            # after the state change: the old run can no longer store a chunk
            await self._exports.delete_chunks(export.id)
            if updated.status == ExportStatus.QUEUED:
                rescued += 1 if await self._queue(updated) else 0
            else:
                failed += 1
        return {"queued": queued, "rescued": rescued, "failed": failed}

    def _interrupted(self, document: ResponseExportDocument):
        if document.status != ExportStatus.STREAMING:
            return None
        document.status = ExportStatus.CANCELLED
        document.error_code = "interrupted"
        document.finished_at = self._clock()
        return document

    # ------------------------------------------------------------ deletion hooks
    async def forget_files_of_form(self, workspace_id: RecordId, form_id: str) -> int:
        return await self._exports.forget_files_of_form(workspace_id, form_id)

    async def forget_actor(self, user_id: str) -> int:
        """The account of ``user_id`` was deleted: its export audit rows stay,
        without the user (``DELETED_ACTOR``); a file it had waiting is deleted."""
        return await self._exports.forget_actor(user_id)

    async def delete_for_form(self, workspace_id: RecordId, form_id: str) -> None:
        await self._exports.delete_for_form(workspace_id, form_id)

    async def delete_for_forms(self, form_ids: List[str]) -> None:
        await self._exports.delete_by_form_ids(form_ids)

    async def delete_for_workspaces(self, workspace_ids: List[str]) -> None:
        await self._exports.delete_by_workspace_ids(workspace_ids)


async def _defer_job(export_id: str) -> None:
    """Queue ``build_response_export``: the id is the only argument."""
    from procrastinate.exceptions import AlreadyEnqueued

    from backend.jobs import tasks

    try:
        await tasks.build_response_export.configure(
            queueing_lock=f"build_response_export:{export_id}"
        ).defer_async(export_id=export_id)
    except AlreadyEnqueued:
        pass
