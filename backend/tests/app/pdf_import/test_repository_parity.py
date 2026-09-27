"""The Postgres twin of the import repository behaves like the Mongo original.
Skipped unless DATABASE_URL points at a *_test database."""

import datetime as dt

import pytest
from beanie import PydanticObjectId

from backend.app.container import container
from backend.app.repositories.form_import_repository import FormImportRepository
from backend.app.repositories.postgres.forms import PostgresFormImportRepository
from backend.app.schemas.form_import import (
    FormImportDocument,
    ImportStatus,
    PageAnalysis,
)
from tests.app.repositories.test_refdata_parity import parity

pytestmark = pytest.mark.asyncio


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()


def record(ws, form_id, status, minutes_ago=0):
    created = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=minutes_ago)
    return FormImportDocument(
        id=PydanticObjectId(),
        workspace_id=ws,
        form_id=form_id,
        created_by="u1",
        status=status,
        file_name=f"{form_id}.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        source_key=f"private/{ws}/{form_id}/imports/x/source.pdf",
        page_count=1,
        pages=[PageAnalysis(number=1, width=595, height=842, route="text")],
        created_at=created,
        updated_at=created,
    )


async def test_form_imports(sessions):
    ws, other = PydanticObjectId(), PydanticObjectId()
    old = record(ws, "f-old", ImportStatus.COMPLETED, minutes_ago=60 * 30)
    recent = record(ws, "f-recent", ImportStatus.RUNNING, minutes_ago=5)
    queued = record(ws, "f-queued", ImportStatus.QUEUED, minutes_ago=1)
    elsewhere = record(other, "f-else", ImportStatus.RUNNING)
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    await parity(
        FormImportRepository(),
        PostgresFormImportRepository(sessions),
        [
            ("save", lambda: (old,)),
            ("save", lambda: (recent,)),
            ("save", lambda: (queued,)),
            ("save", lambda: (elsewhere,)),
            ("get", lambda: (recent.id,)),
            ("get", lambda: (PydanticObjectId(),)),
            ("list_by_workspace", lambda: (ws,)),
            ("count_active", lambda: (ws,)),
            ("delete_by_form_ids", lambda: (["f-queued", "f-missing"],)),
            ("count_active", lambda: (ws,)),
            ("list_by_workspace", lambda: (ws, 1)),
        ],
    )
    # the daily window counts by creation time in both stores
    assert await FormImportRepository().count_created_since(ws, since) == 1
    assert (
        await PostgresFormImportRepository(sessions).count_created_since(ws, since) == 1
    )
