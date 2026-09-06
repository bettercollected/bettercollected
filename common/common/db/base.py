"""Declarative base factory and the columns every migrated row carries.

Decisions D1 and D2 (plans/postgres-consolidation.md): primary keys are the
Mongo ObjectId hex strings, and each table is a typed "spine" of queried
columns plus a ``doc`` JSONB body holding the whole document, so a row
round-trips losslessly to the Mongo document it mirrors.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import CheckConstraint, MetaData, Text, event, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from common.db.canonical import checksum

# Alembic autogenerate needs stable constraint names; these give every
# constraint one derived from its table and columns.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

OBJECT_ID_PATTERN = r"^[0-9a-f]{24}$"
ID_CHECK_NAME = "id_is_object_id"

SOURCE_APP = "app"
SOURCE_BACKFILL = "backfill"


def make_base(schema: str) -> type[DeclarativeBase]:
    """A declarative base whose tables live in ``schema`` (one per service)."""

    class Base(DeclarativeBase):
        metadata = MetaData(schema=schema, naming_convention=NAMING_CONVENTION)

    Base.__name__ = f"Base_{schema}"
    Base.__qualname__ = Base.__name__
    return Base


class BaseRow:
    """Mixin: the common columns of every migrated table.

    ``id``            the Mongo ``_id`` as a 24-hex string (CHECK-constrained).
    ``doc``           the full document as BSON Extended JSON (see canonical.py).
    ``_bc_source``    ``app`` for rows the application wrote, ``backfill`` for
                      rows the migration copied — backfill never overwrites
                      ``app`` rows (plans/postgres-consolidation.md §5).
    ``_bc_checksum``  ``document_checksum(doc)``, recomputed automatically on
                      every insert and update, so verification can compare a
                      row with its Mongo document without re-reading ``doc``.

    Timestamps are bumped for ``app`` rows only; backfilled rows keep the
    values copied from Mongo.
    """

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    updated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
    doc: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    bc_source: Mapped[str] = mapped_column(
        "_bc_source", Text, nullable=False, server_default=text(f"'{SOURCE_APP}'")
    )
    bc_checksum: Mapped[str] = mapped_column("_bc_checksum", Text, nullable=False)


@event.listens_for(BaseRow, "instrument_class", propagate=True)
def _add_id_check(mapper, class_) -> None:
    """Every concrete BaseRow table gets the ObjectId CHECK on ``id``.

    Done here rather than via ``__table_args__`` so a model that declares its
    own ``__table_args__`` (a unique constraint, an index) cannot lose it.
    """
    table = class_.__table__
    # The naming convention rewrites the name to ck_<table>_<name>; match on the suffix.
    if any(
        str(getattr(c, "name", "")).endswith(ID_CHECK_NAME) for c in table.constraints
    ):
        return
    table.append_constraint(
        CheckConstraint(f"id ~ '{OBJECT_ID_PATTERN}'", name=ID_CHECK_NAME)
    )


def _stamp(target: BaseRow, *, inserting: bool) -> None:
    now = datetime.now(timezone.utc)
    if target.bc_source is None:
        target.bc_source = SOURCE_APP
    if target.bc_source == SOURCE_APP:
        if inserting and target.created_at is None:
            target.created_at = now
        if inserting and target.updated_at is None:
            target.updated_at = now
        if not inserting:
            target.updated_at = now
    target.bc_checksum = checksum(target.doc)


@event.listens_for(BaseRow, "before_insert", propagate=True)
def _before_insert(mapper, connection, target) -> None:
    _stamp(target, inserting=True)


@event.listens_for(BaseRow, "before_update", propagate=True)
def _before_update(mapper, connection, target) -> None:
    _stamp(target, inserting=False)
