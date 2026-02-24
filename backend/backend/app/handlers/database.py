import inspect

from beanie import init_beanie
from loguru import logger
from pymongo import AsyncMongoClient
from pymongo.errors import InvalidOperation

from backend.app.schemas.allowed_origin import (
    AllowedOriginsDocument,
)
from backend.app.schemas.apscheduler import APSchedulerDocument
from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.schemas.form_plugin_config import FormPluginConfigDocument
from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupMemberDocument,
    ResponderGroupFormDocument,
)
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

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


async def init_scheduler_db(client: AsyncMongoClient):
    db = client["apscheduler"]
    await init_beanie(database=db, document_models=[APSchedulerDocument])
    pass


async def init_db(db: str, client: AsyncMongoClient):
    """
    Asynchronously initializes the database connection and beanie for the app.

    This function initializes beanie using the specified database and document models.

    Args:
        db: Database name
        client: AsyncMongoClient instance

    Returns:
        None
    """
    db = client[db]
    document_models.extend(
        [
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
            ResponderGroupFormDocument,
            ResponderGroupMemberDocument,
            ResponderGroupDocument,
        ]
    )
    await init_beanie(
        database=db,
        document_models=document_models,
    )
    logger.info("Database connected successfully.")


async def close_db(client: AsyncMongoClient):
    """
    Closes the database connection.

    Returns:
        None
    """
    try:
        result = client.close()
        if inspect.isawaitable(result):
            await result
        logger.info("Database disconnected successfully.")
    except InvalidOperation as error:
        logger.error("Database disconnect failure.")
        logger.error(error)
