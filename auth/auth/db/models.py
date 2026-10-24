from __future__ import annotations

from sqlalchemy import Index, UniqueConstraint

from auth.db.base import S, Base
from common.db import BaseRow, DeletionTombstoneMixin, MirrorWriteFailureMixin
from common.db.migrate import MigrationProgressMixin, StoreMigrationMixin


class UserRow(Base, BaseRow):
    __tablename__ = "users"
    email = S.text("email")
    stripe_customer_id = S.text("stripe_customer_id")
    stripe_payment_id = S.text("stripe_payment_id")
    otp_code_for = S.text("otp_code_for")
    plan = S.text("plan")
    __table_args__ = (
        UniqueConstraint("email"),
        Index(None, "stripe_customer_id"),
        Index(None, "stripe_payment_id"),
    )


class ProviderRow(Base, BaseRow):
    __tablename__ = "providers"
    __mongo_collection__ = "Provider"  # no Settings.name on the Beanie document
    provider_name = S.text("provider_name")
    __table_args__ = (Index(None, "provider_name"),)


class MirrorWriteFailure(Base, MirrorWriteFailureMixin):
    __tablename__ = "mirror_write_failures"


class MigrationProgress(Base, MigrationProgressMixin):
    """Checkpoints of the Mongo → Postgres backfill (python -m <service>.migrate)."""

    __tablename__ = "migration_progress"


class StoreMigration(Base, StoreMigrationMixin):
    """The "migration verified" marker and per-group verify records
    (common.db.marker); written only by a clean ``verify``."""

    __tablename__ = "store_migration"


class DeletionTombstone(Base, DeletionTombstoneMixin):
    """Ids deleted from this schema's tables, kept so that reconcile never
    copies a deleted record back (common.db.tombstones). Ids only."""

    __tablename__ = "deletion_tombstones"
