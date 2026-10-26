"""Postgres runtime pieces every service wires the same way.

Engine and session providers that are ``None`` without ``DATABASE_URL``, a
lazy proxy for repositories that depend on each other, and the startup
reachability check. The backend grew these first (backend/db); auth and the
google integration use them from here.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Mapping, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from common.db.engine import DatabaseSettings, make_engine, make_sessionmaker, ping
from common.db.flags import DbFlags
from common.db.schema_guard import AuxiliarySchema, MigrationTarget, ensure_schema_ready

logger = logging.getLogger(__name__)


def build_engine(
    settings: DatabaseSettings, application_name: str
) -> Optional[AsyncEngine]:
    if not settings.configured:
        return None
    return make_engine(settings, application_name=application_name)


def build_sessionmaker(
    engine: Optional[AsyncEngine],
) -> Optional[async_sessionmaker[AsyncSession]]:
    return None if engine is None else make_sessionmaker(engine)


class LazyRepository:
    """Resolve a routed repository at first use, not at construction — for
    twins that compose over each other's routed repository (a provider cycle).
    Attribute access is forwarded to the resolved repository."""

    def __init__(self, resolve: Callable[[], Any]):
        self._resolve = resolve
        self._target = None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):  # copying/pickling probes must not resolve
            raise AttributeError(name)
        if self._target is None:
            self._target = self._resolve()
        return getattr(self._target, name)


async def check_postgres_at_startup(
    flags: DbFlags,
    engine: Optional[AsyncEngine],
    target: Optional[MigrationTarget] = None,
    auxiliary: Sequence[AuxiliarySchema] = (),
    *,
    env: Mapping[str, str] = os.environ,
) -> None:
    """Postgres is the only store: it must be configured and reachable. Once
    reachable, the service's schema (``target``, plus ``auxiliary`` ones) is
    migrated when ``DB_AUTO_MIGRATE`` is on and must then be at the code's
    head: a reachable database with the wrong schema refuses to start
    (:mod:`common.db.schema_guard`)."""
    if engine is None:
        raise RuntimeError("Postgres is the only store but DATABASE_URL is not set")
    try:
        await ping(engine)
        logger.info("Postgres reachable (application database)")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Postgres is unreachable") from exc
    if target is not None or auxiliary:
        await ensure_schema_ready(flags, engine, target, auxiliary, env=env)


async def dispose_engine(engine: Optional[AsyncEngine]) -> None:
    if engine is not None:
        await engine.dispose()
