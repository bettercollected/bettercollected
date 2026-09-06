"""Postgres runtime pieces every service wires the same way.

Engine and session providers that are ``None`` without ``DATABASE_URL``, the
twin-or-None factory, a lazy proxy for routed repositories that depend on
each other, the startup reachability check, and the outbox recorder that
files a mirror-write failure in the *primary* store. The backend grew these
first (backend/db); auth and the google integration use them from here.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Type

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from common.db.engine import DatabaseSettings, make_engine, make_sessionmaker, ping
from common.db.flags import DbFlags, ReadSource
from common.db.outbox import MirrorWriteFailureDocument
from common.db.routing import MirrorFailure

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


def postgres_repository(
    cls: Type[Any],
    session_factory: Optional[async_sessionmaker[AsyncSession]],
    *args: Any,
    **kwargs: Any,
) -> Optional[Any]:
    """The Postgres twin of a repository, or ``None`` when Postgres is not configured."""
    return None if session_factory is None else cls(session_factory, *args, **kwargs)


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
    flags: DbFlags, engine: Optional[AsyncEngine]
) -> None:
    """Reachability is checked only when the flags involve Postgres at all, and
    is fatal only when a group *serves* from it: a mirror failing must never
    take the application down."""
    if not flags.requires_postgres():
        return
    if engine is None:
        raise RuntimeError(
            "DB_*/JOBS_* flags require Postgres but DATABASE_URL is not set"
        )
    try:
        await ping(engine)
        logger.info("Postgres reachable (application database)")
    except Exception as exc:  # noqa: BLE001
        if flags.serves_from_postgres():
            raise RuntimeError(
                "Postgres is unreachable and a repository group serves from it"
            ) from exc
        logger.error(
            "Postgres unreachable at startup; it is only a mirror, continuing: %s",
            type(exc).__name__,
        )


async def dispose_engine(engine: Optional[AsyncEngine]) -> None:
    if engine is not None:
        await engine.dispose()


MAX_IDS = 20


def failure_ids(failure: MirrorFailure) -> str:
    """Best-effort: the ids a failed mirror write touched, from its arguments
    and the documents a replay tried to store."""
    found: list[str] = []
    values = (
        list(failure.args) + list(failure.documents) + list(failure.kwargs.values())
    )
    for value in values:
        if getattr(value, "id", None) is not None and hasattr(value, "save"):
            found.append(str(value.id))
        elif type(value).__name__ in ("ObjectId", "PydanticObjectId"):
            found.append(str(value))
        elif isinstance(value, str) and len(value) <= 64:
            found.append(value)
        elif isinstance(value, (list, tuple)):
            for item in list(value)[:MAX_IDS]:
                if getattr(item, "id", None) is not None and hasattr(item, "save"):
                    found.append(str(item.id))
                elif isinstance(item, str) and len(item) <= 64:
                    found.append(item)
    return ",".join(found[:MAX_IDS]) or "-"


def failure_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


class OutboxRecorder:
    """Record a mirror-write failure in the primary store: a
    ``MirrorWriteFailureDocument`` while Mongo is primary, a row of the
    service's mirror_write_failures table once Postgres is. The reconciler
    (migration CLI) drains both."""

    def __init__(
        self,
        session_factory: Optional[async_sessionmaker[AsyncSession]],
        row_cls: Type[Any],
    ):
        self._sessions = session_factory
        self._row = row_cls

    async def __call__(self, failure: MirrorFailure) -> None:
        row_id = failure_ids(failure)
        if failure.store is ReadSource.POSTGRES:
            await MirrorWriteFailureDocument(
                table_name=failure.repository,
                row_id=row_id,
                op=failure.method,
                error=failure_error(failure.error),
            ).insert()
            return
        if self._sessions is None:
            logger.error(
                "mirror to Mongo failed and Postgres is not configured to record it: %s %s",
                failure.repository,
                failure.method,
            )
            return
        async with self._sessions() as session, session.begin():
            session.add(
                self._row(
                    table_name=failure.repository,
                    row_id=row_id,
                    op=failure.method,
                    error=failure_error(failure.error),
                )
            )
