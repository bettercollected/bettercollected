"""The stores an operator command uses: the container's routed repositories,
booted the way the services boot them, so a command reads from the store the
services read (``DB_READ_SOURCE`` / ``DB_READ_SOURCE__<group>``) and writes the
stores they write (``DB_WRITE_MODE`` / ``DB_WRITE_MODE__<group>``), before,
during and after the move to Postgres.

Mongo (and Beanie) is opened only while one of the command's groups still reads
or writes it, so a command keeps working once Mongo is gone; the Postgres
engine is the container's own (``DATABASE_URL``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Iterable

from common.db.flags import DbFlags, ReadSource


def needs_mongo(flags: DbFlags, groups: Iterable[str]) -> bool:
    """Whether any of ``groups`` still reads from or writes to Mongo."""
    return any(
        flags.read_source(group) is ReadSource.MONGO or flags.writes_mongo(group)
        for group in groups
    )


@asynccontextmanager
async def routed_repositories(*groups: str):
    """Yields the container, ready for the routed repositories of ``groups``;
    closes what it opened on exit."""
    from dependency_injector import providers
    from pymongo import AsyncMongoClient

    from backend.app.container import container
    from backend.app.handlers.database import close_db, init_db
    from backend.config import settings
    from backend.db.startup import dispose_postgres

    flags = container.flags()
    client = None
    if needs_mongo(flags, groups):
        client = AsyncMongoClient(settings.mongo_settings.URI)
        container.database_client.override(providers.Object(client))
        await init_db(settings.mongo_settings.DB, client)
    try:
        yield container
    finally:
        if client is not None:
            await close_db(client)
        await dispose_postgres(container)
