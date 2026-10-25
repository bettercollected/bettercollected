"""The record codec (common/common/records) against auth's golden fixture.

The record codec encodes the pinned user documents to the pinned bytes, the
``Record`` class builds and decodes to the same bytes, and it serialises and
describes itself (JSON schema) exactly like the Beanie class it replaced
(frozen in beanie_originals.py). See common/common/records/golden.py.
"""

import pytest

from common.db import from_row_doc
from common.db.codec_golden import build_cases, check
from common.records import golden

from tests.integration.app.beanie_originals import ORIGINALS, init_originals
from tests.integration.app.test_codec_golden import FIXTURE, RECORD_CLASSES, classes


def test_record_codec_encodes_the_documents_to_the_pinned_bytes():
    assert golden.check_encoding(FIXTURE, build_cases(classes())) == []


def test_records_build_to_the_pinned_bytes():
    cases = build_cases(golden.twins(classes()))
    # the bridge codec agrees with the record codec on the records, too
    assert check(FIXTURE, cases) == []
    assert golden.check_encoding(FIXTURE, cases) == []


def test_pinned_docs_decode_into_records_and_encode_back():
    records = {cls.__name__: golden.twin(cls) for cls in RECORD_CLASSES}
    assert golden.check_round_trip(FIXTURE, records) == []


def test_records_look_the_same_on_the_wire():
    records = {cls.__name__: cls for cls in RECORD_CLASSES}
    assert golden.check_wire(FIXTURE, records, from_row_doc) == []


@pytest.mark.asyncio
async def test_the_record_looks_like_its_beanie_original():
    """``UserDocument`` describes and serialises every pinned document exactly
    as the Beanie class did before 4.1."""
    await init_originals()
    originals = {cls.__name__: cls for cls in ORIGINALS}
    records = {cls.__name__: cls for cls in RECORD_CLASSES}
    assert set(originals) == set(records)
    assert golden.check_wire(FIXTURE, originals, from_row_doc, records) == []
