"""MongoDB at startup: connected only while some repository group uses it.

The routing flags decide (:meth:`common.db.flags.DbFlags.uses_mongo`): once
every repository group of a service reads from and writes only to Postgres,
with no shadow reads, nothing the service serves touches Mongo, and the
process starts with ``MONGO_URI`` unset or Mongo down. While any group still
uses Mongo, startup is unchanged: Beanie's initialisation talks to the server
and fails the process when it is unreachable.

Beanie is initialised either way. The Postgres twins hand out the same
Document classes, and Beanie refuses to construct a Document of an
uninitialised class. Without Mongo the classes get collection handles on a
client that never connects (pymongo's async client connects on first use),
and the initialisation skips the two things that would reach a server: the
``buildInfo`` probe and index creation. The client points at
:data:`NOT_USED_URI`, a name that never resolves, with a short server
selection timeout: code that reaches Mongo anyway fails within a second with
the reason in the address, instead of quietly reading a store that is no
longer written.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from beanie import View, init_beanie
from beanie.odm.utils.init import Initializer
from pymongo import AsyncMongoClient

from common.db.flags import DbFlags
from common.db.tombstones import ensure_mongo_ttl, tombstone_deletes

#: Where the client of a process that does not use Mongo points (".invalid" never resolves).
NOT_USED_URI = "mongodb://mongo-not-used.invalid:27017/"
NOT_USED_TIMEOUT_MS = 1000
#: The server major version Beanie is told without asking one (it gates time-series collections only).
ASSUMED_MAJOR_VERSION = 7


def mongo_required(flags: DbFlags, groups: Iterable[str]) -> bool:
    """Whether a service with these repository ``groups`` needs Mongo."""
    return flags.uses_mongo(groups)


def mongo_client(uri: Optional[str], *, required: bool) -> AsyncMongoClient:
    """The service's client: on ``uri`` when Mongo is required, else one that
    never connects (and ``uri`` may be unset)."""
    if required:
        return AsyncMongoClient(uri)
    return AsyncMongoClient(NOT_USED_URI, serverSelectionTimeoutMS=NOT_USED_TIMEOUT_MS)


class _OfflineInitializer(Initializer):
    """Beanie's initialiser without its server round trip: the collection list
    and server version it caches are only consulted for time-series
    collections and views, which none of the services declare."""

    async def _load_cached_info(self) -> None:
        self._database_major_version = ASSUMED_MAJOR_VERSION
        self._existing_collections = []


async def init_documents(
    database: Any,
    document_models: Sequence[type],
    *,
    required: bool,
) -> None:
    """``init_beanie`` when Mongo is required; otherwise the same class set-up
    with no request to the server (no ``buildInfo``, no indexes)."""
    if required:
        await init_beanie(database=database, document_models=list(document_models))
        # every delete records a tombstone first (common.db.tombstones)
        tombstone_deletes(document_models)
        await ensure_mongo_ttl(database)
        return
    views = [m for m in document_models if isinstance(m, type) and issubclass(m, View)]
    if views:  # a view is (re)created on the server: it needs Mongo
        raise TypeError(f"views need a Mongo server: {[v.__name__ for v in views]}")
    await _OfflineInitializer(
        database=database, document_models=list(document_models), skip_indexes=True
    )


def mongo_status(required: bool) -> dict:
    """What a status endpoint reports for Mongo."""
    return {"used": required, "status": "used" if required else "not used"}
