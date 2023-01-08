import asyncio

from beanie import init_beanie
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import InvalidOperation

from common.schemas.form_scheduler_config import SchedulerFormConfigDocument
from common.schemas.google_form import GoogleFormDocument
from common.schemas.google_form_response import GoogleFormResponseDocument
from common.schemas.oauth_credential import Oauth2CredentialDocument


async def init_db(db: str, client: AsyncIOMotorClient):
    """
    Asynchronously initializes the database connection and beanie for the app.

    This function uses an asyncio loop to get the running loop, and uses it
    to create a MotorClient instance with the specified MongoDB settings. It
    then initializes beanie using the specified database and document models.

    Args:
        db: Database name
        client: Database URI

    Returns:
        None
    """
    client.get_io_loop = asyncio.get_running_loop
    db = client[db]
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


async def close_db(client: AsyncIOMotorClient):
    """
    Asynchronously closes the database connection.

    This function attempts to close the MotorClient instance, and logs a success
    or failure message.

    Returns:
        None
    """
    try:
        client.close()
        logger.info("Database disconnected successfully.")
    except InvalidOperation as error:
        logger.error("Database disconnect failure.")
        logger.error(error)
