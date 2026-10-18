"""What the responses data tasks and their command-line scripts share: the
keyset and the opener built from it, the configured data stores, and the base
store classes. Imported by the runner and by ``backend/scripts``; never by the
admin web process.

The keyset comes from one function, :func:`load_keyset` (the environment for
now), so it can later come from the settings store. Nothing here uses the
shared ``crypto_service`` singleton.
"""

from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional

from backend.admin.tasks.catalog.responses_common import StoreChoice
from backend.admin.tasks.spec import Refusal
from common.services.keyset import KEYSET_ENV, CryptoService, UnreadableCiphertext

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
@dataclass(frozen=True)
class StoreConfig:
    mongo_uri: Optional[str]
    mongo_db: str
    database_url: Optional[str]

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "StoreConfig":
        env = os.environ if env is None else env
        return cls(
            mongo_uri=(env.get("MONGO_URI") or "").strip() or None,
            mongo_db=(env.get("MONGO_DB") or "").strip() or "bettercollected_backend",
            database_url=(env.get("DATABASE_URL") or "").strip() or None,
        )

    def resolve(self, choice: StoreChoice) -> List[str]:
        """The stores to cover. Refuses (``store_not_configured``) when a store
        asked for is not configured, or when ``auto`` finds none."""
        configured = [
            name
            for name, ok in (("mongo", self.mongo_uri), ("postgres", self.database_url))
            if ok
        ]
        wanted = {
            StoreChoice.auto: configured,
            StoreChoice.both: ["mongo", "postgres"],
            StoreChoice.mongo: ["mongo"],
            StoreChoice.postgres: ["postgres"],
        }[choice]
        if not wanted or any(name not in configured for name in wanted):
            raise Refusal("store_not_configured")
        return wanted


class MongoBase:
    name = "mongo"

    def __init__(self, database):
        self.db = database  # pymongo AsyncDatabase

    def encode_key(self, key) -> str:
        return str(key)

    def decode_key(self, text: str):
        from bson import ObjectId

        return ObjectId(text)

    async def ping(self) -> None:
        await self.db.command("ping")

    async def count_responses(self) -> int:
        return await self.db["form_responses"].estimated_document_count()

    async def links(self) -> Dict[str, List[str]]:
        links: Dict[str, List[str]] = defaultdict(list)
        cursor = (
            self.db["workspace_forms"]
            .find({}, {"form_id": 1, "workspace_id": 1})
            .sort("_id", 1)
        )
        async for row in cursor:
            workspace = str(row.get("workspace_id"))
            form_id = str(row.get("form_id"))
            if row.get("workspace_id") and workspace not in links[form_id]:
                links[form_id].append(workspace)
        return links


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
    """Connect to the named stores; closed on exit. ``read_only`` makes every
    Postgres transaction read only at the session level, so a bug cannot write
    (Mongo is only ever written by calls a read-only task does not make)."""
    closers: list = []
    stores: list = []
    try:
        for name in names:
            if name == "mongo":
                from pymongo import AsyncMongoClient

                client = AsyncMongoClient(config.mongo_uri, serverSelectionTimeoutMS=5000)
                closers.append(client.close)
                stores.append(classes["mongo"](client[config.mongo_db]))
            else:
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
):
    """The checks both tasks share, in order; each failure is a ``Refusal``.

    Returns ``(config, store names, keyset)``. A wrong or empty database must
    not look clean, so a store with no responses at all is refused."""
    config = StoreConfig.from_env(env)
    names = config.resolve(choice)
    keyset = load_keyset(env)
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
