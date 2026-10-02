"""Schema readiness at startup: refuse to serve on an unmigrated schema, and
optionally migrate it first.

A service whose persistence flags put a repository group on Postgres needs its
own schema at the Alembic head of the code it runs; otherwise every request
touching a Postgres store fails with ``UndefinedTable``. So at startup:

1. ``DB_AUTO_MIGRATE=true`` (opt-in, default off): ``alembic upgrade head`` for
   the service's own schema, in-process, plus any auxiliary schema the service
   owns (the backend's procrastinate ``jobs`` tables). Each schema is migrated
   under a Postgres advisory lock held on a dedicated connection, so replicas
   starting together serialise: the first migrates, the others wait, then find
   the schema at head and continue.
2. Compare the database's revision with the code's head(s); behind or missing
   refuses to start with a message naming the fix. Ahead (a newer release
   migrated it, then this image came back in a rollback or a reschedule) only
   warns: migrations are expand-only, so the older code still runs on the
   newer schema, and refusing would turn every rollback into an outage.

With every group on Mongo the check is skipped entirely (no database needed).
deploy.sh's explicit migration step keeps working unchanged: it simply leaves
nothing for step 1 to do.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import ModuleType
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Iterable,
    Mapping,
    Optional,
    Protocol,
    Sequence,
)

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from common.db.alembic_support import create_schema_if_missing_sql
from common.db.flags import DbFlags

logger = logging.getLogger(__name__)

AUTO_MIGRATE_KEY = "DB_AUTO_MIGRATE"
LOCK_WAIT_KEY = "DB_AUTO_MIGRATE_LOCK_WAIT_SECONDS"
DEFAULT_LOCK_WAIT_SECONDS = 300.0
# How long the migration's own DDL may wait for a table lock (e.g. behind a
# long query holding it) before failing, so a stuck migration ends instead of
# hanging every replica until its healthcheck kills it.
MIGRATION_LOCK_TIMEOUT = "60s"
_LOCK_NAMESPACE = "bettercollected:schema-migrate:"
_LOCK_POLL_SECONDS = 1.0


def auto_migrate_enabled(env: Mapping[str, str] = os.environ) -> bool:
    return (env.get(AUTO_MIGRATE_KEY) or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def lock_wait_seconds(env: Mapping[str, str] = os.environ) -> float:
    raw = (env.get(LOCK_WAIT_KEY) or "").strip()
    try:
        return float(raw) if raw else DEFAULT_LOCK_WAIT_SECONDS
    except ValueError:
        return DEFAULT_LOCK_WAIT_SECONDS


def lock_key(schema: str) -> int:
    """A stable signed 64-bit advisory-lock key, one per schema."""
    digest = hashlib.sha256((_LOCK_NAMESPACE + schema).encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


class SchemaNotReady(RuntimeError):
    """The database schema does not match the code; the service must not serve."""


# -- the code's side ------------------------------------------------------------
@dataclass(frozen=True)
class MigrationTarget:
    """One service's Alembic history and the schema it owns."""

    schema: str
    script_location: str
    service: str = ""  # for messages: which alembic.ini deploy.sh runs

    @classmethod
    def for_package(
        cls, package: ModuleType, schema: str, service: str = ""
    ) -> "MigrationTarget":
        """``<package>/migrations`` — where every service keeps its env.py."""
        location = Path(package.__file__).resolve().parent / "migrations"
        return cls(schema=schema, script_location=str(location), service=service)

    def config(self, connection: Optional[Connection] = None) -> Config:
        config = Config()
        config.set_main_option("script_location", self.script_location)
        config.set_main_option("path_separator", "os")
        if connection is not None:
            config.attributes["connection"] = connection
        return config

    def script(self) -> ScriptDirectory:
        return ScriptDirectory.from_config(self.config())

    def code_revisions(self) -> tuple[tuple[str, ...], frozenset[str]]:
        """(heads, every revision this code knows)."""
        script = self.script()
        heads = tuple(sorted(script.get_heads()))
        known = frozenset(s.revision for s in script.walk_revisions())
        return heads, known


# -- the database's side ---------------------------------------------------------
class RevisionSource(Protocol):
    async def current_revisions(self, schema: str) -> Optional[tuple[str, ...]]:
        """The revisions stamped in ``<schema>.alembic_version``; ``None`` when
        the table does not exist."""


async def read_revisions(
    conn: AsyncConnection, schema: str
) -> Optional[tuple[str, ...]]:
    table = await conn.scalar(
        text("SELECT to_regclass(:t)"), {"t": f'"{schema}".alembic_version'}
    )
    if table is None:
        return None
    rows = await conn.execute(
        text(f'SELECT version_num FROM "{schema}".alembic_version')
    )
    return tuple(sorted(r[0] for r in rows))


class EngineRevisionSource:
    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def current_revisions(self, schema: str) -> Optional[tuple[str, ...]]:
        async with self._engine.connect() as conn:
            return await read_revisions(conn, schema)


# -- the comparison ---------------------------------------------------------------
class RevisionState(str, Enum):
    CURRENT = "current"
    BEHIND = "behind"
    AHEAD = "ahead"
    MISSING = "missing"


