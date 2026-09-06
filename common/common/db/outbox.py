"""Outboxes for mirror writes that failed (plans/postgres-consolidation.md §6).

In dual-write mode the mirror write is bounded and never fails the request; a
failure is recorded in the *primary* store so the reconciler can replay it:

* Mongo primary → :class:`MirrorWriteFailureDocument` (collection
  ``mirror_write_failures``) — services register it with Beanie.
* Postgres primary → a per-schema table declared from
  :class:`MirrorWriteFailureMixin` (``<schema>.mirror_write_failures``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from common.configs.mongo_document import MongoDocument

MIRROR_OPS = ("insert", "update", "delete")


class MirrorWriteFailureMixin:
    """Columns of the Postgres-side outbox. Concrete class per service:

    class MirrorWriteFailure(Base, MirrorWriteFailureMixin):
        __tablename__ = "mirror_write_failures"
    """

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    row_id: Mapped[str] = mapped_column(Text, nullable=False)
    op: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))


class MirrorWriteFailureDocument(MongoDocument):
    """The Mongo-side outbox, for the phase in which Mongo is primary."""

    table_name: str
    row_id: str
    op: str
    error: str
    attempts: int = 0
    resolved_at: Optional[datetime] = None

    class Settings:
        name = "mirror_write_failures"
