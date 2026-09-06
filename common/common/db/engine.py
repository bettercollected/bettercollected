"""Async engine and session factories with the timeouts every session must carry."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

ASYNC_SCHEME = "postgresql+asyncpg://"


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from exc


def _bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def normalise_url(url: str) -> str:
    """Accept ``postgresql://`` and ``postgres://`` URLs and pin them to the asyncpg driver."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return ASYNC_SCHEME + url[len(prefix) :]
    if not url.startswith(ASYNC_SCHEME):
        raise ValueError(
            f"DATABASE_URL must start with {ASYNC_SCHEME} (or postgresql://), got {url.split('://')[0]!r}://…"
        )
    return url


@dataclass(frozen=True)
class DatabaseSettings:
    """Connection settings, read from the environment by :meth:`from_env`.

    The three timeouts are applied server-side on every connection, so no
    session — request path, worker, or migration — can hold a statement, a
    lock, or an idle transaction indefinitely. ``mirror_timeout_ms`` bounds the
    best-effort mirror write in dual-write mode (plans/postgres-consolidation.md §6).
    """

    url: Optional[str]
    pool_size: int = 5
    max_overflow: int = 5
    pool_timeout_s: int = 10
    statement_timeout_ms: int = 30_000
    lock_timeout_ms: int = 5_000
    idle_in_transaction_ms: int = 60_000
    mirror_timeout_ms: int = 2_000
    echo: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "DatabaseSettings":
        raw_url = env.get("DATABASE_URL") or None
        return cls(
            url=normalise_url(raw_url) if raw_url else None,
            pool_size=_int(env, "DB_POOL_SIZE", 5),
            max_overflow=_int(env, "DB_MAX_OVERFLOW", 5),
            pool_timeout_s=_int(env, "DB_POOL_TIMEOUT_S", 10),
            statement_timeout_ms=_int(env, "DB_STATEMENT_TIMEOUT_MS", 30_000),
            lock_timeout_ms=_int(env, "DB_LOCK_TIMEOUT_MS", 5_000),
            idle_in_transaction_ms=_int(env, "DB_IDLE_IN_TRANSACTION_MS", 60_000),
            mirror_timeout_ms=_int(env, "DB_MIRROR_TIMEOUT_MS", 2_000),
            echo=_bool(env, "DB_ECHO", False),
        )

    @property
    def configured(self) -> bool:
        return bool(self.url)


def make_engine(settings: DatabaseSettings, *, application_name: str) -> AsyncEngine:
    """One engine per process. ``application_name`` shows up in ``pg_stat_activity``."""
    if not settings.url:
        raise ValueError("DATABASE_URL is not set")
    return create_async_engine(
        settings.url,
        echo=settings.echo,
        pool_pre_ping=True,
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout_s,
        connect_args={
            "server_settings": {
                "application_name": application_name,
                "statement_timeout": str(settings.statement_timeout_ms),
                "lock_timeout": str(settings.lock_timeout_ms),
                "idle_in_transaction_session_timeout": str(
                    settings.idle_in_transaction_ms
                ),
            }
        },
    )


def make_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def ping(engine: AsyncEngine) -> bool:
    """Readiness check: a round trip, not just a pool checkout."""
    async with engine.connect() as conn:
        return (await conn.execute(text("SELECT 1"))).scalar_one() == 1
