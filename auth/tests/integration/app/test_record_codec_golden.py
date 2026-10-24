"""The record codec (common/common/records) against auth's golden fixture.

The record codec encodes the pinned user documents to the pinned bytes, the
class rebased onto ``Record`` builds and decodes to the same bytes, and it
serialises and describes itself (JSON schema) like the Beanie class. See
common/common/records/golden.py.
"""

import pytest

from common.db import from_row_doc
from common.db.codec_golden import build_cases, check
from common.records import golden

from tests.integration.app.test_codec_golden import FIXTURE, documents  # noqa: F401

pytestmark = pytest.mark.asyncio


def _classes(documents):  # noqa: F811
    return {c: cls for c, cls in documents.items() if cls is not None}


async def test_record_codec_encodes_the_documents_to_the_pinned_bytes(
    documents,  # noqa: F811
):
    cases = build_cases(_classes(documents))
    assert golden.check_encoding(FIXTURE, cases) == []


async def test_records_build_to_the_pinned_bytes(documents):  # noqa: F811
    cases = build_cases(golden.twins(_classes(documents)))
    assert check(FIXTURE, cases) == []
    assert golden.check_encoding(FIXTURE, cases) == []


async def test_pinned_docs_decode_into_records_and_encode_back(
    documents,  # noqa: F811
):
    classes = {cls.__name__: golden.twin(cls) for cls in _classes(documents).values()}
    assert golden.check_round_trip(FIXTURE, classes) == []


async def test_records_look_the_same_on_the_wire(documents):  # noqa: F811
    classes = {cls.__name__: cls for cls in _classes(documents).values()}
    assert golden.check_wire(FIXTURE, classes, from_row_doc) == []
