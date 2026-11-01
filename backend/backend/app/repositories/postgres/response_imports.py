"""Repositories of the CSV import of responses (Postgres only, new in 4.3): the
import rows (audit entries and job state) and the encrypted uploads. Queries
use the spine columns of :mod:`backend.db.models`. Nothing here reads an
answer; the upload is ciphertext."""

import datetime as dt
import hashlib
from typing import Callable, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.response_import import (
    BUSY_STATUSES,
    DELETED_ACTOR,
    ImportStatus,
    ResponseImportDocument,
    ResponseImportFileDocument,
)
from backend.db.models import ResponseImportFileRow, ResponseImportRow
from common.clock import utcnow
from common.records.codec import decode, row_values
from common.records.repository import RecordRepository


def _id(value) -> str:
    return str(value)


class ImportBusy(Exception):
    """This form already has an import being checked, queued or run."""


class WorkspaceBusy(Exception):
    """The workspace already has its share of imports in flight."""


def _workspace_lock_key(workspace_id) -> int:
    digest = hashlib.sha1(("response-import|" + _id(workspace_id)).encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


class PostgresResponseImportRepository(RecordRepository):
    row = ResponseImportRow
    document = ResponseImportDocument

    async def get(self, workspace_id, form_id, import_id) -> Optional[ResponseImportDocument]:
        """Only an import of this form of this workspace."""
        return await self.one(
            ResponseImportRow.id == _id(import_id),
            ResponseImportRow.workspace_id == _id(workspace_id),
            ResponseImportRow.form_id == _id(form_id),
        )

    async def get_by_id(self, import_id) -> Optional[ResponseImportDocument]:
        return await self.one(ResponseImportRow.id == _id(import_id))

    async def save(self, document: ResponseImportDocument) -> ResponseImportDocument:
        return await self.save_document(document)

    async def list_for_form(self, workspace_id, form_id, limit: int = 20) -> List[ResponseImportDocument]:
        """The form's imports, newest first."""
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(self.row.doc)
                        .where(
                            ResponseImportRow.workspace_id == _id(workspace_id),
                            ResponseImportRow.form_id == _id(form_id),
                        )
                        .order_by(ResponseImportRow.created_at.desc(), ResponseImportRow.id.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [decode(self.document, d) for d in docs]

    async def list_by_status(
        self, statuses: Sequence[ImportStatus], limit: int = 500
    ) -> List[ResponseImportDocument]:
        return await self.many(
            ResponseImportRow.status.in_([s.value for s in statuses]),
            order_by=(ResponseImportRow.created_at, ResponseImportRow.id),
            limit=limit,
        )

    async def waiting_files_of_form(self, workspace_id, form_id) -> List[ResponseImportDocument]:
        """The form's imports whose upload is still held and no worker has."""
        return await self.many(
            ResponseImportRow.workspace_id == _id(workspace_id),
            ResponseImportRow.form_id == _id(form_id),
            ResponseImportRow.status.in_([ImportStatus.UPLOADED.value, ImportStatus.CHECKED.value]),
        )

    async def update_locked(
        self,
        import_id,
        change: Callable[[ResponseImportDocument], Optional[ResponseImportDocument]],
        touch: bool = True,
    ) -> Optional[ResponseImportDocument]:
        """Apply ``change`` to the import row, locked until it is saved: the
        stored copy, never one read earlier. ``change`` returns the document to
        store, or None to leave the row alone. Returns what was stored (None
        when the row is gone or ``change`` declined)."""
        async with self._session() as session, session.begin():
            doc = (
                await session.execute(
                    select(ResponseImportRow.doc)
                    .where(ResponseImportRow.id == _id(import_id))
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if doc is None:
                return None
            document = decode(self.document, doc)
            updated = change(document)
            if updated is None:
                return None
            if touch:
                updated.touch()
            await session.execute(self._upsert_statement(row_values(updated)))
            return updated

    async def admit(
        self,
        import_id,
        change: Callable[[ResponseImportDocument], Optional[ResponseImportDocument]],
        workspace_cap: int,
    ) -> Optional[ResponseImportDocument]:
        """``update_locked`` for a change that makes the import busy (checking
        or queued): refused with ``WorkspaceBusy`` when the workspace already
        has ``workspace_cap`` imports in flight and with ``ImportBusy`` when the
        form has one (the partial unique index of revision 0035 backs it, so two
        requests at once cannot both get in). The count and the write share one
        transaction under a lock on the workspace."""
        try:
            async with self._session() as session, session.begin():
                doc = (
                    await session.execute(
                        select(ResponseImportRow.doc)
                        .where(ResponseImportRow.id == _id(import_id))
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if doc is None:
                    return None
                document = decode(self.document, doc)
                await session.execute(
                    select(func.pg_advisory_xact_lock(_workspace_lock_key(document.workspace_id)))
                )
                in_flight = (
                    await session.execute(
                        select(func.count())
                        .select_from(ResponseImportRow)
                        .where(
                            ResponseImportRow.workspace_id == _id(document.workspace_id),
                            ResponseImportRow.status.in_([s.value for s in BUSY_STATUSES]),
                        )
                    )
                ).scalar_one()
                if in_flight >= workspace_cap:
                    raise WorkspaceBusy()
                updated = change(document)
                if updated is None:
                    return None
                updated.touch()
                await session.execute(self._upsert_statement(row_values(updated)))
                return updated
        except IntegrityError:
            raise ImportBusy() from None

    # -- the uploaded file ------------------------------------------------------
    async def save_file(self, file: ResponseImportFileDocument) -> None:
        await self.upsert(file, row=ResponseImportFileRow)

    async def get_file(self, import_id) -> Optional[ResponseImportFileDocument]:
        return await self.one_of(
            ResponseImportFileRow,
            ResponseImportFileDocument,
            ResponseImportFileRow.import_id == _id(import_id),
        )

    async def delete_file(self, import_id) -> int:
        return await self.delete_where(
            ResponseImportFileRow.import_id == _id(import_id), row=ResponseImportFileRow
        )

    async def count_files(self, import_id) -> int:
        async with self._session() as session:
            return (
                await session.execute(
                    select(func.count())
                    .select_from(ResponseImportFileRow)
                    .where(ResponseImportFileRow.import_id == _id(import_id))
                )
            ).scalar_one()

    async def file_ids_older_than(self, cutoff: dt.datetime, limit: int = 500) -> List[str]:
        """Imports whose upload was stored before ``cutoff`` (the sweep's
        safety net: an upload with no row, or one a crashed job left)."""
        async with self._session() as session:
            return list(
                (
                    await session.execute(
                        select(ResponseImportFileRow.import_id)
                        .where(ResponseImportFileRow.created_at < cutoff)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )

    # -- erasure ------------------------------------------------------------------
    async def forget_actor(self, user_id) -> int:
        """The account was deleted: its imports keep their audit row, with the
        user replaced by ``DELETED_ACTOR``; an upload it still had waiting is
        deleted, a job of it that is running is told to stop."""
        changed = 0
        for found in await self.many(ResponseImportRow.actor_id == _id(user_id)):

            def change(document: ResponseImportDocument):
                if document.actor_id != _id(user_id):
                    return None
                if document.status == ImportStatus.RUNNING:
                    document.invalidated_at = utcnow()
                elif document.status in (ImportStatus.UPLOADED, ImportStatus.CHECKED):
                    document.status = ImportStatus.DISCARDED
                    document.headers = []
                document.actor_id = DELETED_ACTOR
                return document

            # ``touch=False``: only the user is replaced, a queued job keeps its age
            updated = await self.update_locked(found.id, change, touch=False)
            if updated is not None:
                changed += 1
                if updated.status == ImportStatus.DISCARDED:
                    await self.delete_file(found.id)
        return changed

    async def delete_for_form(self, workspace_id, form_id) -> int:
        deleted = await self.delete_where(
            ResponseImportRow.workspace_id == _id(workspace_id),
            ResponseImportRow.form_id == _id(form_id),
        )
        await self.delete_where(
            ResponseImportFileRow.workspace_id == _id(workspace_id),
            ResponseImportFileRow.form_id == _id(form_id),
            row=ResponseImportFileRow,
        )
        return deleted

    async def delete_by_form_ids(self, form_ids: Sequence) -> int:
        if not form_ids:
            return 0
        ids = [_id(f) for f in form_ids]
        deleted = await self.delete_where(ResponseImportRow.form_id.in_(ids))
        await self.delete_where(ResponseImportFileRow.form_id.in_(ids), row=ResponseImportFileRow)
        return deleted

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        if not workspace_ids:
            return 0
        ids = [_id(w) for w in workspace_ids]
        deleted = await self.delete_where(ResponseImportRow.workspace_id.in_(ids))
        await self.delete_where(
            ResponseImportFileRow.workspace_id.in_(ids), row=ResponseImportFileRow
        )
        return deleted
