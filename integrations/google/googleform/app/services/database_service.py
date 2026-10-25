"""Beanie set-up for the document classes, without a Mongo server.

The service stores its data in Postgres only (since 4.1). Its documents are
still Beanie classes, read and written through the Postgres repository
(``common.db.beanie_bridge``), and Beanie refuses to construct a document of
an uninitialised class. So the classes are initialised on a client that never
connects (``common.db.mongo``): no ``buildInfo``, no indexes, and ``MONGO_URI``
is not read. Mongo is read only by the import from 4.0
(``python -m googleform.migrate``).
"""

import inspect
import logging

from pymongo import AsyncMongoClient

from common.db import init_documents, mongo_client

log = logging.getLogger(__name__)

# Created inside init_db (a running event loop), not at import.
_client: "AsyncMongoClient | None" = None

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


def uses_mongo() -> bool:
    """Never: the google group is served from Postgres only."""
    return False


async def init_db():
    """Set the document classes up; nothing is sent to a Mongo server."""
    global _client
    _client = mongo_client(None, required=False)
    await init_documents(_client["not_used"], document_models, required=False)
    log.info("Mongo is not used by the Google Forms integration; not connected.")


async def close_db():
    try:
        if _client is not None:
            result = _client.close()
            if inspect.isawaitable(result):
                await result
        log.info("Database disconnected successfully.")
    except Exception as e:
        log.error("Database disconnect failure.")
        log.error(e)
