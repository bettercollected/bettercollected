"""The record codec (common/common/records) against the backend's golden fixture.

Every backend document class mirrored to Postgres, in every pinned variant:
the record codec encodes the Beanie instances to the pinned bytes, the same
classes rebased onto ``Record`` build and decode to the pinned bytes, and
the rebased classes serialise and describe themselves (JSON schema) exactly
as the Beanie ones. See common/common/records/golden.py.
"""

from backend.app.handlers.database import document_models
from common.db import from_row_doc
from common.db.codec_golden import build_cases, check
from common.records import golden

from tests.app.db.test_codec_golden import FIXTURE, OVERRIDES, _documents


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
    classes = {cls.__name__: golden.twin(cls) for cls in document_models}
    assert golden.check_round_trip(FIXTURE, classes) == []


def test_records_look_the_same_on_the_wire(_initialized_app):
    classes = {cls.__name__: cls for cls in _classes().values()}
    assert golden.check_wire(FIXTURE, classes, from_row_doc) == []
