"""Shared Alembic plumbing so each service's ``migrations/env.py`` is a few lines.

    # <service>/migrations/env.py
    from alembic import context
    from common.db.alembic_support import run_migrations
    from <pkg>.app.db.base import SCHEMA, Base
    import <pkg>.app.db.models  # noqa: F401  (registers the tables)

    run_migrations(context, Base.metadata, SCHEMA)

Each service owns exactly one schema: the version table lives in it, and
autogenerate only sees objects in it, so three services can share one database
without stepping on each other's migrations.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from common.db.ddl import drop_helper_function_ddl, helper_function_ddl
from common.db.engine import normalise_url


def _include_object_for(schema: str):
    def include_object(obj, name, type_, reflected, compare_to) -> bool:
        if type_ == "table":
            return obj.schema == schema
        table = getattr(obj, "table", None)
        if table is not None:
            return table.schema == schema
        return True

    return include_object


def context_options(metadata: MetaData, schema: str) -> dict[str, Any]:
    return dict(
        target_metadata=metadata,
        include_schemas=True,
        include_object=_include_object_for(schema),
        version_table_schema=schema,
        compare_type=True,
    )


def resolve_url(config) -> str:
    url = config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "set DATABASE_URL (or sqlalchemy.url in alembic.ini) to run migrations"
        )
    return normalise_url(url)


def create_schema_if_missing_sql(schema: str) -> str:
    """CREATE SCHEMA only when absent. Plain ``CREATE SCHEMA IF NOT EXISTS`` still
    demands CREATE on the *database*, which the per-service roles (bc_app, ...)
    deliberately lack; they own their schema, which the init script created.
    CI and scratch databases run as a superuser and create it here."""
    return (
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = "
        f"'{schema}') THEN EXECUTE 'CREATE SCHEMA \"{schema}\"'; END IF; END $$"
    )


def _run_sync(connection: Connection, context, metadata: MetaData, schema: str) -> None:
    connection.execute(text(create_schema_if_missing_sql(schema)))
    context.configure(connection=connection, **context_options(metadata, schema))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(context, metadata: MetaData, schema: str) -> None:
    """Entry point for ``env.py``: offline SQL emission or online async execution."""
    url = resolve_url(context.config)
    if context.is_offline_mode():
        context.configure(
            url=url,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            **context_options(metadata, schema),
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    async def _online() -> None:
        engine = create_async_engine(url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                await connection.run_sync(_run_sync, context, metadata, schema)
                await connection.commit()
        finally:
            await engine.dispose()

    asyncio.run(_online())


# -- helpers for revision files ---------------------------------------------
def ensure_schema(op, schema: str) -> None:
    op.execute(create_schema_if_missing_sql(schema))


def create_helper_functions(op, schema: str) -> None:
    for statement in helper_function_ddl(schema):
        op.execute(statement)


def drop_helper_functions(op, schema: str) -> None:
    for statement in drop_helper_function_ddl(schema):
        op.execute(statement)


# -- for tests: "do the migrations produce exactly the models?" ---------------
def metadata_diff(connection: Connection, metadata: MetaData, schema: str) -> list:
    """Empty list when the live schema matches ``metadata``; else Alembic's diff ops."""
    opts = context_options(metadata, schema)
    opts.pop("target_metadata")
    migration_context = MigrationContext.configure(connection, opts=opts)
    return compare_metadata(migration_context, metadata)
