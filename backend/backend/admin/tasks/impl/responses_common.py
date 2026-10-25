"""What the responses data tasks and their command-line scripts share: the
keyset and the opener built from it, the configured data store (Postgres, the
only one since 4.1; a request for Mongo is refused ``store_retired`` before
anything connects), and the base store class. Imported by the runner and by ``backend/scripts``; never by the
admin web process.

The keyset comes from one function, :func:`load_keyset` (the environment for
now), so it can later come from the settings store. Nothing here uses the
shared ``crypto_service`` singleton.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.spec import Refusal
from common.services.keyset import KEYSET_ENV, CryptoService, UnreadableCiphertext

logger = logging.getLogger(__name__)

CIPHERTEXT_PREFIX = b"v1:"
Opener = Callable[[str, str, bytes], bool]


class KeysetUnreadable(Exception):
    """The configured keyset cannot be loaded. Never carries the value."""


# ------------------------------------------------------------------- keyset
def load_keyset(env: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """The keyset (the env format: base64 of the JSON keyset), or None.

    The one place these tasks get it from; the settings store replaces this."""
    value = (os.environ if env is None else env).get(KEYSET_ENV)
    return value if value and value.strip() else None


async def load_task_keyset(ctx) -> Optional[str]:
    """The keyset a responses task uses: the settings store's verified row (where
    the keyset of a 4.0 stack lives, and the source the keyset tasks use), else the
    runner's environment (``TASK_RUNNER_KEYSET``), else None."""
    from backend.admin.config import AdminConfigError
    from backend.admin.tasks.impl import keyset_state

    try:
        keys = keyset_state.runner_keys()
    except AdminConfigError:
        return load_keyset()
    async with ctx.connection() as conn:
        stored = await keyset_state.read_stored(conn, keys)
    return stored.value if stored is not None else load_keyset()


def make_opener(keyset: str, *, lenient: bool = False) -> Opener:
    """``opens(workspace_id, form_id, value)``: whether ``value`` decrypts under
    that context. The plaintext is dropped here, never kept or printed.

    ``lenient`` treats any failure as "does not open"; otherwise only an
    unreadable ciphertext is, and other errors propagate."""
    try:
        service = CryptoService(keyset)
    except Exception:  # parse and tink errors can quote their input
        raise KeysetUnreadable("the keyset cannot be loaded") from None

    def opens(workspace_id: str, form_id: str, value: bytes) -> bool:
        try:
            service.decrypt(workspace_id=workspace_id, form_id=form_id, data=value)
        except UnreadableCiphertext:
            return False
        except Exception:
            if lenient:
                return False
            raise
        return True

    return opens


