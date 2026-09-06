"""Postgres engine/session providers for the backend container.

Everything here is a no-op when ``DATABASE_URL`` is unset: the engine provider
yields ``None``, Postgres repositories are not registered, and the routing
layer treats the store as absent (plans/postgres-consolidation.md §6).
"""

from __future__ import annotations

from typing import Any, Optional, Type

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from common.db import DatabaseSettings, make_engine, make_sessionmaker

APPLICATION_NAME = "bettercollected-backend"


def build_engine(settings: DatabaseSettings) -> Optional[AsyncEngine]:
    if not settings.configured:
        return None
    return make_engine(settings, application_name=APPLICATION_NAME)


def build_sessionmaker(
    engine: Optional[AsyncEngine],
) -> Optional[async_sessionmaker[AsyncSession]]:
    return None if engine is None else make_sessionmaker(engine)


def postgres_repository(
    cls: Type[Any],
    session_factory: Optional[async_sessionmaker[AsyncSession]],
    *args: Any,
    **kwargs: Any,
) -> Optional[Any]:
    """The Postgres twin of a repository, or ``None`` when Postgres is not configured."""
    return None if session_factory is None else cls(session_factory, *args, **kwargs)
