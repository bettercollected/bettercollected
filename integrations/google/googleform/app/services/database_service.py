import inspect
import logging

from beanie import init_beanie
from pymongo import AsyncMongoClient

from googleform.config import settings

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


async def init_db():
    global _client
    _client = AsyncMongoClient(mongo_settings.URI)
    db = _client[mongo_settings.DB]
    await init_beanie(database=db, document_models=document_models)
    log.info("Database connected successfully.")


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
