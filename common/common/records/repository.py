"""The Postgres repository base for :class:`~common.records.base.Record` classes.

Subclasses set ``row`` (the table's BaseRow model) and ``document`` (a Record
class) and express their queries against the row's spine columns; everything
crosses the boundary as records, through :mod:`common.records.codec`. A save
moves ``updated_at`` with :meth:`Record.touch`, and every delete records a
tombstone in the same transaction (:mod:`common.db.tombstones`), which the
import from 4.0 reads.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, List, Optional, Sequence, Type

from sqlalchemy import delete, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common.db.tombstones import prune_due, prune_postgres, record_postgres
from common.records.base import Record
from common.records.codec import decode, row_values

logger = logging.getLogger(__name__)


class PostgresNotConfigured(RuntimeError):
    pass


class RecordRepository:
    """``row`` (the table's BaseRow model) and ``document`` (a Record class)."""

    row: Type[Any]
    document: Type[Any]

    def __init__(self, session_factory: Optional[async_sessionmaker[AsyncSession]]):
        self._sessions = session_factory

    # -- sessions --------------------------------------------------------------
    def _session(self) -> AsyncSession:
        if self._sessions is None:
            raise PostgresNotConfigured(
                "DATABASE_URL is not set; the Postgres store is unavailable"
            )
        return self._sessions()

    # -- reads -----------------------------------------------------------------
    def _order(self) -> Sequence[Any]:
        # created_at then id reproduces insertion order.
        return (self.row.created_at, self.row.id)

    async def one(
        self, *where: Any, order_by: Optional[Sequence[Any]] = None
    ) -> Optional[Any]:
        return await self.one_of(self.row, self.document, *where, order_by=order_by)

    async def one_of(
        self,
        row: Type[Any],
        document: Type[Any],
        *where: Any,
        order_by: Optional[Sequence[Any]] = None,
    ):
        """``one`` against another table of the same group."""
        async with self._session() as session:
            stmt = (
                select(row.doc)
                .where(*where)
                .order_by(*(order_by or (row.created_at, row.id)))
                .limit(1)
            )
            doc = (await session.execute(stmt)).scalar_one_or_none()
        return None if doc is None else decode(document, doc)

    async def get_or_raise(self, document_id: Any) -> Any:
        """The record, or the record layer's ``NotFoundError``."""
        found = await self.one(self.row.id == str(document_id))
        return self.document.verify_doc_exists(found, {"id": document_id})

    async def many(
        self,
        *where: Any,
        order_by: Optional[Sequence[Any]] = None,
        limit: Optional[int] = None,
        row: Optional[Type[Any]] = None,
        document: Optional[Type[Any]] = None,
    ) -> List[Any]:
        """``row``/``document`` select another table of the group, for
        repositories spanning two collections."""
        row, document = row or self.row, document or self.document
        async with self._session() as session:
            stmt = (
                select(row.doc)
                .where(*where)
                .order_by(*(order_by or (row.created_at, row.id)))
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            docs = (await session.execute(stmt)).scalars().all()
        return [decode(document, d) for d in docs]

    async def count(self, *where: Any) -> int:
        async with self._session() as session:
            return (
                await session.execute(
                    select(func.count()).select_from(self.row).where(*where)
                )
            ).scalar_one()

    # -- writes ----------------------------------------------------------------
    def _column_names(self, row: Optional[Type[Any]] = None) -> dict[str, str]:
        """attribute -> column name (``bc_source`` is stored as ``_bc_source``)."""
        mapper = sa_inspect(row or self.row).mapper
        return {
            attr: mapper.attrs[attr].columns[0].name
            for attr in (
                "id",
                "doc",
                "created_at",
                "updated_at",
                "bc_source",
                "bc_checksum",
            )
        }

    @staticmethod
    def _check_collection(document: Any, row: Type[Any]) -> None:
        """A record belongs to one collection: refuse to store it in another
        repository's table loudly."""
        get_settings = getattr(type(document), "get_settings", None)
        collection = get_settings().name if get_settings else None
        if collection is not None and collection != row.mongo_collection():
            raise TypeError(
                f"a {type(document).__name__} (collection {collection!r}) cannot be "
                f"stored in table {row.__tablename__!r}"
            )

    def _upsert_statement(
        self, values: dict[str, Any], row: Optional[Type[Any]] = None
    ):
        row = row or self.row
        names = self._column_names(row)
        stmt = pg_insert(row).values({names[k]: v for k, v in values.items()})
        excluded = stmt.excluded
        return stmt.on_conflict_do_update(
            index_elements=[names["id"]],
            set_={
                names["doc"]: excluded[names["doc"]],
                names["updated_at"]: excluded[names["updated_at"]],
                names["bc_source"]: excluded[names["bc_source"]],
                names["bc_checksum"]: excluded[names["bc_checksum"]],
            },
        )

    async def upsert(self, document: Any, row: Optional[Type[Any]] = None) -> Any:
        """Store ``document`` (minting an id if it has none); ``row`` selects
        another table of the group."""
        self._check_collection(document, row or self.row)
        values = row_values(document)
        async with self._session() as session, session.begin():
            await session.execute(self._upsert_statement(values, row))
        return document

    async def save_document(
        self, document: Any, row: Optional[Type[Any]] = None
    ) -> Any:
        """Move ``updated_at`` to now, then store (what a save does); the
        methods that insert or update fields leave ``updated_at`` as it is and
        use :meth:`upsert`."""
        if isinstance(document, Record):
            document.touch()
        return await self.upsert(document, row)

    async def upsert_many(
        self, documents: Iterable[Any], row: Optional[Type[Any]] = None
    ) -> None:
        async with self._session() as session, session.begin():
            for document in documents:
                self._check_collection(document, row or self.row)
                await session.execute(
                    self._upsert_statement(row_values(document), row)
                )

    async def _delete_recorded(self, session, row: Type[Any], *where: Any) -> int:
        """Delete and, in the same transaction, record a tombstone per
        deleted id (:mod:`common.db.tombstones`)."""
        ids = (
            (await session.execute(delete(row).where(*where).returning(row.id)))
            .scalars()
            .all()
        )
        await record_postgres(
            session, row.__table__.schema, row.mongo_collection(), ids
        )
        return len(ids)

    async def _prune_tombstones_if_due(self, row: Type[Any]) -> None:
        """Every so many recorded deletes, drop a bounded batch of expired
        tombstones: after the delete committed, in a transaction of its own,
        and never failing the delete."""
        schema = row.__table__.schema
        if not prune_due(schema):
            return
        try:
            async with self._session() as session, session.begin():
                await prune_postgres(session, schema)
        except Exception as exc:  # noqa: BLE001 — pruning is housekeeping
            logger.warning(
                "pruning tombstones failed: schema=%s error=%s",
                schema,
                type(exc).__name__,
            )

    async def delete_where(self, *where: Any, row: Optional[Type[Any]] = None) -> int:
        row = row or self.row
        async with self._session() as session, session.begin():
            deleted = await self._delete_recorded(session, row, *where)
        await self._prune_tombstones_if_due(row)
        return deleted

    async def delete_one_where(
        self, *where: Any, row: Optional[Type[Any]] = None
    ) -> int:
        """Delete the first matching row in insertion order (``created_at``,
        then ``id``)."""
        row = row or self.row
        async with self._session() as session, session.begin():
            target = (
                select(row.id)
                .where(*where)
                .order_by(row.created_at, row.id)
                .limit(1)
                .scalar_subquery()
            )
            deleted = await self._delete_recorded(session, row, row.id == target)
        await self._prune_tombstones_if_due(row)
        return deleted

    async def delete_by_id(self, document_id: Any) -> int:
        return await self.delete_where(self.row.id == str(document_id))
