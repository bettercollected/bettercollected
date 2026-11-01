"""The queue of erased answers that were offered as options
(``services/option_sources/erasure.py``). Written by the response repository
inside the erasure transaction; read and emptied by the redaction run."""

from typing import List, Optional

from backend.app.schemas.option_source_erasure import OptionSourceErasureDocument
from backend.db.models import OptionSourceErasureRow
from common.records.repository import RecordRepository

Row = OptionSourceErasureRow


class PostgresOptionErasureRepository(RecordRepository):
    row = Row
    document = OptionSourceErasureDocument

    async def pending(
        self, limit: int, after: Optional[str] = None
    ) -> List[OptionSourceErasureDocument]:
        """Notes by id; ``after`` (the id of the last note of the previous
        page) continues a listing."""
        where = [Row.id > str(after)] if after is not None else []
        return await self.many(*where, order_by=(Row.id,), limit=limit)

    async def pending_count(self) -> int:
        return await self.count()

    async def remove(self, ids: List[str]) -> int:
        if not ids:
            return 0
        return await self.delete_where(Row.id.in_([str(i) for i in ids]))
