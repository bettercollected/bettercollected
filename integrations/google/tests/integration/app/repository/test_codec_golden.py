"""Golden fixtures of the ``doc`` codec for every google document mirrored to Postgres.

See common/common/db/codec_golden.py. The fixture is regenerated only on
purpose: ``scripts/regenerate-codec-golden.sh``. Beanie needs a reachable
Mongo (MONGO_URI) to initialise; nothing is written to it.
"""

from pathlib import Path

import pytest
import pytest_asyncio

import googleform.app.schemas.google_form  # noqa: F401 — registers the classes
import googleform.app.schemas.google_form_response  # noqa: F401
import googleform.app.schemas.oauth_credential  # noqa: F401
import googleform.db.models  # noqa: F401 — registers the rows on the metadata
from common.db import BaseRow
from common.db.codec_golden import (
    build_cases,
    check,
    check_round_trip,
    mirrored_documents,
)
from googleform.app.services import database_service
from googleform.db.base import Base

pytestmark = pytest.mark.asyncio

FIXTURE = Path(__file__).parents[3] / "fixtures" / "codec_golden" / "google.json"


@pytest_asyncio.fixture
async def documents():
    await database_service.init_db()
    rows = [m.class_ for m in Base.registry.mappers if issubclass(m.class_, BaseRow)]
    yield mirrored_documents(rows, database_service.document_models)
    await database_service.close_db()


async def test_every_mirrored_table_has_a_document_class(documents):
    assert sorted(c for c, cls in documents.items() if cls is None) == []


async def test_encoding_matches_the_pinned_bytes(documents):
    assert check(FIXTURE, build_cases(documents)) == []


async def test_decode_then_encode_gives_the_pinned_bytes(documents):
    classes = {cls.__name__: cls for cls in documents.values()}
    assert check_round_trip(FIXTURE, classes) == []
