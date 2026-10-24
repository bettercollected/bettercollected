import inspect
import logging

import loguru

from auth.config import settings
from common.db import MirrorWriteFailureDocument, init_documents

log = logging.getLogger(__name__)

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


async def init_db(database_client, *, required: bool = True):
    """Beanie on ``database_client``. With ``required`` false (the auth group
    is on Postgres only) nothing is sent to Mongo: the documents are set up
    without ``buildInfo`` or index creation and the client never connects."""
    # No motor `get_io_loop` shim — beanie 2.x / pymongo's async client
    # doesn't use it, and it crashed init_beanie on the newer versions.
    db = database_client[settings.mongo_settings.DB]
    await init_documents(
        db, [*document_models, MirrorWriteFailureDocument], required=required
    )
    if required:
        loguru.logger.info("Database connected successfully.")
    else:
        loguru.logger.info("Mongo is not used by the auth group; not connected.")


async def close_db(database_client):
    try:
        result = database_client.close()
        if inspect.isawaitable(result):
            await result
        loguru.logger.info("Database disconnected successfully.")
    except Exception as e:
        loguru.logger.error("Database disconnect failure.")
        loguru.logger.error(e)
