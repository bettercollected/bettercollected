"""The repository of workspace security events (Postgres only, new in 4.3)."""

import datetime as dt
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import func, or_, select, tuple_

from backend.app.schemas.workspace_audit_event import WorkspaceAuditEventDocument
from backend.db.models import WorkspaceAuditEventRow
from common.records.codec import decode, row_values
from common.records.repository import RecordRepository


# how many entries one delete of the daily purge removes (one transaction each)
PURGE_BATCH = 2000


def _id(value) -> str:
    return str(value)


class PostgresWorkspaceAuditRepository(RecordRepository):
    row = WorkspaceAuditEventRow
    document = WorkspaceAuditEventDocument

    async def record(self, document: WorkspaceAuditEventDocument) -> None:
        """One plain INSERT: no read first, no uniqueness to check."""
        await self.upsert(document)

    async def record_many(
        self, documents: Sequence[WorkspaceAuditEventDocument]
    ) -> None:
        """Plain INSERTs of all the entries in one transaction: all are stored or
        none."""
        await self.upsert_many(documents)

    async def record_many_in(
        self, session, documents: Sequence[WorkspaceAuditEventDocument]
    ) -> None:
        """The same plain INSERTs in the caller's transaction, so the entries and
        the change they describe are stored together or not at all."""
        for document in documents:
            self._check_collection(document, self.row)
            await session.execute(self._upsert_statement(row_values(document)))

    @staticmethod
    def page_statement(
        workspace_id,
        limit: int,
        before: Optional[Tuple[dt.datetime, str]] = None,
        events: Optional[Sequence[str]] = None,
        *,
        form_id: Optional[str] = None,
        actor: Optional[str] = None,
        target: Optional[str] = None,
        involving: Optional[str] = None,
        since: Optional[dt.datetime] = None,
        until: Optional[dt.datetime] = None,
    ):
        """The query of ``page`` (a function of its arguments only, so a test
        can ask the database how it runs it)."""
        row = WorkspaceAuditEventRow
        where = [row.workspace_id == _id(workspace_id)]
        if events is not None:
            where.append(row.event.in_(list(events)))
        if form_id is not None:
            where.append(row.form_id == str(form_id))
        if actor is not None:
            where.append(row.user_id == str(actor))
        if target is not None:
            where.append(row.target_user_id == str(target))
        if involving is not None:
            where.append(
                or_(
                    row.user_id == str(involving),
                    row.target_user_id == str(involving),
                )
            )
        if since is not None:
            where.append(row.created_at >= since)
        if until is not None:
            where.append(row.created_at <= until)
        if before is not None:
            where.append(
                tuple_(row.created_at, row.id) < tuple_(before[0], before[1])
            )
        return (
            select(row.doc)
            .where(*where)
            .order_by(row.created_at.desc(), row.id.desc())
            .limit(limit)
        )

    async def page(
        self,
        workspace_id,
        limit: int,
        before: Optional[Tuple[dt.datetime, str]] = None,
        events: Optional[Sequence[str]] = None,
        *,
        form_id: Optional[str] = None,
        actor: Optional[str] = None,
        target: Optional[str] = None,
        involving: Optional[str] = None,
        since: Optional[dt.datetime] = None,
        until: Optional[dt.datetime] = None,
    ) -> List[WorkspaceAuditEventDocument]:
        """Newest first (keyset: ``before`` is the (time, id) of the last
        entry of the previous page); at most ``limit`` entries. ``events``:
        only those kinds of entry (a page lists its own, not every kind the
        log holds). The filters of the audit log page, all of this workspace's
        rows only: ``form_id``; ``actor`` (who did it), ``target`` (who it was
        done to) and ``involving`` (either of the two); ``since`` and
        ``until`` (inclusive times). Each is an indexed column (revision
        0038)."""
        statement = self.page_statement(
            workspace_id,
            limit,
            before,
            events,
            form_id=form_id,
            actor=actor,
            target=target,
            involving=involving,
            since=since,
            until=until,
        )
        async with self._session() as session:
            docs = (await session.execute(statement)).scalars().all()
        return [decode(self.document, d) for d in docs]

    async def count_up_to(
        self,
        workspace_id,
        cap: int,
        events: Optional[Sequence[str]] = None,
        *,
        form_id: Optional[str] = None,
        actor: Optional[str] = None,
        target: Optional[str] = None,
        involving: Optional[str] = None,
        since: Optional[dt.datetime] = None,
        until: Optional[dt.datetime] = None,
    ) -> int:
        """How many entries the same filters as ``page`` match, counted only up
        to ``cap`` (a bounded scan: the answer is ``cap`` when there are at
        least that many)."""
        limited = self.page_statement(
            workspace_id,
            cap,
            None,
            events,
            form_id=form_id,
            actor=actor,
            target=target,
            involving=involving,
            since=since,
            until=until,
        )
        counted = select(func.count()).select_from(
            limited.with_only_columns(WorkspaceAuditEventRow.id).order_by(None).subquery()
        )
        async with self._session() as session:
            return int((await session.execute(counted)).scalar_one())

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        if not workspace_ids:
            return 0
        return await self.delete_where(
            WorkspaceAuditEventRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )

    async def _delete_in_batches(self, batch: int, *where) -> int:
        """Delete the rows that match ``where`` ``batch`` at a time, oldest
        first, each batch in a transaction of its own: a purge that has months
        of entries to delete (a workspace that shortened its retention) never
        holds one long transaction or writes every tombstone at once."""
        row = WorkspaceAuditEventRow
        batch = max(1, int(batch))
        total = 0
        while True:
            oldest = (
                select(row.id)
                .where(*where)
                .order_by(row.created_at, row.id)
                .limit(batch)
            )
            deleted = await self.delete_where(row.id.in_(oldest))
            total += deleted
            if deleted < batch:
                return total

    async def purge_before(
        self,
        cutoff: dt.datetime,
        except_workspaces: Sequence = (),
        batch: int = PURGE_BATCH,
    ) -> int:
        """Delete every entry older than ``cutoff``, except those of
        ``except_workspaces`` (which have a retention of their own), in batches."""
        where = [WorkspaceAuditEventRow.created_at < cutoff]
        if except_workspaces:
            where.append(
                WorkspaceAuditEventRow.workspace_id.not_in(
                    [_id(w) for w in except_workspaces]
                )
            )
        return await self._delete_in_batches(batch, *where)

    async def purge_workspace_before(
        self, workspace_id, cutoff: dt.datetime, batch: int = PURGE_BATCH
    ) -> int:
        """Delete the entries of one workspace older than ``cutoff``, in batches."""
        return await self._delete_in_batches(
            batch,
            WorkspaceAuditEventRow.workspace_id == _id(workspace_id),
            WorkspaceAuditEventRow.created_at < cutoff,
        )
