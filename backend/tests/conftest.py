import asyncio
from pathlib import Path
import os
from typing import Any, Coroutine
from unittest.mock import patch

from dotenv import load_dotenv

# pytest-xdist: each worker ("gw0", "gw1", ...) gets its own Mongo and Postgres
# databases, named after the configured ones plus the worker id. This has to
# happen before the backend is imported: some modules read DATABASE_URL at import
# time (the procrastinate app). Without xdist nothing changes.
XDIST_WORKER = os.environ.get("PYTEST_XDIST_WORKER", "")
# The configured Postgres URL; under xdist the server's admin connection and the
# "test" guard use it, and each worker's database is derived from it.
BASE_DATABASE_URL = os.environ.get("DATABASE_URL", "")
if XDIST_WORKER:
    load_dotenv(os.getenv("DOTENV_PATH", ".env.test"))
    BASE_DATABASE_URL = os.environ.get("DATABASE_URL", "")
    os.environ["MONGO_TEST_DB"] = (
        f"{os.environ.get('MONGO_TEST_DB', 'bettercollected_test')}_{XDIST_WORKER}"
    )
    if BASE_DATABASE_URL:
        _url, _, _query = BASE_DATABASE_URL.partition("?")
        os.environ["DATABASE_URL"] = f"{_url}_{XDIST_WORKER}" + (
            f"?{_query}" if _query else ""
        )

import httpx
import pymongo
import pytest
import pytest_asyncio
from common.models.form_import import FormImportResponse
from common.models.standard_form import StandardForm, StandardFormResponse

from tests.app.auth_helpers import access_token
from backend.app import get_application
from backend.app.asgi import lifespan
from backend.app.container import container
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.schemas.standard_form import FormDocument
from backend.app.schemas.standard_form_response import FormResponseDocument
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.schemas.workspace_user import WorkspaceUserDocument
from backend.app.services import workspace_service
from backend.config import settings
from tests.app.controllers.data import (
    formData,
    formResponse,
    user_info,
    testUser,
    testUser1,
    testUser2,
    proUser,
    invited_user,
    formData_test,
)

load_dotenv(os.getenv("DOTENV_PATH", ".env.test"))

TEST_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost")
TEST_MONGO_DB = os.getenv("MONGO_TEST_DB", "bettercollected_test")


TEST_DATABASE_URL = os.getenv("DATABASE_URL", "")
if not XDIST_WORKER:
    BASE_DATABASE_URL = TEST_DATABASE_URL


