"""Stored documents without Beanie: the ``Record`` base and its row codec.

Every Python service keeps its data in Postgres rows shaped as an ``id``, a
few typed "spine" columns and the whole document in ``doc`` (JSONB, BSON
Extended JSON) with a checksum. Until 4.1 the documents were Beanie classes
(``MongoDocument``) and ``common.db.beanie_bridge`` turned them into rows;
that module now survives as test support only (the golden fixtures and the
import tests need the 4.0 classes). This package is what replaced it, and
changed no stored byte and nothing on the wire:

* :class:`common.ids.RecordId` replaces ``PydanticObjectId``;
* :class:`Record` replaces ``MongoDocument`` (fields, stamping, ``Settings``,
  ``verify_doc_exists``; no query methods: all reads and writes go through the
  repositories);
* :mod:`common.records.codec` replaces the bridge: :func:`encode`,
  :func:`decode` and :func:`row_values` produce and read the same ``doc``
  and checksum, proven against the golden fixtures of every stored
  document class (``*/tests/fixtures/codec_golden``) and the records ones
  (``common/tests/fixtures/codec_golden/records.json``);
* :class:`common.records.repository.RecordRepository` is the one repository
  base: queries over the spine columns, saves that move ``updated_at`` with
  :meth:`Record.touch`, and deletes that record a tombstone in the same
  transaction (:mod:`common.db.tombstones`, read by the import from 4.0).

A new stored class is a ``Record`` with ``class Settings: name = ...`` (the
collection and table name; ``bson_encoders`` define the stored bytes), a row in
the service's ``db/models.py``, an Alembic revision, and a golden case.

Nothing in this package imports Beanie (:mod:`common.records.golden` does, in
test code only); ``bson`` stays (ObjectId and the Extended JSON encoding) until
the Mongo import path is removed in 5.0.
"""

from common.ids import RecordId, derived_id, is_record_id, new_id
from common.records import canonical
from common.records.base import Record, RecordSettings, settings_of
from common.records.canonical import (
    canonical_document,
    canonical_json,
    checksum,
    from_canonical_document,
)
from common.records.codec import (
    SOURCE_APP,
    decode,
    encode,
    ensure_id,
    row_values,
    to_bson,
)

__all__ = [
    "Record",
    "RecordId",
    "RecordSettings",
    "SOURCE_APP",
    "canonical",
    "canonical_document",
    "canonical_json",
    "checksum",
    "decode",
    "derived_id",
    "encode",
    "ensure_id",
    "from_canonical_document",
    "is_record_id",
    "new_id",
    "row_values",
    "settings_of",
    "to_bson",
]
