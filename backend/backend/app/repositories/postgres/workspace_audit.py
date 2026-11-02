"""The repository of workspace security events (Postgres only, new in 4.3)."""

import datetime as dt
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import or_, select, tuple_

from backend.app.schemas.workspace_audit_event import WorkspaceAuditEventDocument
from backend.db.models import WorkspaceAuditEventRow
from common.records.codec import decode
from common.records.repository import RecordRepository


def _id(value) -> str:
    return str(value)


class PostgresWorkspaceAuditRepository(RecordRepository):
    row = WorkspaceAuditEventRow
    document = WorkspaceAuditEventDocument

    async def record(self, document: WorkspaceAuditEventDocument) -> None:
        """One plain INSERT: no read first, no uniqueness to check."""
        await self.upsert(document)

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

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        if not workspace_ids:
            return 0
        return await self.delete_where(
            WorkspaceAuditEventRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )

    async def purge_before(self, cutoff: dt.datetime) -> int:
        return await self.delete_where(WorkspaceAuditEventRow.created_at < cutoff)
