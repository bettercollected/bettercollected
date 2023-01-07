import asyncio

from beanie import init_beanie
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import InvalidOperation

from common.schemas.form_scheduler_config import SchedulerFormConfigDocument
from common.schemas.google_form import GoogleFormDocument
from common.schemas.google_form_response import GoogleFormResponseDocument
from common.schemas.oauth_credential import Oauth2CredentialDocument
from settings import settings

_mongo_settings = settings.mongo_settings
_client = AsyncIOMotorClient(_mongo_settings.uri)


async def init_db():
    """
    Asynchronously initializes the database connection and beanie for the app.

    This function uses an asyncio loop to get the running loop, and uses it
    to create a MotorClient instance with the specified MongoDB settings. It
    then initializes beanie using the specified database and document models.

    Returns:
    None
    """
    _client.get_io_loop = asyncio.get_running_loop
    db = _client[_mongo_settings.db]
    await init_beanie(
        database=db,
        document_models=[
            # Add mongo schemas here
            SchedulerFormConfigDocument,
            GoogleFormDocument,
            GoogleFormResponseDocument,
            Oauth2CredentialDocument,
        ],
    )
    logger.info("Database connected successfully.")


async def close_db():
    """
    Asynchronously closes the database connection.

    This function attempts to close the MotorClient instance, and logs a success
    or failure message.

    Returns:
    None
    """
    try:
        _client.close()
        logger.info("Database disconnected successfully.")
    except InvalidOperation as error:
        logger.error("Database disconnect failure.")
        logger.error(error)
