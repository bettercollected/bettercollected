import asyncio

from backend.app.schemas.allowed_origin import (
    AllowedOriginsDocument,
)
from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import (
    FormResponseDeletionRequest,
    FormResponseDocument,
)
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_form import (
    WorkspaceFormDocument,
)
from backend.app.schemas.workspace_invitation import (
    WorkspaceUserInvitesDocument,
)
from backend.app.schemas.workspace_user import (
    WorkspaceUserDocument,
)

from beanie import init_beanie

from loguru import logger

from motor.motor_asyncio import AsyncIOMotorClient

from pymongo.errors import InvalidOperation

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


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
            # TODO Merge on extend below
            # Add mongo schemas here
            AllowedOriginsDocument,
            FormDocument,
            FormResponseDocument,
            FormPluginConfigDocument,
            WorkspaceDocument,
            WorkspaceFormDocument,
            WorkspaceUserInvitesDocument,
            WorkspaceUserDocument,
            FormResponseDeletionRequest,
            BlackListedRefreshTokens,
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
