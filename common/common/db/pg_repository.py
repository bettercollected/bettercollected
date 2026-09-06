"""Base for the Postgres twin of a repository.

Subclasses set ``row`` (the BaseRow model) and ``document`` (the Beanie class)
and express their queries against the row's spine columns; everything crosses
the boundary as documents, through :mod:`common.db.beanie_bridge`.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Type

from sqlalchemy import delete, func, select
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from common.db.beanie_bridge import from_row_doc, row_values


class PostgresNotConfigured(RuntimeError):
    pass


class PostgresRepositoryBase:
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
        # Mongo's natural order is insertion order; created_at then id reproduces it.
        return (self.row.created_at, self.row.id)

    async def one(self, *where: Any) -> Optional[Any]:
        return await self.one_of(self.row, self.document, *where)

    async def one_of(self, row: Type[Any], document: Type[Any], *where: Any):
        """``one`` against another table of the same group — for the places the
        Mongo original reads a second collection inside one method."""
        async with self._session() as session:
            stmt = (
                select(row.doc).where(*where).order_by(row.created_at, row.id).limit(1)
            )
            doc = (await session.execute(stmt)).scalar_one_or_none()
        return None if doc is None else from_row_doc(document, doc)

    async def get_or_raise(self, document_id: Any) -> Any:
        """The twin of ``Document.get``: the document, or the document layer's
        ``NotFoundError`` with the same message."""
        found = await self.one(self.row.id == str(document_id))
        return self.document.verify_doc_exists(found, {"id": document_id})

    async def many(
        self,
        *where: Any,
        order_by: Optional[Sequence[Any]] = None,
        limit: Optional[int] = None,
    ) -> List[Any]:
        async with self._session() as session:
            stmt = (
                select(self.row.doc)
                .where(*where)
                .order_by(*(order_by or self._order()))
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            docs = (await session.execute(stmt)).scalars().all()
        return [from_row_doc(self.document, d) for d in docs]

    async def count(self, *where: Any) -> int:
        async with self._session() as session:
            return (
                await session.execute(
                    select(func.count()).select_from(self.row).where(*where)
                )
            ).scalar_one()

    # -- writes ----------------------------------------------------------------
    def _column_names(self) -> dict[str, str]:
        """attribute -> column name (``bc_source`` is stored as ``_bc_source``)."""
        mapper = sa_inspect(self.row).mapper
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

    def _upsert_statement(self, values: dict[str, Any]):
        names = self._column_names()
        stmt = pg_insert(self.row).values({names[k]: v for k, v in values.items()})
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

    async def upsert(self, document: Any) -> Any:
        values = row_values(document)
        async with self._session() as session, session.begin():
            await session.execute(self._upsert_statement(values))
        return document

    async def upsert_many(self, documents: Iterable[Any]) -> None:
        async with self._session() as session, session.begin():
            for document in documents:
                await session.execute(self._upsert_statement(row_values(document)))

    async def replay_write(self, documents: Iterable[Any]) -> None:
        """Store what the primary persisted (``@write_op(replay=True)``)."""
        documents = list(documents)
        for document in documents:
            if not isinstance(document, self.document):
                raise TypeError(
                    f"{type(self).__name__} cannot store a "
                    f"{type(document).__name__}; expected {self.document.__name__}"
                )
        await self.upsert_many(documents)

    async def delete_where(self, *where: Any) -> int:
        async with self._session() as session, session.begin():
            result = await session.execute(delete(self.row).where(*where))
        return result.rowcount or 0

    async def delete_one_where(self, *where: Any) -> int:
        """Delete the first matching row in Mongo's natural order — the twin of
        ``find_one(...).delete()``. Mongo's semantics, even where odd, are what
        verification compares against."""
        async with self._session() as session, session.begin():
            target = (
                select(self.row.id)
                .where(*where)
                .order_by(*self._order())
                .limit(1)
                .scalar_subquery()
            )
            result = await session.execute(
                delete(self.row).where(self.row.id == target)
            )
        return result.rowcount or 0

    async def delete_by_id(self, document_id: Any) -> int:
        return await self.delete_where(self.row.id == str(document_id))