def _database_name(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?")[0]


def _postgres_configured() -> bool:
    """A Postgres test database is available. Guarded: only databases whose name
    contains "test" are ever created, migrated, truncated or dropped by the suite.
    Under xdist the configured name must pass; the worker's adds a suffix."""
    if not TEST_DATABASE_URL:
        return False
    return "test" in _database_name(BASE_DATABASE_URL) and "test" in _database_name(
        TEST_DATABASE_URL
    )


async def _postgres_admin(statement: str) -> None:
    """Run one statement on the server's maintenance database (``postgres``)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from common.db.engine import normalise_url

    url, _, query = normalise_url(BASE_DATABASE_URL).partition("?")
    admin_url = url.rpartition("/")[0] + "/postgres" + (f"?{query}" if query else "")
    engine = create_async_engine(
        admin_url, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text(statement))
    finally:
        await engine.dispose()


async def _create_worker_database() -> None:
    """A fresh Postgres database for this xdist worker (a leftover from an
    interrupted run is replaced). It lives for one test session, so its commits
    don't wait for the WAL flush (on a server with fsync on, that wait was most
    of the Postgres modes' time)."""
    name = _database_name(TEST_DATABASE_URL)
    await _postgres_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    await _postgres_admin(f'CREATE DATABASE "{name}"')
    await _postgres_admin(f'ALTER DATABASE "{name}" SET synchronous_commit = off')


async def _drop_worker_database() -> None:
    name = _database_name(TEST_DATABASE_URL)
    await _postgres_admin(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _alembic_upgrade_head() -> None:
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option(
        "script_location", str(backend_dir / "backend" / "migrations")
    )
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(config, "head")


async def _truncate_postgres() -> None:
    """Reset the Postgres test tables between tests.

    TRUNCATE has a fixed per-table cost (locks, relfilenode swap, WAL) that
    across 35 tables ran to ~1.3 s per test and dominated the suite; deleting
    from every table was not much better. So: one round trip asks which tables
    hold rows at all, and only those are cleared. Typically a handful.
    """
    from sqlalchemy import text

    import backend.db.models  # noqa: F401
    from backend.db.base import Base

    engine = container.pg_engine()
    if engine is None:
        return
    tables = [f'"{t.schema}"."{t.name}"' for t in Base.metadata.sorted_tables]
    probe = " UNION ALL ".join(
        f"SELECT '{name}' AS t WHERE EXISTS (SELECT 1 FROM {name})" for name in tables
    )
    async with engine.begin() as conn:
        non_empty = [row[0] for row in await conn.execute(text(probe))]
        for name in non_empty:
            await conn.execute(text(f"DELETE FROM {name}"))


async def _clear_mongo(db) -> None:
    """Empty every collection that holds documents.

    Like the Postgres reset: a delete_many on each of the ~35 collections cost
    a round trip apiece on every test, although a test touches only a few. One
    aggregation (each collection's first document, tagged with its name, via
    $unionWith) finds the non-empty ones, and only those are cleared.
    """
    names = await db.list_collection_names(filter={"type": "collection"})
    if not names:
        return

    def first_of(name: str) -> list:
        return [{"$limit": 1}, {"$project": {"_id": 0, "c": {"$literal": name}}}]

    pipeline = first_of(names[0]) + [
        {"$unionWith": {"coll": name, "pipeline": first_of(name)}} for name in names[1:]
    ]
    cursor = await db[names[0]].aggregate(pipeline)
    for name in [doc["c"] async for doc in cursor]:
        await db[name].delete_many({})


def _drop_test_db() -> None:
    """Drop the test database using a synchronous pymongo client.

    Using a sync client avoids any asyncio event-loop binding issues.
    """
    sync_client = pymongo.MongoClient(TEST_MONGO_URI)
    sync_client.drop_database(TEST_MONGO_DB)
    sync_client.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _initialized_app():
    """Initialise the app (and Beanie) exactly once for the whole test session.

    Re-running the ASGI lifespan per test was the dominant cost of the suite:
    `init_beanie` recreates indexes for every collection on each call. Everything
    shares one session-scoped event loop (see the asyncio settings in
    pyproject.toml) so the AsyncMongoClient created here stays valid for all
    tests — the reason this was previously done per-test.
    """
    original_uri = settings.mongo_settings.URI
    original_db = settings.mongo_settings.DB
    settings.mongo_settings.URI = TEST_MONGO_URI
    settings.mongo_settings.DB = TEST_MONGO_DB
    container.database_client.reset_override()

    _drop_test_db()

    worker_database = bool(XDIST_WORKER) and _postgres_configured()
    if worker_database:
        await _create_worker_database()
    if _postgres_configured():
        # Alembic drives its own event loop; keep it off the session loop.
        await asyncio.to_thread(_alembic_upgrade_head)
    elif container.flags().requires_postgres():
        raise RuntimeError(
            "DB_*/JOBS_* flags require Postgres but DATABASE_URL is unset or does not "
            "point at a database whose name contains 'test'"
        )

    app = get_application(is_test_mode=True)
    async with lifespan(app):
        yield app

    _drop_test_db()
    if worker_database:
        await _drop_worker_database()
    settings.mongo_settings.URI = original_uri
    settings.mongo_settings.DB = original_db
    container.database_client.reset_override()


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def _clean_db(_initialized_app):
    """Reset data before each test without re-initialising Beanie.

    Clearing documents (rather than dropping the database) keeps the indexes and
    collections created by the one-time init, so per-test setup stays cheap.
    """
    await _clear_mongo(container.database_client()[TEST_MONGO_DB])
    if _postgres_configured() and container.flags().requires_postgres():
        await _truncate_postgres()
    yield


@pytest_asyncio.fixture(loop_scope="session")
async def clean_postgres(_initialized_app):
    """For tests that drive the Postgres repositories directly, whatever the flags say."""
    if not _postgres_configured():
        pytest.skip("DATABASE_URL not set to a *_test database")
    await _truncate_postgres()
    yield


@pytest_asyncio.fixture(loop_scope="session")
async def client(_initialized_app):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_initialized_app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.fixture()
async def workspace():
    await workspace_service.create_workspace(testUser)
    workspace = await container.workspace_repo().get_default_workspace_by_owner_id(
        testUser.id
    )
    await container.workspace_user_repo().save(
        WorkspaceUserDocument(
            workspace_id=workspace.id,
            user_id=invited_user.id,
            roles=[WorkspaceRoles.COLLABORATOR],
        )
    )
    return workspace


@pytest.fixture()
async def workspace_1():
    await workspace_service.create_workspace(testUser)
    await workspace_service.create_workspace(testUser1)
    return await container.workspace_repo().get_default_workspace_by_owner_id(
        testUser1.id
    )


@pytest.fixture()
async def workspace_pro():
    await container.workspace_service().create_non_default_workspace(
        title="Title", description="description", workspace_name="name", user=proUser
    )
    return await container.workspace_repo().find_by_name("name")


@pytest.fixture()
async def workspace_form(workspace: Coroutine[Any, Any, WorkspaceDocument]):
    form = await container.workspace_form_service().create_form(
        workspace.id, StandardForm(**formData), testUser
    )
    return form


@pytest.fixture()
async def workspace_form_1(workspace_1: Coroutine[Any, Any, WorkspaceDocument]):
    form = await container.workspace_form_service().create_form(
        workspace_1.id, StandardForm(**formData), testUser1
    )
    return form


@pytest.fixture()
async def published_form(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    published_form = await container.workspace_form_service().publish_form(
        workspace.id, workspace_form.form_id, testUser
    )
    return published_form


@pytest.fixture()
async def published_form_1(
    workspace_1: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form_1: Coroutine[Any, Any, FormDocument],
):
    published_form_1 = await container.workspace_form_service().publish_form(
        workspace_1.id, workspace_form_1.form_id, testUser1
    )
    return published_form_1


@pytest.fixture()
async def workspace_form_response(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[
        Any, Any, FormDocument
    ],  # workspace_form -> published_form
):
    form_response = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponse(**formResponse),
        testUser,
    )
    return dict(form_response)


@pytest.fixture()
async def workspace_form_response_for_test(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    form_response = await container.form_response_service().submit_form_response(
        workspace_form.form_id, StandardFormResponse(**formResponse), workspace.id
    )
    return dict(form_response)


@pytest.fixture()
async def workspace_form_response_1(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    published_form: Coroutine[
        Any, Any, FormDocument
    ],  # workspace_form -> published_form
):
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        published_form.form_id,
        StandardFormResponse(**formResponse),
        testUser1,
    )
    return dict(response)


@pytest.fixture()
async def workspace_form_response_test_1(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    # standard_form_response = StandardFormResponse(**formResponse)
    response = await container.form_response_service().submit_form_response(
        workspace_form.form_id, StandardFormResponse(**formResponse), workspace.id
    )
    return dict(response)


@pytest.fixture()
async def workspace_form_response_2(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    response = await container.workspace_form_service().submit_response(
        workspace.id,
        workspace_form.form_id,
        StandardFormResponse(**formResponse),
        testUser2,
    )
    return dict(response)


@pytest.fixture()
async def workspace_group(
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    workspace_form: Coroutine[Any, Any, FormDocument],
):
    group = await container.responder_groups_service().create_group(
        workspace.id,
        "Testing_Group",
        "testing_group@gmail.com",
        testUser,
        workspace_form.form_id,
        "testing_Description",
        "@gmail.com",
    )
    return group


@pytest.fixture()
def test_user_cookies():
    token = access_token(testUser)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def test_user_cookies_1():
    token = access_token(testUser1)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def test_pro_user_cookies():
    token = access_token(proUser)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def test_invited_user_cookies():
    token = access_token(invited_user)
    return {"Authorization": token, "RefreshToken": token}


@pytest.fixture()
def mock_aiohttp_get_request():
    async def mock_get(*args, **kwargs):
        class MockResponse:
            async def json(self):
                return user_info

        return MockResponse()

    yield patch("aiohttp.ClientSession.get", side_effect=mock_get)


@pytest.fixture()
def mock_aiohttp_post_request(
    workspace_form: Coroutine[Any, Any, FormDocument],
    workspace_form_response: Coroutine[Any, Any, dict],
):
    async def mock_post(*args, **kwargs):
        return {"form": formData_test, "responses": [formResponse]}
        # responses = StandardFormResponse(**formData_test)
        # form = StandardForm(**dict(workspace_form))
        # return FormImportResponse(form=form, responses=[responses])

    yield patch(
        "backend.app.services.workspace_form_service.WorkspaceFormService.convert_form",
        side_effect=mock_post,
    )


@pytest.fixture()
def mock_aiohttp_post_request_for_pro(
    workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
):
    async def mock_post(*args, **kwargs):
        form = await container.workspace_form_service().create_form(
            workspace_pro.id, StandardForm(**formData), proUser
        )
        return FormImportResponse(
            form=StandardForm(**form.model_dump()),
            responses=[StandardFormResponse(**formResponse)],
        )

    yield patch(
        "backend.app.services.workspace_form_service.WorkspaceFormService.convert_form",
        side_effect=mock_post,
    )


@pytest.fixture()
def mock_send_otp_get_request():
    yield patch(
        "backend.app.services.workspace_service.WorkspaceService.send_otp_for_workspace",
        return_value={"message": "Otp sent successfully"},
    )


@pytest.fixture()
def mock_validate_otp():
    async def get_user_after_validation_of_otp(*args, **kwargs):
        return {"user": testUser.model_dump()}

    yield patch(
        "common.services.http_client.HttpClient.get",
        side_effect=get_user_after_validation_of_otp,
    )


@pytest.fixture()
def mock_get_user_info():
    async def get_user_info_from_ids(*args, **kwargs):
        return user_info

    return patch(
        "common.services.http_client.HttpClient.get",
        side_effect=get_user_info_from_ids,
    )


@pytest.fixture()
def mock_create_invitation_request():
    async def send_email_for_invitation(*args, **kwargs):
        return {"data": "Mail sent successfully!!"}

    return patch(
        "common.services.http_client.HttpClient.get",
        side_effect=send_email_for_invitation,
    )


@pytest.fixture()
def mock_get_workspace_by_query():
    async def get_workspace_by_query(*args, **kwargs):
        return {"workspace_owner": proUser.model_dump()}

    return patch(
        "common.services.http_client.HttpClient.get",
        side_effect=get_workspace_by_query,
    )


@pytest.fixture(autouse=True)
def no_silent_mirror_failures(request):
    """In a mirrored mode (dual / postgres_primary_dual) a failing mirror write
    is swallowed by design: the request still succeeds and the outbox records
    it. In tests that silence would hide a store that can't take a write, so
    any mirror failure fails the test. Tests that exercise failures on purpose
    mark themselves with @pytest.mark.allow_mirror_failures."""
    metrics = container.routing_metrics()
    before = dict(metrics.mirror_failures)
    yield
    if request.node.get_closest_marker("allow_mirror_failures"):
        return
    new = {
        key: count - before.get(key, 0)
        for key, count in metrics.mirror_failures.items()
        if count > before.get(key, 0)
    }
    assert not new, f"mirror writes failed (group, method): {new}"
