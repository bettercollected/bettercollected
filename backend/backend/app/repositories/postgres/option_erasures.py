"""The queue of erased answers that were offered as options
(``services/option_sources/erasure.py``). Written by the response repository
inside the erasure transaction; read and emptied by the redaction run."""

from typing import List

from backend.app.schemas.option_source_erasure import OptionSourceErasureDocument
from backend.db.models import OptionSourceErasureRow
from common.records.repository import RecordRepository

Row = OptionSourceErasureRow


class PostgresOptionErasureRepository(RecordRepository):
    row = Row
    document = OptionSourceErasureDocument

    async def pending(self, limit: int) -> List[OptionSourceErasureDocument]:
        """The oldest notes first."""
        return await self.many(order_by=(Row.created_at, Row.id), limit=limit)

    async def pending_count(self) -> int:
        return await self.count()

    async def remove(self, ids: List[str]) -> int:
        if not ids:
            return 0
        return await self.delete_where(Row.id.in_([str(i) for i in ids]))
