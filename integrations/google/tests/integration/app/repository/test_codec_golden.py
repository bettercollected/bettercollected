"""Golden fixtures of the ``doc`` codec for every google document mirrored to Postgres.

See common/common/db/codec_golden.py. The fixture is regenerated only on
purpose: ``scripts/regenerate-codec-golden.sh``. The document is a ``Record``:
no Beanie, no server.
"""

from pathlib import Path

import googleform.db.models  # noqa: F401 — registers the rows on the metadata
from common.db import BaseRow
from common.db.codec_golden import (
    build_cases,
    check,
    check_round_trip,
    mirrored_documents,
)
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.db.base import Base

FIXTURE = Path(__file__).parents[3] / "fixtures" / "codec_golden" / "google.json"

#: The stored document classes (``Record`` since 4.1).
RECORD_CLASSES = (Oauth2CredentialDocument,)

# Tables kept (expand-only) whose document classes and code were removed.
NO_DOCUMENT_CLASS = ["GoogleFormDocument", "GoogleFormResponseDocument"]


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
