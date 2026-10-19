"""The "migration verified" marker: proof in Postgres that the data was migrated and verified.

Every service schema has a ``store_migration`` table. The migration CLI's
``verify`` appends to it, and nothing else writes it (backfill and reconcile
never do):

* a ``group`` row for every repository group whose collections were *all*
  verified clean in that run: no missing, mismatched or drifted row and equal
  counts in both stores, checked in full (``--sample-every 1``);
* a ``service`` row, the marker itself, when either

  - one verify run covered every collection of the service and all were
    clean (``verify`` with no ``--group``/``--collections``, or ``--group``
    naming every group), or
  - per-group verifies combine: the latest ``group`` row of every group of
    the service is clean, covers all of that group's current collections,
    is at most :data:`COMBINE_WINDOW` old, and is newer than the last
    backfill checkpoint of its collections. The combined row records the
    group runs it rests on (``based_on``) and, as ``verified_at``, the oldest
    of them.

A verify that finds differences writes nothing and revokes nothing: the
marker states that a clean verify happened, not that the stores still agree.
:func:`migration_verified` reads the latest ``service`` row; it is what a
startup guard checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional

from sqlalchemy import BigInteger, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from common.db.groups import SERVICE_SCHEMAS

MARKER_TABLE = "store_migration"
SCOPE_SERVICE = "service"  # the marker: every collection of the service verified clean
SCOPE_GROUP = "group"  # one repository group verified clean
COMBINE_WINDOW = timedelta(days=7)


class StoreMigrationMixin:
    """Columns of ``<schema>.store_migration``. Concrete class per service::

    class StoreMigration(Base, StoreMigrationMixin):
        __tablename__ = "store_migration"
    """

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    service: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    # the repository groups this row covers (one for a group row)
    groups: Mapped[list] = mapped_column(JSONB, nullable=False)
    # collection -> {"group", "mongo", "postgres"}: counts at verify time
    collections: Mapped[dict] = mapped_column(JSONB, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    code_version: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[str] = mapped_column(Text, nullable=False)
    # a combined marker: the group rows it rests on ({group, run_id, verified_at})
    based_on: Mapped[Optional[list]] = mapped_column(JSONB)

    @declared_attr.directive
    def __table_args__(cls):
        return (Index(None, "scope", "verified_at"),)


@dataclass(frozen=True)
class MarkerInfo:
    service: str
    verified_at: datetime
    run_id: str
    code_version: str
    groups: tuple[str, ...]
    collections: dict = field(default_factory=dict)
    based_on: Optional[list] = None  # None: one full verify run

    @property
    def combined(self) -> bool:
        return self.based_on is not None

    def counts(self) -> dict[str, dict[str, int]]:
        return {
            name: {"mongo": c.get("mongo", 0), "postgres": c.get("postgres", 0)}
            for name, c in self.collections.items()
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "verified_at": self.verified_at.isoformat(),
            "run_id": self.run_id,
            "code_version": self.code_version,
            "groups": list(self.groups),
            "collections": self.collections,
            "combined": self.combined,
            "based_on": self.based_on,
        }


async def marker_table_exists(conn: AsyncConnection, schema: str) -> bool:
    found = await conn.scalar(
        text("SELECT to_regclass(:t)"), {"t": f'"{schema}".{MARKER_TABLE}'}
    )
    return found is not None


async def migration_verified(
    conn: AsyncConnection,
    service: str,
    *,
    schema: Optional[str] = None,
    collections: Optional[Iterable[str]] = None,
) -> Optional[MarkerInfo]:
    """The latest "migration verified" marker of ``service``, or ``None``.

    ``None`` also when the schema has no marker table (not migrated that far)
    or, with ``collections``, when the marker does not cover every one of them
    (a table added after the verify)."""
    schema = schema or SERVICE_SCHEMAS[service]
    if not await marker_table_exists(conn, schema):
        return None
    row = (
        (
            await conn.execute(
                text(
                    f"SELECT service, verified_at, run_id, code_version, groups, collections, based_on "
                    f'FROM "{schema}".{MARKER_TABLE} '
                    "WHERE scope = :scope AND service = :service ORDER BY id DESC LIMIT 1"
                ),
                {"scope": SCOPE_SERVICE, "service": service},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    marker = MarkerInfo(
        service=row["service"],
        verified_at=row["verified_at"],
        run_id=row["run_id"],
        code_version=row["code_version"],
        groups=tuple(row["groups"] or ()),
        collections=dict(row["collections"] or {}),
        based_on=row["based_on"],
    )
    if collections is not None and not set(collections) <= set(marker.collections):
        return None
    return marker