@dataclass(frozen=True)
class RevisionCheck:
    schema: str
    state: RevisionState
    current: tuple[str, ...]
    expected: tuple[str, ...]
    service: str = ""

    @property
    def ok(self) -> bool:
        return self.state is RevisionState.CURRENT

    @property
    def blocking(self) -> bool:
        """Behind or never migrated: this code would query tables that are not
        there. Ahead is not blocking (see the module docstring)."""
        return self.state in (RevisionState.BEHIND, RevisionState.MISSING)

    def message(self) -> str:
        current = ", ".join(self.current) or "none"
        expected = ", ".join(self.expected) or "none"
        where = f"schema {self.schema!r}"
        alembic = (
            f"alembic -c {self.service}/alembic.ini upgrade head"
            if self.service
            else "alembic upgrade head"
        )
        fix = (
            f"Run the migrations before starting the service (`{alembic}` with this "
            f"DATABASE_URL, as deploy.sh does), or set {AUTO_MIGRATE_KEY}=true to "
            f"apply them at startup."
        )
        if self.state is RevisionState.MISSING:
            return (
                f"{where} has no Alembic revision (never migrated); "
                f"expected revision {expected}. {fix}"
            )
        if self.state is RevisionState.BEHIND:
            return (
                f"{where} is behind: database at revision {current}, "
                f"code expects {expected}. {fix}"
            )
        if self.state is RevisionState.AHEAD:
            return (
                f"{where} is ahead: database at revision {current}, which this code "
                f"does not know (a newer release migrated it, e.g. before a "
                f"rollback); code expects {expected}. Starting anyway: migrations are "
                f"expand-only, so this release still runs on the newer schema. "
                f"Nothing is migrated backwards automatically."
            )
        return f"{where} is at head ({expected})"


def compare_revisions(
    schema: str,
    current: Optional[Iterable[str]],
    heads: Iterable[str],
    known: Iterable[str],
    service: str = "",
) -> RevisionCheck:
    expected = tuple(sorted(heads))
    cur = tuple(sorted(current or ()))
    if not cur:
        state = RevisionState.MISSING
    elif set(cur) == set(expected):
        state = RevisionState.CURRENT
    elif set(cur) - set(known):
        state = RevisionState.AHEAD
    else:
        state = RevisionState.BEHIND
    return RevisionCheck(schema, state, cur, expected, service)


async def check_revision(
    target: MigrationTarget, source: RevisionSource
) -> RevisionCheck:
    heads, known = target.code_revisions()
    current = await source.current_revisions(target.schema)
    return compare_revisions(target.schema, current, heads, known, target.service)


# -- auxiliary schemas (not Alembic-managed) ---------------------------------------
@dataclass(frozen=True)
class AuxiliarySchema:
    """A schema a service owns outside Alembic — the backend's procrastinate
    queue tables. ``present`` probes it over a SQLAlchemy connection;
    ``apply`` creates it given the database URL and returns True when it did."""

    name: str
    needed: Callable[[DbFlags], bool]
    present: Callable[[AsyncConnection], Awaitable[bool]]
    apply: Callable[[str], Awaitable[bool]]
    fix: str = ""

    def missing_message(self) -> str:
        fix = f"{self.fix} Or set" if self.fix else "Set"
        return (
            f"schema {self.name!r} is missing its tables. {fix} "
            f"{AUTO_MIGRATE_KEY}=true to apply it at startup."
        )


# -- locking + migration ------------------------------------------------------------
@asynccontextmanager
async def schema_lock(
    conn: AsyncConnection, schema: str, wait_seconds: float = DEFAULT_LOCK_WAIT_SECONDS
) -> AsyncIterator[None]:
    """Session-level advisory lock on a dedicated connection: survives the
    migration's commits, released explicitly (or by the connection closing).
    Waits at most ``wait_seconds`` for another instance's migration, polling,
    then gives up with :class:`TimeoutError`."""
    key = lock_key(schema)
    deadline = time.monotonic() + wait_seconds
    waiting = False
    while not await conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": key}):
        await conn.commit()
        if not waiting:
            logger.info("schema %r: another instance is migrating it; waiting", schema)
            waiting = True
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"schema {schema!r}: another instance held the migration lock for "
                f"more than {wait_seconds:g}s ({LOCK_WAIT_KEY})"
            )
        await asyncio.sleep(_LOCK_POLL_SECONDS)
    await conn.commit()
    try:
        yield
    finally:
        try:
            await conn.rollback()
            await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": key})
            await conn.commit()
        except Exception:  # noqa: BLE001 — closing the connection releases it too
            logger.warning(
                "schema %r: advisory unlock failed; released on close", schema
            )


def _upgrade_sync(connection: Connection, target: MigrationTarget) -> None:
    command.upgrade(target.config(connection=connection), "head")


def _applied(
    target: MigrationTarget,
    before: Optional[tuple[str, ...]],
    after: Optional[tuple[str, ...]],
) -> list[str]:
    if not after or tuple(before or ()) == tuple(after):
        return []
    if before and len(before) > 1:
        return list(after)
    script = target.script()
    upper = after[0] if len(after) == 1 else after
    lower = before[0] if before else "base"
    revisions = [s.revision for s in script.iterate_revisions(upper, lower)]
    return list(reversed(revisions))


