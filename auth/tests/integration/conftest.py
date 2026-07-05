from auth.app import get_application
from auth.app.container import container
from auth.config import settings

from dependency_injector import providers

from fastapi.testclient import TestClient

import mongomock.database
from mongomock_motor import AsyncMongoMockClient

import pytest

# beanie >= 2.1 initialises collections by calling
# `list_collection_names(authorizedCollections=...)`. Real MongoDB supports that
# kwarg, but mongomock (backing the in-memory test client) does not, and the
# argument is meaningless for an in-memory database. Drop unknown kwargs so the
# mock stays compatible with newer beanie. Test-only shim.
_orig_list_collection_names = mongomock.database.Database.list_collection_names


def _list_collection_names(self, filter=None, session=None, **_kwargs):
    return _orig_list_collection_names(self, filter=filter, session=session)


mongomock.database.Database.list_collection_names = _list_collection_names


@pytest.fixture
def app_runner():
    container.database_client.override(providers.Singleton(AsyncMongoMockClient))
    app = get_application()

    with TestClient(
        app,
        base_url=f"http://testserver{settings.API_ROOT_PATH}",
    ) as client:
        yield client
