"""Repositories of the responses export (Postgres only, new in 4.2): the export
rows (audit entries and job state) and the encrypted chunks of a job's file.
Queries use the spine columns of :mod:`backend.db.models`. Nothing here holds or
reads an answer."""

from typing import Callable, List, Optional, Sequence

from sqlalchemy import func, select

from backend.app.schemas.response_export import (
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

    async def unfinished_for(self, workspace_id, form_id, actor_id) -> Optional[ResponseExportDocument]:
        """A job of this requester for this form that has not ended."""
        return await self.one(
            ResponseExportRow.workspace_id == _id(workspace_id),
            ResponseExportRow.form_id == _id(form_id),
            ResponseExportRow.actor_id == _id(actor_id),
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

    async def delete_for_form(self, workspace_id, form_id) -> int:
        await self.delete_where(
            ResponseExportChunkRow.workspace_id == _id(workspace_id),
            ResponseExportChunkRow.form_id == _id(form_id),
            row=ResponseExportChunkRow,
        )
        return await self.delete_where(
            ResponseExportRow.workspace_id == _id(workspace_id),
            ResponseExportRow.form_id == _id(form_id),
        )

    async def delete_by_form_ids(self, form_ids: Sequence) -> int:
        if not form_ids:
            return 0
        ids = [_id(f) for f in form_ids]
        await self.delete_where(ResponseExportChunkRow.form_id.in_(ids), row=ResponseExportChunkRow)
        return await self.delete_where(ResponseExportRow.form_id.in_(ids))

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        if not workspace_ids:
            return 0
        ids = [_id(w) for w in workspace_ids]
        await self.delete_where(
            ResponseExportChunkRow.workspace_id.in_(ids), row=ResponseExportChunkRow
        )
        return await self.delete_where(ResponseExportRow.workspace_id.in_(ids))

    # -- chunks ---------------------------------------------------------------
    async def add_chunk(self, chunk: ResponseExportChunkDocument) -> None:
        await self.upsert(chunk, row=ResponseExportChunkRow)

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
