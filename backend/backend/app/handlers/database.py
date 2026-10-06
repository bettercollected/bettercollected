import inspect

from beanie import init_beanie
from loguru import logger
from pymongo import AsyncMongoClient
from pymongo.errors import InvalidOperation

from backend.app.schemas.allowed_origin import (
    AllowedOriginsDocument,
)
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
from backend.app.schemas.workspace_domain import WorkspaceDomainDocument
from backend.app.schemas.sso_connection import SsoConnectionDocument
from backend.app.schemas.sso_used_state import SsoUsedStateDocument
from backend.app.schemas.scim import (
    ScimDirectoryDocument,
    ScimEventDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimUserDocument,
)
from backend.app.schemas.flow_event import FlowEventDocument
from backend.app.schemas.rate_limit_counter import RateLimitCounterDocument
from common.db import MirrorWriteFailureDocument

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


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
            FlowEventDocument,
            RateLimitCounterDocument,
            WorkspaceDomainDocument,
            SsoConnectionDocument,
            SsoUsedStateDocument,
            ScimDirectoryDocument,
            ScimUserDocument,
            ScimGroupDocument,
            ScimGroupMemberDocument,
            ScimEventDocument,
            MirrorWriteFailureDocument,
        ]
    )
    await init_beanie(
        database=db,
        document_models=document_models,
    )
    await ensure_membership_unique_index(db)
    logger.info("Database connected successfully.")


MEMBERSHIP_INDEX = "uq_workspace_users_workspace_user"


async def ensure_membership_unique_index(db) -> bool:
    """One membership per workspace and user (``workspace_users``). Created
    here, not in the document's settings, so a database that still holds
    duplicates starts anyway: it logs an ERROR naming the check to run
    (``python -m backend.membership_duplicates``) and the inserts keep
    reading the existing row instead. Nothing is ever deleted here."""
    from pymongo import ASCENDING
    from pymongo.errors import DuplicateKeyError, OperationFailure

    try:
        await db["workspace_users"].create_index(
            [("workspace_id", ASCENDING), ("user_id", ASCENDING)],
            unique=True,
            name=MEMBERSHIP_INDEX,
        )
        return True
    except (DuplicateKeyError, OperationFailure) as error:
        logger.error(
            "workspace_users holds duplicate memberships (same workspace and "
            "user), so the unique index {} was not created ({}). Run `python -m "
            "backend.membership_duplicates` and resolve them by hand (see "
            "docs/sso.md, 'Duplicate memberships').",
            MEMBERSHIP_INDEX,
            type(error).__name__,
        )
        return False


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
