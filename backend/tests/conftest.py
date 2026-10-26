import asyncio
from pathlib import Path
import os
import re
import secrets
import time
from typing import Any, Coroutine
from unittest.mock import patch

from dotenv import load_dotenv

# The respondent identity key (RESPONDENT_IDENTITY_KEY) is a deployment secret
# and never in the repository: a run without one gets a throwaway key.
os.environ.setdefault("RESPONDENT_IDENTITY_KEY", secrets.token_hex(32))

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
from common.db.beanie_bridge import offline_client
from common.models.form_import import FormImportResponse
from common.models.standard_form import StandardForm, StandardFormResponse

from tests.app.auth_helpers import access_token
from backend.app import get_application
from backend.app import asgi as _asgi
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

# The API converts stored respondent identities in a background task after it
# starts. The session app does not: tests that exercise the pass call it
# themselves, and a pass running in the background would hold its advisory lock.
_asgi.start_background_passes = lambda engine: None

TEST_MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost")
TEST_MONGO_DB = os.getenv("MONGO_TEST_DB", "bettercollected_test")


#: Whether this session set the 4.0 Beanie classes up on the test Mongo (set at
#: session start): when a selected test drives Mongo itself (marker ``mongo``:
#: the import from 4.0). Otherwise the suite neither creates, clears nor drops
#: a Mongo database, and the classes are set up offline. The application itself
#: never connects to Mongo.
_MONGO = {"connected": False, "client": None}


def mongo_database():
    """The test Mongo database, as the 4.0 Beanie classes see it (only in a
    session with ``mongo`` tests)."""
    return _MONGO["client"][TEST_MONGO_DB]


ALL = "*"
#: Tests that drive a Mongo server themselves: the import from 4.0 (the
#: migration CLI), the store-wide operator tasks and scripts.
#: They get the ``mongo`` marker. CI runs the Postgres mode without Mongo and
#: ``-m "not mongo"``, and these in a job of their own with Mongo (docs/ci.md).
#: A test missing here fails there on the unreachable Mongo: add it (the whole
#: file, or its test functions by name).
MONGO_DRIVEN = {
    "tests/app/db/test_outbox.py": ALL,
    "tests/app/migrate/test_deletion_tombstones.py": ALL,
    "tests/app/migrate/test_engine.py": ALL,
    "tests/app/migrate/test_reconcile_interleaved.py": ALL,
    "tests/app/migrate/test_marker.py": ALL,
    "tests/app/migrate/test_mirror_order.py": ALL,
    "tests/app/migrate/test_mirror_verify.py": ALL,
    "tests/app/migrate/test_verify_agrees_with_reconcile.py": ALL,
    "tests/app/migrate/test_resolve_outbox.py": ALL,
    "tests/app/services/test_case_duplicates_forms_import.py": {
        "test_the_plan_and_drops_wait_for_a_complete_forms_import",
        "test_a_link_deleted_after_a_finished_import_does_not_block",
        "test_a_link_written_to_mongo_after_a_finished_backfill_refuses",
        "test_a_backfill_that_skipped_documents_falls_back_to_the_links",
        "test_a_settled_backfill_reads_no_links",
    },
}


def _mongo_driven(nodeid: str) -> bool:
    path, _, rest = nodeid.partition("::")
    names = MONGO_DRIVEN.get(path)
    if names is None:
        return False
    return names == ALL or rest.split("::")[-1].split("[")[0] in names


def pytest_collection_modifyitems(config, items):
    for item in items:
        if _mongo_driven(item.nodeid):
            item.add_marker(pytest.mark.mongo)


TEST_DATABASE_URL = os.getenv("DATABASE_URL", "")
if not XDIST_WORKER:
    BASE_DATABASE_URL = TEST_DATABASE_URL


def _database_name(url: str) -> str:
    return url.rsplit("/", 1)[-1].split("?")[0]


_TEST_NAME = re.compile(r"(^|_)test($|_)")


def _is_test_database(name: str) -> bool:
    """``test`` as a whole word of the name (``bettercollected_test``,
    ``x_test_gw0``); ``latest`` or ``contest_prod`` are not test databases."""
    return bool(_TEST_NAME.search(name))