def keyset_fingerprint(keyset: str) -> str:
    """A short digest of the keyset's key ids and key-material digests, to tell
    on resume that it is still the same keyset. Reveals nothing about the keys."""
    from common.services.keyset import key_digest, parse_keyset

    parsed = parse_keyset(keyset)
    parts = sorted(f"{k.key_id}:{key_digest(k)}" for k in parsed.key)
    parts.append(f"primary:{parsed.primary_key_id}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


# ------------------------------------------------------------------- stores
STORE_NAMES = ("postgres",)


def plan_task_stores(choice: StoreChoice, configured: List[str]) -> List[str]:
    """The stores a task covers: Postgres alone (the store rule shared by the
    responses and keyset tasks).

    * ``postgres`` and ``auto`` (the default; ``auto`` is kept for parameters
      saved before 4.1): Postgres, which must be configured
      (``store_not_configured``);
    * ``mongo`` and ``both``: refused ``store_retired``, whatever is
      configured. Nothing connects to Mongo: it is read only by the import
      from 4.0 (``python -m backend.migrate``)."""
    if choice in (StoreChoice.mongo, StoreChoice.both):
        raise Refusal("store_retired")
    if "postgres" not in configured:
        raise Refusal("store_not_configured")
    return ["postgres"]


@dataclass(frozen=True)
class StoreConfig:
    # the connection string carries a password: never in a repr or a log
    database_url: Optional[str] = field(repr=False)

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "StoreConfig":
        env = os.environ if env is None else env
        return cls(database_url=(env.get("DATABASE_URL") or "").strip() or None)

    def configured(self) -> List[str]:
        return ["postgres"] if self.database_url else []

    def resolve(self, choice: StoreChoice) -> List[str]:
        """The stores to cover (:func:`plan_task_stores`)."""
        return plan_task_stores(choice, self.configured())


class PostgresBase:
    name = "postgres"

    def __init__(self, engine):
        self.engine = engine  # SQLAlchemy AsyncEngine

    def encode_key(self, key) -> str:
        return str(key)

    def decode_key(self, text: str):
        return text

    async def ping(self) -> None:
        from sqlalchemy import text

        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def count_responses(self) -> int:
        from sqlalchemy import func, select

        from backend.db.models import FormResponseRow

        async with self.engine.connect() as conn:
            return (
                await conn.execute(select(func.count()).select_from(FormResponseRow))
            ).scalar_one()

    async def links(self) -> Dict[str, List[str]]:
        from sqlalchemy import select

        from backend.db.models import WorkspaceFormRow

        links: Dict[str, List[str]] = defaultdict(list)
        async with self.engine.connect() as conn:
            rows = await conn.execute(
                select(
                    WorkspaceFormRow.form_id, WorkspaceFormRow.workspace_id
                ).order_by(WorkspaceFormRow.id)
            )
            for form_id, workspace in rows:
                if workspace and workspace not in links[str(form_id)]:
                    links[str(form_id)].append(workspace)
        return links


@asynccontextmanager
async def open_stores(
    config: StoreConfig,
    names: List[str],
    classes: Mapping[str, Any],
    *,
    read_only: bool,
):
    """Connect to the named stores (Postgres only); closed on exit.
    ``read_only`` makes every transaction read only at the session level, so a
    bug cannot write."""
    closers: list = []
    stores: list = []
    try:
        for name in names:
            if name != "postgres":  # a plan never names another; never connect
                raise Refusal("store_retired")
            from sqlalchemy.ext.asyncio import create_async_engine

            settings = {"statement_timeout": "60000"}
            if read_only:
                settings["default_transaction_read_only"] = "on"
            engine = create_async_engine(
                config.database_url,
                pool_size=2,
                max_overflow=0,
                connect_args={"server_settings": settings},
            )
            closers.append(engine.dispose)
            stores.append(classes["postgres"](engine))
        yield stores
    finally:
        for close in reversed(closers):
            try:
                await close()
            except Exception:  # noqa: BLE001 - closing must not mask the outcome
                pass


async def preflight(
    choice: StoreChoice,
    classes: Mapping[str, Any],
    *,
    read_only: bool,
    env: Optional[Mapping[str, str]] = None,
    keyset: Optional[str] = None,
):
    """The checks both tasks share, in order; each failure is a ``Refusal``.

    Returns ``(config, store names, keyset)``. ``keyset`` is the one the caller
    resolved (:func:`load_task_keyset`); without one the environment is read.
    A wrong or empty database must not look clean, so a store with no responses
    at all is refused."""
    config = StoreConfig.from_env(env)
    names = config.resolve(choice)
    keyset = keyset or load_keyset(env)
    if keyset is None:
        raise Refusal("keyset_missing")
    try:
        make_opener(keyset)
    except KeysetUnreadable:
        raise Refusal("keyset_unreadable") from None
    async with open_stores(config, names, classes, read_only=read_only) as stores:
        for store in stores:
            try:
                await store.ping()
                count = await store.count_responses()
            except Exception:  # noqa: BLE001 - never surface a driver message
                raise Refusal("store_unreachable") from None
            if count == 0:
                raise Refusal("store_empty")
    return config, names, keyset
