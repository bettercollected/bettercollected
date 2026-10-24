import inspect

from dependency_injector import providers
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
from backend.app.schemas.api_idempotency_record import ApiIdempotencyRecordDocument
from common.db import MirrorWriteFailureDocument, init_documents, mongo_client

document_models = []


def entity(cls):
    document_models.append(cls)
    return cls


async def open_mongo(container, uri: str, db: str, *, required: bool):
    """The container's Mongo client with Beanie initialised on it.

    A client already set on the container (a test's) is used as it is;
    otherwise one is created here, inside the running event loop. While no
    repository group uses Mongo (``required`` false, see
    ``backend.db.startup.mongo_required``) nothing connects: Beanie is set up
    without a request to the server and the client never opens.
    """
    client = container.database_client()
    if client is None:
        client = mongo_client(uri, required=required)
        container.database_client.override(providers.Object(client))
    await init_db(db, client, required=required)
    return client


async def init_db(db: str, client: AsyncMongoClient, *, required: bool = True):
    """
    Asynchronously initializes the database connection and beanie for the app.

    This function initializes beanie using the specified database and document models.
    With ``required`` false (no repository group uses Mongo) nothing is sent to
    the server: no ``buildInfo``, no index creation.

    Args:
        db: Database name
        client: AsyncMongoClient instance
        required: whether Mongo is used (and so must answer)

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
            ApiIdempotencyRecordDocument,
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
    await init_documents(db, document_models, required=required)
    if not required:
        logger.info("Mongo is not used by any repository group; not connected.")
        return
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
