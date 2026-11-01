"""The queue of erased answers that were offered as options
(``services/option_sources/erasure.py``). Written by the response repository
inside the erasure transaction; read and emptied by the redaction run."""

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import tuple_

from backend.app.schemas.option_source_erasure import OptionSourceErasureDocument
from backend.db.models import OptionSourceErasureRow
from common.records.repository import RecordRepository

Row = OptionSourceErasureRow


class PostgresOptionErasureRepository(RecordRepository):
    row = Row
    document = OptionSourceErasureDocument

    async def pending(
        self, limit: int, after: Optional[Tuple[datetime, str]] = None
    ) -> List[OptionSourceErasureDocument]:
        """The oldest notes first; ``after`` (``(created_at, id)`` of the last
        note of the previous page) continues a listing."""
        where = []
        if after is not None:
            where.append(tuple_(Row.created_at, Row.id) > tuple_(after[0], after[1]))
        return await self.many(*where, order_by=(Row.created_at, Row.id), limit=limit)

    async def pending_count(self) -> int:
        return await self.count()

    async def remove(self, ids: List[str]) -> int:
        if not ids:
            return 0
        return await self.delete_where(Row.id.in_([str(i) for i in ids]))
