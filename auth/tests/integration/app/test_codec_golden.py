"""Golden fixtures of the ``doc`` codec for every auth document mirrored to Postgres.

See common/common/db/codec_golden.py. The fixture is regenerated only on
purpose: ``scripts/regenerate-codec-golden.sh``.
"""

from pathlib import Path

import pytest
import pytest_asyncio
from mongomock_motor import AsyncMongoMockClient

import auth.app.schemas.user  # noqa: F401 — registers the document classes
import auth.db.models  # noqa: F401 — registers the rows on the metadata
from auth.app.services.database_service import document_models, init_db
from auth.db.base import Base
from common.db import BaseRow
from common.db.codec_golden import (
    build_cases,
    check,
    check_round_trip,
    mirrored_documents,
)

pytestmark = pytest.mark.asyncio

FIXTURE = Path(__file__).parents[2] / "fixtures" / "codec_golden" / "auth.json"

# Tables kept (expand-only) whose document class and code were removed.
NO_DOCUMENT_CLASS = ["Provider"]


@pytest_asyncio.fixture
async def documents():
    await init_db(AsyncMongoMockClient())
    rows = [m.class_ for m in Base.registry.mappers if issubclass(m.class_, BaseRow)]
    return mirrored_documents(rows, document_models)


async def test_every_mirrored_table_has_a_document_class_or_is_listed(documents):
    assert sorted(c for c, cls in documents.items() if cls is None) == NO_DOCUMENT_CLASS


async def test_encoding_matches_the_pinned_bytes(documents):
    documents = {c: cls for c, cls in documents.items() if cls is not None}
    assert check(FIXTURE, build_cases(documents)) == []


async def test_decode_then_encode_gives_the_pinned_bytes(documents):
    classes = {cls.__name__: cls for cls in documents.values() if cls is not None}
    assert check_round_trip(FIXTURE, classes) == []
