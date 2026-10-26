"""Engine and schema guard for the admin service (Postgres only)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

import backend.admin as _package
from backend.admin.config import AdminSettings
from backend.admin.repositories.tables import SCHEMA
from common.db import MigrationTarget, SchemaNotReady, ensure_schema_ready, load_flags

MIGRATIONS = MigrationTarget.for_package(
    _package, SCHEMA, service="backend/backend/admin"
)

# The admin service reads no persistence flags: its only store is Postgres.
_FLAGS = load_flags({})


def make_engine(settings: AdminSettings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=5,
        max_overflow=0,
        pool_pre_ping=True,
        connect_args={"server_settings": {"statement_timeout": "10000"}},
    )


async def ensure_schema(engine: AsyncEngine) -> None:
    """Refuse to start (raise :class:`SchemaNotReady`) unless ``admin`` is at the
    code's Alembic head. Never migrates: the runtime role cannot, and deploy.sh
    runs the migration as the migration role before the service starts."""
    await ensure_schema_ready(_FLAGS, engine, MIGRATIONS, env={})


__all__ = ["MIGRATIONS", "SchemaNotReady", "ensure_schema", "make_engine"]
