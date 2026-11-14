"""The analytics group's repositories: Postgres only (its Mongo collections
are read only by the import from 4.0)."""

import datetime as dt
import hashlib
import time
from typing import Callable, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import delete, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.schemas.captcha_count import CaptchaDailyCountDocument
from backend.app.schemas.flow_event import FlowEventDocument
from backend.app.schemas.rate_limit_counter import RateLimitCounterDocument
from backend.db.models import (
    CaptchaDailyCountRow,
    FormFlowEventRow,
    RateLimitCounterRow,
)
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

    # Expired counters (there is no TTL index in Postgres) are swept in bounded
    # batches of SWEEP_BATCH rows, at most SWEEP_MAX_BATCHES of them, at most
    # once per SWEEP_EVERY_SECONDS in a process, after a new counter was
    # committed, skipping rows another replica's sweep or request holds locked.
    # The request that crosses the interval awaits it (a few short deletes, not
    # one per counter as before). A counter is never needed after its
    # expires_at, so nothing waits for the sweep and a failed sweep only logs.
    SWEEP_EVERY_SECONDS = 60
    SWEEP_BATCH = 500
    SWEEP_MAX_BATCHES = 10

    def __init__(self, session_factory, sweep_clock: Callable[[], float] = time.monotonic):
        super().__init__(session_factory)
        self._sweep_clock = sweep_clock
        self._next_sweep = 0.0
        self._sweeping = False

    async def hit(
        self, counter_id: str, expires_at: dt.datetime, amount: int = 1
    ) -> int:
        """Add ``amount`` (one request by default) to the counter
        ``counter_id`` (24 hex characters), creating it to expire at
        ``expires_at``; returns the count including this request. The row
        lock makes it atomic, so requests reaching several replicas at once
        are all counted."""
        return (await self._apply(counter_id, expires_at, amount, None))[1]

    async def admit(
        self, counter_id: str, expires_at: dt.datetime, limit: int
    ) -> Tuple[bool, int]:
        """Add one request only if the count is still below ``limit``, in the
        same locked step that reads it: ``(admitted, count)``. Parallel
        requests, on any replica, are admitted exactly ``limit`` times; a
        refused one changes nothing."""
        return await self._apply(counter_id, expires_at, 1, limit)

    async def release(self, counter_id: str) -> None:
        """Give one admitted request back (never below zero): for a request
        that was admitted by one budget and refused by another."""
        locked = (
            select(RateLimitCounterRow.doc)
            .where(RateLimitCounterRow.id == counter_id)
            .with_for_update()
        )
        async with self._session() as session, session.begin():
            doc = (await session.execute(locked)).scalar_one_or_none()
            if doc is None:
                return
            counter = decode(RateLimitCounterDocument, doc)
            counter.hits = max(0, counter.hits - 1)
            counter.updated_at = utcnow()
            await session.execute(self._upsert_statement(row_values(counter)))

    async def _apply(
        self,
        counter_id: str,
        expires_at: dt.datetime,
        amount: int,
        limit: Optional[int],
    ) -> Tuple[bool, int]:
        """``(admitted, count)``: ``amount`` is added to the locked counter,
        unless ``limit`` is set and the count is already at it."""
        now = utcnow()
        if limit is not None and limit <= 0:
            return False, 0
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
                if limit is not None and counter.hits >= limit:
                    return False, counter.hits
                counter.hits += amount
                counter.updated_at = now
                await session.execute(self._upsert_statement(row_values(counter)))
                return True, counter.hits
        if created:
            await self._sweep_if_due()
        return True, amount

    async def _sweep_if_due(self) -> None:
        """Housekeeping after a counter was created, never failing the request."""
        now = self._sweep_clock()
        if self._sweeping or now < self._next_sweep:
            return
        self._sweeping = True
        self._next_sweep = now + self.SWEEP_EVERY_SECONDS
        try:
            await self.purge_expired()
        except Exception as exc:  # noqa: BLE001 — a sweep must not fail a request
            logger.warning("rate-limit counter sweep failed: {}", type(exc).__name__)
        finally:
            self._sweeping = False

    async def purge_expired(self, now: Optional[dt.datetime] = None) -> int:
        """Delete expired counters in bounded batches that skip locked rows;
        returns how many went. No tombstones: a counter is ephemeral, and one
        that came back from an import would be expired too."""
        now = now or utcnow()
        total = 0
        for _ in range(self.SWEEP_MAX_BATCHES):
            batch = (
                select(RateLimitCounterRow.id)
                .where(RateLimitCounterRow.expires_at <= now)
                .limit(self.SWEEP_BATCH)
                .with_for_update(skip_locked=True)
            )
            async with self._session() as session, session.begin():
                result = await session.execute(
                    delete(RateLimitCounterRow).where(
                        RateLimitCounterRow.id.in_(batch.scalar_subquery())
                    )
                )
            deleted = result.rowcount or 0
            total += deleted
            if deleted < self.SWEEP_BATCH:
                break
        return total

