import inspect
import logging

import loguru
from beanie import init_beanie

from auth.config import settings
from common.db import MirrorWriteFailureDocument

log = logging.getLogger(__name__)

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


async def init_db(database_client):
    # No motor `get_io_loop` shim — beanie 2.x / pymongo's async client
    # doesn't use it, and it crashed init_beanie on the newer versions.
    db = database_client[settings.mongo_settings.DB]
    await init_beanie(
        database=db, document_models=[*document_models, MirrorWriteFailureDocument]
    )
    loguru.logger.info("Database connected successfully.")


async def close_db(database_client):
    try:
        result = database_client.close()
        if inspect.isawaitable(result):
            await result
        loguru.logger.info("Database disconnected successfully.")
    except Exception as e:
        loguru.logger.error("Database disconnect failure.")
        loguru.logger.error(e)