def migration_engine(url: str) -> AsyncEngine:
    """A throw-away engine for DDL: no pool, none of the request-path timeouts."""
    return create_async_engine(url, poolclass=NullPool)


async def upgrade_schema(
    url: str, target: MigrationTarget, wait_seconds: float = DEFAULT_LOCK_WAIT_SECONDS
) -> list[str]:
    """``alembic upgrade head`` for one schema under its advisory lock.
    Returns the revisions applied (empty when already at head, or when the
    database is ahead of this code — nothing to upgrade to)."""
    engine = migration_engine(url)
    try:
        async with engine.connect() as conn:
            async with schema_lock(conn, target.schema, wait_seconds):
                before = await read_revisions(conn, target.schema)
                await conn.commit()
                _, known = target.code_revisions()
                if set(before or ()) - known:
                    return []
                await conn.execute(
                    text(f"SET lock_timeout = '{MIGRATION_LOCK_TIMEOUT}'")
                )
                await conn.commit()
                await conn.run_sync(_upgrade_sync, target)
                await conn.commit()
                after = await read_revisions(conn, target.schema)
                await conn.commit()
    finally:
        await engine.dispose()
    return _applied(target, before, after)


async def ensure_auxiliary(
    url: str, aux: AuxiliarySchema, wait_seconds: float = DEFAULT_LOCK_WAIT_SECONDS
) -> bool:
    """Apply an auxiliary schema under its advisory lock; True when applied."""
    engine = migration_engine(url)
    try:
        async with engine.connect() as conn:
            async with schema_lock(conn, aux.name, wait_seconds):
                present = await aux.present(conn)
                if not present:
                    # like Alembic's env: a no-op where postgres/init created it
                    await conn.execute(text(create_schema_if_missing_sql(aux.name)))
                await conn.commit()
                if present:
                    return False
                return await aux.apply(url)
    finally:
        await engine.dispose()


async def ensure_schema_ready(
    flags: DbFlags,
    engine: Optional[AsyncEngine],
    target: Optional[MigrationTarget],
    auxiliary: Sequence[AuxiliarySchema] = (),
    *,
    env: Mapping[str, str] = os.environ,
    revision_source: Optional[RevisionSource] = None,
) -> None:
    """Migrate (when ``DB_AUTO_MIGRATE`` is on) and verify, or raise
    :class:`SchemaNotReady`. Callers have checked the database is reachable.
    Mongo-only flags need no database: nothing is checked or migrated."""
    if not flags.requires_postgres():
        return
    if auto_migrate_enabled(env):
        if engine is None:
            raise SchemaNotReady(f"{AUTO_MIGRATE_KEY}=true but DATABASE_URL is not set")
        url = engine.url.render_as_string(hide_password=False)
        names = ([target.schema] if target else []) + [a.name for a in auxiliary]
        wait = lock_wait_seconds(env)
        try:
            if target is not None:
                applied = await upgrade_schema(url, target, wait)
                if applied:
                    # WARNING on purpose: a schema change must be visible in every
                    # service's logs, whatever level they are configured to show.
                    logger.warning(
                        "%s: schema %r migrated, applied %s",
                        AUTO_MIGRATE_KEY,
                        target.schema,
                        ", ".join(applied),
                    )
                else:
                    logger.info(
                        "%s: schema %r: nothing to apply", AUTO_MIGRATE_KEY, target.schema
                    )
            for aux in auxiliary:
                if await ensure_auxiliary(url, aux, wait):
                    logger.warning("%s: schema %r applied", AUTO_MIGRATE_KEY, aux.name)
                else:
                    logger.info(
                        "%s: schema %r already present", AUTO_MIGRATE_KEY, aux.name
                    )
        except Exception as exc:
            raise SchemaNotReady(
                f"{AUTO_MIGRATE_KEY}: migrating schema(s) {', '.join(names)} failed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc

    problems: list[str] = []
    if target is not None and flags.uses_postgres_tables():
        source = revision_source or EngineRevisionSource(_require(engine))
        check = await check_revision(target, source)
        if check.ok:
            logger.info(
                "schema %r at head (%s)", target.schema, ", ".join(check.expected)
            )
        elif check.blocking:
            problems.append(check.message())
        else:
            logger.warning("%s", check.message())
    needed_aux = [a for a in auxiliary if a.needed(flags)]
    if needed_aux:
        async with _require(engine).connect() as conn:
            for aux in needed_aux:
                if not await aux.present(conn):
                    problems.append(aux.missing_message())
    if problems:
        raise SchemaNotReady(
            "refusing to start: the database schema does not match this release.\n  "
            + "\n  ".join(problems)
        )


def _require(engine: Optional[AsyncEngine]) -> AsyncEngine:
    if engine is None:
        raise SchemaNotReady(
            "DB_*/JOBS_* flags require Postgres but DATABASE_URL is not set"
        )
    return engine
