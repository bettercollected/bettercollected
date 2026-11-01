"""The repository of workspace security events (Postgres only, new in 4.3)."""

import datetime as dt
from typing import List, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.workspace_audit_event import WorkspaceAuditEventDocument
from backend.db.models import WorkspaceAuditEventRow
from common.records.codec import decode
from common.records.repository import RecordRepository


def _id(value) -> str:
    return str(value)


class PostgresWorkspaceAuditRepository(RecordRepository):
    row = WorkspaceAuditEventRow
    document = WorkspaceAuditEventDocument

    async def record(self, document: WorkspaceAuditEventDocument) -> bool:
        """Store the entry; False when this session already has one for this
        workspace and event (the unique index decides, so it holds across
        processes and restarts)."""
        try:
            await self.upsert(document)
        except IntegrityError:
            return False
        return True

    async def recent(
        self, workspace_id, limit: int = 20
    ) -> List[WorkspaceAuditEventDocument]:
        async with self._session() as session:
            docs = (
                (
                    await session.execute(
                        select(self.row.doc)
                        .where(WorkspaceAuditEventRow.workspace_id == _id(workspace_id))
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
