"""The repository of workspace security events (Postgres only, new in 4.3)."""

import datetime as dt
from typing import List, Optional, Sequence, Tuple

from sqlalchemy import select, tuple_

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

    async def page(
        self,
        workspace_id,
        limit: int,
        before: Optional[Tuple[dt.datetime, str]] = None,
    ) -> List[WorkspaceAuditEventDocument]:
        """Newest first (keyset: ``before`` is the (time, id) of the last
        entry of the previous page); at most ``limit`` entries."""
        where = [WorkspaceAuditEventRow.workspace_id == _id(workspace_id)]
        if before is not None:
            where.append(
                tuple_(WorkspaceAuditEventRow.created_at, WorkspaceAuditEventRow.id)
                < tuple_(before[0], before[1])
            )
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(self.row.doc)
                        .where(*where)
                        .order_by(
                            WorkspaceAuditEventRow.created_at.desc(),
                            WorkspaceAuditEventRow.id.desc(),
                        )
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [decode(self.document, d) for d in docs]

    async def delete_by_workspace_ids(self, workspace_ids: Sequence) -> int:
        if not workspace_ids:
            return 0
        return await self.delete_where(
            WorkspaceAuditEventRow.workspace_id.in_([_id(w) for w in workspace_ids])
        )

    async def purge_before(self, cutoff: dt.datetime) -> int:
        return await self.delete_where(WorkspaceAuditEventRow.created_at < cutoff)
