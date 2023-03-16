import asyncio
import logging

from beanie import init_beanie

from auth.config import settings

log = logging.getLogger(__name__)

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


async def init_db(database_client):
    database_client.get_io_loop = asyncio.get_running_loop
    db = database_client[settings.mongo_settings.DB]
    await init_beanie(database=db, document_models=document_models)
    log.info("Database connected successfully.")


async def close_db(database_client):
    try:
        database_client().close()
        log.info("Database disconnected successfully.")
    except Exception as e:
        log.error("Database disconnect failure.")
        log.error(e)
