import inspect

from dependency_injector import providers
from loguru import logger
from pymongo import AsyncMongoClient
from pymongo.errors import InvalidOperation

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
    document_models.extend([MirrorWriteFailureDocument])
    await init_documents(db, document_models, required=required)
    if not required:
        logger.info("Mongo is not used by any repository group; not connected.")
        return
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
