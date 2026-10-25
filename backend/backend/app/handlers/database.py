import inspect
from typing import Optional

from dependency_injector import providers
from loguru import logger
from pymongo import AsyncMongoClient
from pymongo.errors import InvalidOperation, PyMongoError

from backend.app.schemas.responder_group import (
    ResponderGroupDocument,
    ResponderGroupMemberDocument,
    ResponderGroupFormDocument,
)
from backend.app.schemas.standard_form_response import (
    DELETION_REQUEST_INDEX,
    DELETION_REQUEST_INDEX_MODEL,
    LEGACY_DELETION_REQUEST_INDEX,
    FormResponseDeletionRequest,
    FormResponseDocument,
    drop_legacy_deletion_request_index,
)
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
            FormResponseDocument,
            FormResponseDeletionRequest,
            ResponderGroupFormDocument,
            ResponderGroupMemberDocument,
            ResponderGroupDocument,
            MirrorWriteFailureDocument,
        ]
    )
    await init_documents(db, document_models, required=required)
    if not required:
        logger.info("Mongo is not used by any repository group; not connected.")
        return
    await ensure_deletion_request_indexes(db)
    logger.info("Database connected successfully.")


async def _duplicate_pairs(collection, keys, match) -> Optional[int]:
    """How many ``keys`` combinations more than one document of ``collection``
    (among those matching ``match``) holds; None when that can't be counted.
    Counts only: no ids or values."""
    try:
        cursor = await collection.aggregate(
            [
                {"$match": match},
                {"$group": {"_id": {k: f"${k}" for k in keys}, "n": {"$sum": 1}}},
                {"$match": {"n": {"$gt": 1}}},
                {"$count": "pairs"},
            ]
        )
        found = await cursor.to_list(1)
        return found[0]["pairs"] if found else 0
    except PyMongoError:
        return None


async def ensure_deletion_request_indexes(db) -> bool:
    """Deletion requests per workspace (``responses_deletion_requests``, app
    revision 0020 in Postgres): drop the superseded per-response unique index
    a database from before still has (it refuses a workspace's request, or
    its mirrored copy, while another workspace has one for the same
    response), then build the per-workspace one. Neither stops the service:
    a failure is logged as an ERROR and the start goes on. True when both
    are in place."""
    collection = db["responses_deletion_requests"]
    done = True
    try:
        if await drop_legacy_deletion_request_index(collection):
            logger.info(
                "Dropped the superseded index {} from responses_deletion_requests.",
                LEGACY_DELETION_REQUEST_INDEX,
            )
    except PyMongoError as error:
        done = False
        logger.error(
            "Could not drop the superseded index {} from responses_deletion_requests "
            "({}): while it exists, a workspace's deletion request for a response "
            "another workspace already has one for is refused. Drop it by hand: "
            "db.responses_deletion_requests.dropIndex('{}').",
            LEGACY_DELETION_REQUEST_INDEX,
            type(error).__name__,
            LEGACY_DELETION_REQUEST_INDEX,
        )
    try:
        await collection.create_indexes([DELETION_REQUEST_INDEX_MODEL])
    except PyMongoError as error:
        done = False
        pairs = await _duplicate_pairs(
            collection, ("form_id", "response_id", "provider", "workspace_id"), {}
        )
        logger.error(
            "The unique index {} on responses_deletion_requests was not created "
            "({}); requests filed more than once for the same response, provider "
            "and workspace: {}. The service runs without it.",
            DELETION_REQUEST_INDEX,
            type(error).__name__,
            "unknown" if pairs is None else pairs,
        )
    return done


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