CountKey = Tuple[str, str, str, str, str]  # day, workspace, form, purpose, outcome


def captcha_count_id(key: CountKey) -> str:
    """The id of the row that counts ``key``: 24 hex characters of a hash of its
    five fields (they name no person, so the hash needs no secret)."""
    return hashlib.sha256("\n".join(key).encode("utf-8")).hexdigest()[:24]


class PostgresCaptchaCountRepository(RecordRepository):
    """The daily counts of the automatic spam check (``services/captcha/stats.py``):
    counts only, one row per day, workspace, form, purpose and outcome."""

    row = CaptchaDailyCountRow
    document = CaptchaDailyCountDocument

    async def add_counts(self, counts: Dict[CountKey, int]) -> None:
        """Add every amount to its row, creating rows that are not there, in one
        transaction. Rows are locked in id order so that two replicas flushing
        at the same time cannot deadlock."""
        if not counts:
            return
        names = self._column_names()
        by_id = {captcha_count_id(key): (key, n) for key, n in counts.items() if n > 0}
        async with self._session() as session, session.begin():
            for row_id in sorted(by_id):
                key, amount = by_id[row_id]
                locked = (
                    select(CaptchaDailyCountRow.doc)
                    .where(CaptchaDailyCountRow.id == row_id)
                    .with_for_update()
                )
                doc = (await session.execute(locked)).scalar_one_or_none()
                if doc is None:
                    first = CaptchaDailyCountDocument(
                        id=RecordId(row_id),
                        day=key[0],
                        workspace_id=key[1],
                        form_id=key[2],
                        purpose=key[3],
                        outcome=key[4],
                        count=amount,
                    )
                    inserted = await session.execute(
                        pg_insert(CaptchaDailyCountRow)
                        .values({names[k]: v for k, v in row_values(first).items()})
                        .on_conflict_do_nothing(index_elements=[names["id"]])
                        .returning(CaptchaDailyCountRow.id)
                    )
                    if inserted.scalar_one_or_none() is not None:
                        continue
                    # another replica created it first: add to that one
                    doc = (await session.execute(locked)).scalar_one()
                counted = decode(CaptchaDailyCountDocument, doc)
                counted.count += amount
                counted.updated_at = utcnow()
                await session.execute(self._upsert_statement(row_values(counted)))

    async def totals(
        self,
        *,
        since_day: str,
        workspace_id: Optional[str] = None,
        form_id: Optional[str] = None,
    ) -> Dict[Tuple[str, str], int]:
        """``{(purpose, outcome): count}`` from ``since_day`` (``YYYY-MM-DD``,
        inclusive) on, for one workspace or one form."""
        where = [CaptchaDailyCountRow.day >= since_day]
        if workspace_id is not None:
            where.append(CaptchaDailyCountRow.workspace_id == workspace_id)
        if form_id is not None:
            where.append(CaptchaDailyCountRow.form_id == form_id)
        # literal columns: the same expression in the select and the group by
        purpose = literal_column("captcha_daily_counts.doc ->> 'purpose'")
        outcome = literal_column("captcha_daily_counts.doc ->> 'outcome'")
        counted = func.sum(
            literal_column("(captcha_daily_counts.doc ->> 'count')::bigint")
        )
        stmt = (
            select(purpose, outcome, counted)
            .where(*where)
            .group_by(purpose, outcome)
        )
        async with self._session() as session:
            rows = (await session.execute(stmt)).all()
        return {(purpose, outcome): int(n or 0) for purpose, outcome, n in rows}

    async def delete_before(self, day: str) -> int:
        """Counts of days before ``day`` (``YYYY-MM-DD``): the retention sweep."""
        return await self.delete_where(CaptchaDailyCountRow.day < day)
