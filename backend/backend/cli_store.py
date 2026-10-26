"""The stores an operator command uses: the container's repositories, booted
the way the services boot them.

Postgres is the only store (``DATABASE_URL``): the command gets the same
container, engine included, and the engine is disposed on exit. Nothing here
connects to Mongo.
"""

from __future__ import annotations

from contextlib import asynccontextmanager


@asynccontextmanager
async def open_container():
    """Yields the container, ready for its repositories; disposes the
    Postgres engine on exit."""
    from backend.app.container import container
    from backend.db.startup import dispose_postgres

    try:
        yield container
    finally:
        await dispose_postgres(container)
