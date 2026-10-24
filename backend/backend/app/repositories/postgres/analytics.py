"""The analytics group's repositories: Postgres only (its Mongo collections
are read only by the import from 4.0)."""

import datetime as dt
from typing import List

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.schemas.flow_event import FlowEventDocument
from backend.app.schemas.rate_limit_counter import RateLimitCounterDocument
from backend.db.models import FormFlowEventRow, RateLimitCounterRow
from common.clock import utcnow
from common.records import RecordId, decode, row_values
from common.records.repository import RecordRepository


class PostgresFlowEventRepository(RecordRepository):
    row = FormFlowEventRow
    document = FlowEventDocument

    async def add(
        self, form_id: str, session_id: str, from_page: str, to_page: str
    ) -> FlowEventDocument:
        return await self.save_document(
            FlowEventDocument(
                form_id=form_id,
                session_id=session_id,
                from_page=from_page,
                to_page=to_page,
            )
        )

    async def list_by_form_id(self, form_id: str) -> List[FlowEventDocument]:
        return await self.many(FormFlowEventRow.form_id == form_id)

    async def delete_older_than(self, cutoff: dt.datetime) -> int:
        """Events recorded before ``cutoff``; uses the created_at index."""
        return await self.delete_where(FormFlowEventRow.created_at < cutoff)


class PostgresRateLimitRepository(RecordRepository):
    row = RateLimitCounterRow
    document = RateLimitCounterDocument

    async def hit(
        self, counter_id: str, expires_at: dt.datetime, amount: int = 1
    ) -> int:
        """Add ``amount`` (one request by default) to the counter
        ``counter_id`` (24 hex characters), creating it to expire at
        ``expires_at``; returns the count including this request. The row
        lock makes it atomic, so requests reaching several replicas at once
        are all counted."""
        now = utcnow()
        names = self._column_names()
        locked = (
            select(RateLimitCounterRow.doc)
            .where(RateLimitCounterRow.id == counter_id)
            .with_for_update()
        )
        async with self._session() as session, session.begin():
            doc = (await session.execute(locked)).scalar_one_or_none()
            if doc is None:
                first = RateLimitCounterDocument(
                    id=RecordId(counter_id),
                    hits=amount,
                    expires_at=expires_at,
                )
                values = row_values(first)
                inserted = await session.execute(
                    pg_insert(RateLimitCounterRow)
                    .values({names[k]: v for k, v in values.items()})
                    .on_conflict_do_nothing(index_elements=[names["id"]])
                    .returning(RateLimitCounterRow.id)
                )
                if inserted.scalar_one_or_none() is not None:
                    created = True
                else:
                    # another request created it first: count on that one
                    doc = (await session.execute(locked)).scalar_one()
                    created = False
            else:
                created = False
            if not created:
                counter = decode(RateLimitCounterDocument, doc)
                counter.hits += amount
                counter.updated_at = now
                await session.execute(self._upsert_statement(row_values(counter)))
                return counter.hits
        # no TTL index here: expired counters go whenever a new one starts
        await self.delete_where(RateLimitCounterRow.expires_at <= now)
        return amount
