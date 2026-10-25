"""Golden fixtures of the ``doc`` codec for every auth table.

See common/common/db/codec_golden.py. The fixture is regenerated only on
purpose: ``scripts/regenerate-codec-golden.sh``.
"""

from pathlib import Path

import auth.db.models  # noqa: F401 — registers the rows on the metadata
from auth.app.schemas.user import UserDocument
from auth.db.base import Base
from common.db import BaseRow
from common.db.codec_golden import (
    build_cases,
    check,
    check_round_trip,
    mirrored_documents,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "codec_golden" / "auth.json"

#: The stored document classes (``Record`` since 4.1).
RECORD_CLASSES = (UserDocument,)

# Tables kept (expand-only) whose document class and code were removed.
NO_DOCUMENT_CLASS = ["Provider"]


def documents():
    rows = [m.class_ for m in Base.registry.mappers if issubclass(m.class_, BaseRow)]
    return mirrored_documents(rows, RECORD_CLASSES)


def classes():
    return {c: cls for c, cls in documents().items() if cls is not None}


def test_every_mirrored_table_has_a_document_class_or_is_listed():
    assert (
        sorted(c for c, cls in documents().items() if cls is None) == NO_DOCUMENT_CLASS
    )


def test_encoding_matches_the_pinned_bytes():
    assert check(FIXTURE, build_cases(classes())) == []


def test_decode_then_encode_gives_the_pinned_bytes():
    assert check_round_trip(FIXTURE, {c.__name__: c for c in RECORD_CLASSES}) == []
