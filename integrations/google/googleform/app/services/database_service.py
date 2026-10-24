import inspect
import logging
from typing import Optional

from pymongo import AsyncMongoClient

from googleform.config import settings
from common.db import (
    SERVICE_GROUPS,
    MirrorWriteFailureDocument,
    init_documents,
    mongo_client,
    mongo_required,
)

log = logging.getLogger(__name__)
mongo_settings = settings.mongo_settings

# Beanie 2.x dropped motor for pymongo's native async client. The client is
# created inside init_db (a running event loop), not at import — constructing
# an AsyncMongoClient outside the loop triggers an "AsyncMongoClient in a
# different event loop" error when it's first used at startup.
_client: "AsyncMongoClient | None" = None

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


def uses_mongo() -> bool:
    """Whether the google group still uses Mongo (the routing flags decide)."""
    from googleform.app.containers import Container  # the container imports the schemas

    return mongo_required(Container.flags(), SERVICE_GROUPS["google"])


async def init_db(required: Optional[bool] = None):
    """Beanie on the service's client. ``required`` defaults to the flags: once
    the google group is on Postgres only, nothing is sent to Mongo (no
    ``buildInfo``, no indexes) and the client never connects."""
    global _client
    if required is None:
        required = uses_mongo()
    _client = mongo_client(mongo_settings.URI, required=required)
    db = _client[mongo_settings.DB]
    await init_documents(
        db, [*document_models, MirrorWriteFailureDocument], required=required
    )
    if required:
        log.info("Database connected successfully.")
    else:
        log.info("Mongo is not used by the google group; not connected.")


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
