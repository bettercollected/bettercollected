import asyncio
import logging

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from auth.config import settings

log = logging.getLogger(__name__)
mongo_settings = settings.mongo_settings
_client = AsyncIOMotorClient(mongo_settings.URI)

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


async def init_db():
    _client.get_io_loop = asyncio.get_running_loop
    db = _client[mongo_settings.DB]
    await init_beanie(database=db,
                      document_models=document_models)
    log.info("Database connected successfully.")


async def close_db():
    try:
        _client.close()
        log.info("Database disconnected successfully.")
    except Exception as e:
        log.error("Database disconnect failure.")
        log.error(e)
