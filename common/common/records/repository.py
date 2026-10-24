"""The Postgres repository base for :class:`~common.records.base.Record` classes.

:class:`common.db.pg_repository.PostgresRepositoryBase` reads and writes rows
through :mod:`common.db.beanie_bridge`. A group whose documents are records
(see the package docstring, "Adopting it") builds its repositories on
:class:`RecordRepository` instead: the same queries and statements, with every
``doc`` encoded and decoded by :mod:`common.records.codec`, and a save moving
``updated_at`` with :meth:`Record.touch`, as ``MongoDocument.save()`` did.
The stored bytes are the same either way (golden-tested).

While Beanie groups remain, this subclasses the bridge-based base (and so
imports :mod:`common.db`); the package itself does not import it. Once every
group is on records, the base folds into this class.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence, Type

from sqlalchemy import select

from common.db.pg_repository import PostgresRepositoryBase
from common.records.base import Record
from common.records.codec import decode, row_values


class RecordRepository(PostgresRepositoryBase):
    """``row`` (the table's BaseRow model) and ``document`` (a Record class)."""

    async def one_of(
        self,
        row: Type[Any],
        document: Type[Any],
        *where: Any,
        order_by: Optional[Sequence[Any]] = None,
    ):
        async with self._session() as session:
            stmt = (
                select(row.doc)
                .where(*where)
                .order_by(*(order_by or (row.created_at, row.id)))
                .limit(1)
            )
            doc = (await session.execute(stmt)).scalar_one_or_none()
        return None if doc is None else decode(document, doc)

    async def many(
        self,
        *where: Any,
        order_by: Optional[Sequence[Any]] = None,
        limit: Optional[int] = None,
        row: Optional[Type[Any]] = None,
        document: Optional[Type[Any]] = None,
    ) -> List[Any]:
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

    async def upsert(self, document: Any, row: Optional[Type[Any]] = None) -> Any:
        self._check_collection(document, row or self.row)
        values = row_values(document)
        async with self._session() as session, session.begin():
            await session.execute(self._upsert_statement(values, row))
        return document

    async def save_document(
        self, document: Any, row: Optional[Type[Any]] = None
    ) -> Any:
        """Move ``updated_at`` to now, then store (what a save did in Mongo)."""
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