def _postgres_configured() -> bool:
    """A Postgres test database is available. Guarded: only databases with
    ``test`` as a word of their name are ever created, migrated, truncated or
    dropped by the suite. Under xdist the configured name must pass; the worker's
    adds a suffix."""
    if not TEST_DATABASE_URL:
        return False
    return _is_test_database(_database_name(BASE_DATABASE_URL)) and _is_test_database(
        _database_name(TEST_DATABASE_URL)
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


async def _apply_jobs_schema() -> None:
    """procrastinate's queue tables in the ``jobs`` schema: the job queue is on
    Postgres by default (``JOBS_BACKEND``), so a start with the default flags
    checks for them (what ``python -m backend.jobs.schema`` does at deploy)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from backend.jobs.schema import apply_schema

    engine = create_async_engine(
        TEST_DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS jobs"))
    finally:
        await engine.dispose()
    await apply_schema(TEST_DATABASE_URL)


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
async def _initialized_app(request):
    """Initialise the app exactly once for the whole test session.

    Re-running the ASGI lifespan per test was the dominant cost of the suite.
    Everything shares one session-scoped event loop (see the asyncio settings
    in pyproject.toml). The application itself never connects to Mongo; when a
    ``mongo`` test is selected the 4.0 Beanie classes are set up on the test
    Mongo as well (tests/app/db/beanie_originals.py), else offline.
    """
    from tests.app.db.beanie_originals import init_originals

    original_uri = settings.mongo_settings.URI
    original_db = settings.mongo_settings.DB
    settings.mongo_settings.URI = TEST_MONGO_URI
    settings.mongo_settings.DB = TEST_MONGO_DB

    _MONGO["connected"] = any(
        item.get_closest_marker("mongo") for item in request.session.items
    )
    if _MONGO["connected"]:
        _drop_test_db()

    worker_database = bool(XDIST_WORKER) and _postgres_configured()
    if worker_database:
        await _create_worker_database()
    if not _postgres_configured():
        raise RuntimeError(
            "Postgres is the only store but DATABASE_URL is unset or does not "
            "point at a database whose name contains 'test'"
        )
    # Alembic drives its own event loop; keep it off the session loop.
    await asyncio.to_thread(_alembic_upgrade_head)
    await _apply_jobs_schema()
    # A database kept from an earlier run holds that run's respondent identity
    # key check (its key was a throwaway): the start would refuse this run's key.
    await _truncate_postgres()

    if _MONGO["connected"]:
        _MONGO["client"] = pymongo.AsyncMongoClient(TEST_MONGO_URI)
        await init_originals(_MONGO["client"][TEST_MONGO_DB], required=True)
    else:
        await init_originals(offline_client()[TEST_MONGO_DB], required=False)
    app = get_application(is_test_mode=True)
    async with lifespan(app):
        yield app

    if _MONGO["connected"]:
        await _MONGO["client"].close()
        _MONGO["client"] = None
        _drop_test_db()
    if worker_database:
        await _drop_worker_database()
    settings.mongo_settings.URI = original_uri
    settings.mongo_settings.DB = original_db


@pytest.fixture(autouse=True)
def _respondent_identity_state():
    """The process-level key state (verified / known mismatch) is what the app's
    start left; a test that changes it must not leak that into the next."""
    from backend.app.utils import respondent_identity as ri

    mismatch, verified = list(ri._key_mismatch_seen), list(ri._key_verified)
    yield
    ri._key_mismatch_seen[:] = mismatch
    ri._key_verified[:] = verified


@pytest_asyncio.fixture(autouse=True, loop_scope="session")
async def _clean_db(_initialized_app):
    """Reset data before each test without re-initialising the app.

    Clearing rows (rather than dropping the database) keeps the schema created
    by the one-time init, so per-test setup stays cheap.
    """
    if _MONGO["connected"]:
        await _clear_mongo(mongo_database())
    await _truncate_postgres()
    yield


@pytest.fixture(autouse=True)
def rate_limit_clock(_initialized_app, monkeypatch):
    """The shared rate limiter's clock, held still for the test.

    Its fixed windows (a minute for the AI limits, an hour for the public API,
    a day for the AI budget) are aligned to the epoch. On the real clock, a
    test that fills a window and then expects a refusal fails whenever a
    window boundary passes between the two requests: the refused request
    lands in a fresh window and is let through. Held still, every request of
    a test counts in one window; a test moves time by setting
    ``rate_limit_clock["now"]``.
    """
    clock = {"now": time.time()}
    monkeypatch.setattr(container.rate_limiter(), "_clock", lambda: clock["now"])
    return clock


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


@pytest_asyncio.fixture(loop_scope="session")
async def internal_client(_initialized_app):
    """A client on the backend's internal listener (API_INTERNAL_PORT), as the
    task runner and the workers reach it inside the stack."""
    from backend.app.services.internal_routes import internal_port

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_initialized_app, client=("172.18.0.5", 40000)),
        base_url=f"http://backend:{internal_port()}",
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
