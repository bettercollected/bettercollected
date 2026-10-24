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

from common.db.flags import DbFlags


def needs_mongo(flags: DbFlags, groups: Iterable[str]) -> bool:
    """Whether any of ``groups`` still reads from, writes to or shadow-reads Mongo
    (:meth:`common.db.flags.DbFlags.uses_mongo`, the services' own decision)."""
    groups = tuple(groups)
    return bool(groups) and flags.uses_mongo(groups)


@asynccontextmanager
async def routed_repositories(*groups: str):
    """Yields the container, ready for the routed repositories of ``groups``;
    closes what it opened on exit."""
    from backend.app.container import container
    from backend.app.handlers.database import close_db, open_mongo
    from backend.config import settings
    from backend.db.startup import dispose_postgres

    # Beanie is set up either way (documents are built from Postgres rows
    # too), on a client of this command's own; it connects only while one of
    # the groups uses Mongo.
    container.database_client.reset_override()
    client = await open_mongo(
        container,
        settings.mongo_settings.URI,
        settings.mongo_settings.DB,
        required=needs_mongo(container.flags(), groups),
    )
    try:
        yield container
    finally:
        await close_db(client)
        container.database_client.reset_override()
        await dispose_postgres(container)
