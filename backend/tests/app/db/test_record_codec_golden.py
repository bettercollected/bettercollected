"""The record codec (common/common/records) against the backend's golden fixture.

Every backend document class mirrored to Postgres, in every pinned variant:
the record codec encodes the Beanie instances to the pinned bytes, the same
classes rebased onto ``Record`` build and decode to the pinned bytes, and
the rebased classes serialise and describe themselves (JSON schema) exactly
as the Beanie ones. See common/common/records/golden.py.
"""

from common.db.beanie_bridge import from_row_doc
from common.db.codec_golden import build_cases, check
from common.records import golden

from tests.app.db.beanie_originals import ORIGINALS
from tests.app.db.test_codec_golden import (
    FIXTURE,
    OVERRIDES,
    RECORD_CLASSES,
    _documents,
    _models,
)


def _classes():
    return {c: cls for c, cls in _documents().items() if cls is not None}


def test_record_codec_encodes_the_documents_to_the_pinned_bytes(_initialized_app):
    cases = build_cases(_classes(), OVERRIDES)
    assert golden.check_encoding(FIXTURE, cases) == []


def test_records_build_to_the_pinned_bytes(_initialized_app):
    cases = build_cases(golden.twins(_classes()), OVERRIDES)
    # the current codec agrees with the record codec on the records, too
    assert check(FIXTURE, cases) == []
    assert golden.check_encoding(FIXTURE, cases) == []


def test_pinned_docs_decode_into_records_and_encode_back(_initialized_app):
    classes = {cls.__name__: golden.twin(cls) for cls in _models()}
    assert golden.check_round_trip(FIXTURE, classes) == []


def test_records_look_the_same_on_the_wire(_initialized_app):
    classes = {cls.__name__: cls for cls in _classes().values()}
    assert golden.check_wire(FIXTURE, classes, from_row_doc) == []


def test_moved_records_look_like_their_beanie_originals(_initialized_app):
    """The groups served from Postgres only: their ``Record`` classes describe
    and serialise every pinned document exactly as the Beanie classes did
    before the move (frozen in beanie_originals.py)."""
    originals = {cls.__name__: cls for cls in ORIGINALS}
    records = {cls.__name__: cls for cls in RECORD_CLASSES}
    assert set(originals) == set(records)
    assert golden.check_wire(FIXTURE, originals, from_row_doc, records) == []
