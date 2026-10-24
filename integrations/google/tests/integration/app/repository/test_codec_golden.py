"""Golden fixtures of the ``doc`` codec for every google document mirrored to Postgres.

See common/common/db/codec_golden.py. The fixture is regenerated only on
purpose: ``scripts/regenerate-codec-golden.sh``. Beanie is set up without a
server (``init_db(required=False)``); no Mongo is needed.
"""

from pathlib import Path

import pytest
import pytest_asyncio

import googleform.app.schemas.oauth_credential  # noqa: F401 — registers the class
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

# Tables kept (expand-only) whose document classes and code were removed.
NO_DOCUMENT_CLASS = ["GoogleFormDocument", "GoogleFormResponseDocument"]


@pytest_asyncio.fixture
async def documents():
    # the codecs need the document classes set up, not a server
    await database_service.init_db(required=False)
    rows = [m.class_ for m in Base.registry.mappers if issubclass(m.class_, BaseRow)]
    yield mirrored_documents(rows, database_service.document_models)
    await database_service.close_db()


async def test_every_mirrored_table_has_a_document_class_or_is_listed(documents):
    assert sorted(c for c, cls in documents.items() if cls is None) == NO_DOCUMENT_CLASS


async def test_encoding_matches_the_pinned_bytes(documents):
    documents = {c: cls for c, cls in documents.items() if cls is not None}
    assert check(FIXTURE, build_cases(documents)) == []


async def test_decode_then_encode_gives_the_pinned_bytes(documents):
    classes = {cls.__name__: cls for cls in documents.values() if cls is not None}
    assert check_round_trip(FIXTURE, classes) == []
