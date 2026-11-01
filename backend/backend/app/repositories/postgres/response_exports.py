"""Repositories of the responses export (Postgres only, new in 4.2): the export
rows (audit entries and job state) and the encrypted chunks of a job's file.
Queries use the spine columns of :mod:`backend.db.models`. Nothing here holds or
reads an answer."""

import datetime as dt
import hashlib
from typing import Callable, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.response_export import (
    DELETED_ACTOR,
    ExportStatus,
    ResponseExportChunkDocument,
    ResponseExportDocument,
)
from backend.db.models import ResponseExportChunkRow, ResponseExportRow
from common.clock import utcnow
from common.records.codec import decode, row_values
from common.records.repository import RecordRepository


def _id(value) -> str:
    return str(value)


class OpenExportExists(Exception):
    """The requester already has an export of this form in flight or waiting to be fetched."""


class WorkspaceBusy(Exception):
    """The workspace already has its share of jobs in flight."""


class StreamsBusy(Exception):
    """The requester (``scope == "user"``) or the workspace (``"workspace"``)
    already has its share of streamed exports in flight."""

    def __init__(self, scope: str):
        super().__init__(scope)
        self.scope = scope


def _workspace_lock_key(workspace_id) -> int:
    """The advisory lock that serialises admissions (jobs and streams) of one workspace."""
    digest = hashlib.sha1(("response-export|" + _id(workspace_id)).encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


CHUNK_OWNED, CHUNK_LOST, CHUNK_INVALIDATED = "owned", "lost", "invalidated"


class PostgresResponseExportRepository(RecordRepository):
    """The export rows. ``chunks`` (the file's pieces) is its own table, read
    through the second repository, but a deletion of a form's responses must
    clear both, so the erasure methods live here and take the chunk table."""

    row = ResponseExportRow
    document = ResponseExportDocument

    async def get(self, workspace_id, form_id, export_id) -> Optional[ResponseExportDocument]:
        """Only an export of this form of this workspace."""
        return await self.one(
            ResponseExportRow.id == _id(export_id),
            ResponseExportRow.workspace_id == _id(workspace_id),
            ResponseExportRow.form_id == _id(form_id),
        )

    async def get_by_id(self, export_id) -> Optional[ResponseExportDocument]:
        return await self.one(ResponseExportRow.id == _id(export_id))

    async def save(self, document: ResponseExportDocument) -> ResponseExportDocument:
        return await self.save_document(document)

    async def list_for_actor(
        self, workspace_id, form_id, actor_id, limit: int = 10
    ) -> List[ResponseExportDocument]:
        """The requester's own exports of the form, newest first."""
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(self.row.doc)
                        .where(
                            ResponseExportRow.workspace_id == _id(workspace_id),
                            ResponseExportRow.form_id == _id(form_id),
                            ResponseExportRow.actor_id == _id(actor_id),
                        )
                        .order_by(ResponseExportRow.created_at.desc(), ResponseExportRow.id.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [decode(self.document, d) for d in docs]

    async def list_for_form(self, workspace_id, form_id, limit: int = 50) -> List[ResponseExportDocument]:
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(self.row.doc)
                        .where(
                            ResponseExportRow.workspace_id == _id(workspace_id),
                            ResponseExportRow.form_id == _id(form_id),
                        )
                        .order_by(ResponseExportRow.created_at.desc(), ResponseExportRow.id.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [decode(self.document, d) for d in docs]

    async def open_for(self, workspace_id, form_id, actor_id) -> Optional[ResponseExportDocument]:
        """A job of this requester for this form that is in flight or whose
        file waits to be fetched (one live export per requester and form)."""
        return await self.one(
            ResponseExportRow.workspace_id == _id(workspace_id),
            ResponseExportRow.form_id == _id(form_id),
            ResponseExportRow.actor_id == _id(actor_id),
            ResponseExportRow.status.in_(
                [s.value for s in (ExportStatus.QUEUED, ExportStatus.RUNNING, ExportStatus.READY)]
            ),
        )

    async def admit_job(self, document: ResponseExportDocument, workspace_cap: int) -> ResponseExportDocument:
        """Store a new job unless the workspace already has ``workspace_cap``
        in flight (``WorkspaceBusy``) or the requester already has a live export
        of the form (``OpenExportExists``). The count and the insert share one
        transaction under a lock on the workspace, and the partial unique index
        of revision 0027 backs the second rule, so concurrent requests cannot
        both get in."""
        key = _workspace_lock_key(document.workspace_id)
        document.ensure_id()
        values = row_values(document)
        try:
            async with self._session() as session, session.begin():
                await session.execute(select(func.pg_advisory_xact_lock(key)))
                in_flight = (
                    await session.execute(
                        select(func.count())
                        .select_from(ResponseExportRow)
                        .where(
                            ResponseExportRow.workspace_id == _id(document.workspace_id),
                            ResponseExportRow.status.in_(
                                [ExportStatus.QUEUED.value, ExportStatus.RUNNING.value]
                            ),
                        )
                    )
                ).scalar_one()
                if in_flight >= workspace_cap:
                    raise WorkspaceBusy()
                await session.execute(self._upsert_statement(values))
        except IntegrityError:
            raise OpenExportExists() from None
        return document

    async def admit_stream(
        self,
        document: ResponseExportDocument,
        per_user: int,
        per_workspace: int,
        since: dt.datetime,
    ) -> ResponseExportDocument:
        """Store the audit row of a streamed export (or bulk read) unless the
        requester already has ``per_user`` streams in flight in the workspace or
        the workspace has ``per_workspace`` (``StreamsBusy``). A stream is in
        flight while its row is ``streaming`` and was last written (a heartbeat
        of the stream, or its creation) at or after ``since``. The counts and the insert share one transaction under the
        workspace's advisory lock (the one ``admit_job`` takes), so parallel
        requests, on this process or on another replica, cannot all get in."""
        key = _workspace_lock_key(document.workspace_id)
        document.ensure_id()
        values = row_values(document)
        streaming = ResponseExportRow.status == ExportStatus.STREAMING.value
        live = [
            ResponseExportRow.workspace_id == _id(document.workspace_id),
            streaming,
            ResponseExportRow.updated_at >= since,
        ]
        async with self._session() as session, session.begin():
            await session.execute(select(func.pg_advisory_xact_lock(key)))
            in_workspace = (
                await session.execute(
                    select(func.count()).select_from(ResponseExportRow).where(*live)
                )
            ).scalar_one()
            if in_workspace >= per_workspace:
                raise StreamsBusy("workspace")
            by_user = (
                await session.execute(
                    select(func.count())
                    .select_from(ResponseExportRow)
                    .where(*live, ResponseExportRow.actor_id == _id(document.actor_id))
                )
            ).scalar_one()
            if by_user >= per_user:
                raise StreamsBusy("user")
            await session.execute(self._upsert_statement(values))
        return document

    async def count_unfinished_in_workspace(self, workspace_id) -> int:
        return await self.count(
            ResponseExportRow.workspace_id == _id(workspace_id),
            ResponseExportRow.status.in_([ExportStatus.QUEUED.value, ExportStatus.RUNNING.value]),
        )

    async def list_by_status(
        self, statuses: Sequence[ExportStatus], limit: int = 500
    ) -> List[ResponseExportDocument]:
        return await self.many(
            ResponseExportRow.status.in_([s.value for s in statuses]),
            order_by=(ResponseExportRow.created_at, ResponseExportRow.id),
            limit=limit,
        )

    async def update_locked(
        self,
        export_id,
        change: Callable[[ResponseExportDocument], Optional[ResponseExportDocument]],
    ) -> Optional[ResponseExportDocument]:
        """Apply ``change`` to the export row, locked until it is saved: the
        stored copy, never one read earlier. ``change`` returns the document to
        store, or None to leave the row alone. Returns what was stored (None
        when the row is gone or ``change`` declined)."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(ResponseExportRow.doc)
                    .where(ResponseExportRow.id == _id(export_id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            document = decode(self.document, doc)
            updated = change(document)
            if updated is None:
                return None
            updated.touch()
            await session.execute(self._upsert_statement(row_values(updated)))
            return updated

    # -- erasure and deletion ---------------------------------------------------
    async def delete_chunks(self, export_id) -> int:
        return await self.delete_where(
            ResponseExportChunkRow.export_id == _id(export_id), row=ResponseExportChunkRow
        )

    async def forget_files_of_form(self, workspace_id, form_id) -> int:
        """Responses of the form were deleted: every stored export file of it
        goes now, a job that is building is told to throw its file away (one not
        started reads the rows that are left). The
        audit rows stay. Returns how many files were deleted."""
        return await self._forget(
            ResponseExportRow.workspace_id == _id(workspace_id),
            ResponseExportRow.form_id == _id(form_id),
        )

    async def forget_files_of_forms(self, form_ids: Sequence) -> int:
        """The same for forms of any workspace (their responses were deleted
        by form)."""
        if not form_ids:
            return 0
        return await self._forget(ResponseExportRow.form_id.in_([_id(f) for f in form_ids]))

    async def _forget(self, *where) -> int:
        now = utcnow()
        rows = await self.many(
            *where,
            ResponseExportRow.status.in_(
                [s.value for s in (ExportStatus.QUEUED, ExportStatus.RUNNING, ExportStatus.READY)]
            ),
        )
        deleted = 0
        for found in rows:

            def change(document: ResponseExportDocument, now=now):
                if document.status == ExportStatus.READY:
                    document.status = ExportStatus.ERASED
                    document.file_deleted_at = now
                    document.expires_at = None
                elif document.status == ExportStatus.RUNNING:
                    # it may have read the rows already; one still queued has
                    # read nothing and will not meet what was just deleted
                    document.invalidated_at = now
                else:
                    return None
                return document

            updated = await self.update_locked(found.id, change)
            if updated is not None and updated.status == ExportStatus.ERASED:
                await self.delete_chunks(found.id)
                deleted += 1
        return deleted

    async def forget_actor(self, user_id) -> int:
        """The account was deleted: its exports keep their audit row, with the
        user replaced by ``DELETED_ACTOR``; a file it had waiting is deleted, a job
        of it that is still running is told to stop. Returns the rows changed."""
        changed = 0
        for found in await self.many(ResponseExportRow.actor_id == _id(user_id)):

            def change(document: ResponseExportDocument):
                if document.actor_id != _id(user_id):
                    return None
                if document.status == ExportStatus.READY:
                    document.status = ExportStatus.ERASED
                    document.file_deleted_at = utcnow()
                    document.expires_at = None
                elif document.status == ExportStatus.RUNNING:
                    document.invalidated_at = utcnow()
                document.actor_id = DELETED_ACTOR
                return document

            # decided from the stored row under its lock, not from the copy read
            # above: a job may have made it READY since
            updated = await self.update_locked(found.id, change)
            if updated is not None:
                changed += 1
                if updated.status == ExportStatus.ERASED:
                    await self.delete_chunks(found.id)
        return changed

    async def delete_for_form(self, workspace_id, form_id) -> int:
        # the rows first: with the row gone ``add_chunk_if_owned`` (which locks
        # it) refuses a running job's next chunk, and the delete below takes the rest
        deleted = await self.delete_where(
            ResponseExportRow.workspace_id == _id(workspace_id),
            ResponseExportRow.form_id == _id(form_id),
        )
        await self.delete_where(
            ResponseExportChunkRow.workspace_id == _id(workspace_id),
            ResponseExportChunkRow.form_id == _id(form_id),
            row=ResponseExportChunkRow,
        )
        return deleted

    async def delete_by_form_ids(self, form_ids: Sequence) -> int:
        if not form_ids:
            return 0
        ids = [_id(f) for f in form_ids]
        deleted = await self.delete_where(ResponseExportRow.form_id.in_(ids))
        await self.delete_where(ResponseExportChunkRow.form_id.in_(ids), row=ResponseExportChunkRow)
        return deleted

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        if not workspace_ids:
            return 0
        ids = [_id(w) for w in workspace_ids]
        deleted = await self.delete_where(ResponseExportRow.workspace_id.in_(ids))
        await self.delete_where(
            ResponseExportChunkRow.workspace_id.in_(ids), row=ResponseExportChunkRow
        )
        return deleted

    # -- chunks ---------------------------------------------------------------
    async def add_chunk(self, chunk: ResponseExportChunkDocument) -> None:
        await self.upsert(chunk, row=ResponseExportChunkRow)

    async def add_chunk_if_owned(
        self, chunk: ResponseExportChunkDocument, attempt: int, now: dt.datetime
    ) -> str:
        """Store a chunk only while the run that wrote it still owns the export:
        the row is locked, still RUNNING, still on this claim (``attempt``) and not
        invalidated; the same transaction records the heartbeat (``heartbeat_at``).
        Returns ``CHUNK_OWNED``, ``CHUNK_LOST`` (another claim took over) or
        ``CHUNK_INVALIDATED`` (responses were deleted)."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(ResponseExportRow.doc)
                    .where(ResponseExportRow.id == chunk.export_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return CHUNK_LOST
            document = decode(self.document, doc)
            if document.status != ExportStatus.RUNNING or document.attempts != attempt:
                return CHUNK_LOST
            if document.invalidated_at is not None:
                return CHUNK_INVALIDATED
            document.heartbeat_at = now
            document.touch()
            await session.execute(self._upsert_statement(row_values(document)))
            await session.execute(self._upsert_statement(row_values(chunk), ResponseExportChunkRow))
            return CHUNK_OWNED

    async def beat_if_owned(self, export_id, attempt: int, now: dt.datetime) -> str:
        """Record a heartbeat of the run that holds claim ``attempt``, with no
        chunk (a job reading rows that have not yet filled one). Same answers as
        ``add_chunk_if_owned``."""

        def change(document: ResponseExportDocument):
            if document.status != ExportStatus.RUNNING or document.attempts != attempt:
                return None
            if document.invalidated_at is not None:
                return None
            document.heartbeat_at = now
            return document

        updated = await self.update_locked(export_id, change)
        if updated is not None:
            return CHUNK_OWNED
        found = await self.get_by_id(export_id)
        if (
            found is not None
            and found.status == ExportStatus.RUNNING
            and found.attempts == attempt
            and found.invalidated_at is not None
        ):
            return CHUNK_INVALIDATED
        return CHUNK_LOST

    async def get_chunk(self, export_id, index: int) -> Optional[ResponseExportChunkDocument]:
        return await self.one_of(
            ResponseExportChunkRow,
            ResponseExportChunkDocument,
            ResponseExportChunkRow.export_id == _id(export_id),
            ResponseExportChunkRow.chunk_index == index,
        )

    async def count_chunks(self, export_id) -> int:
        return await self.count_of(ResponseExportChunkRow, ResponseExportChunkRow.export_id == _id(export_id))

    async def count_of(self, row, *where) -> int:
        async with self._session() as session:
            return (
                await session.execute(select(func.count()).select_from(row).where(*where))
            ).scalar_one()
