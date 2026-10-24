"""Stored documents without Beanie: the ``Record`` base and its row codec.

Every Python service keeps its data in Postgres rows shaped as an ``id``, a
few typed "spine" columns and the whole document in ``doc`` (JSONB, BSON
Extended JSON) with a checksum. Today the documents are Beanie classes
(``MongoDocument``) and :mod:`common.db.beanie_bridge` turns them into rows.
This package is the Beanie-free replacement the Postgres-only release moves
to; it changes no stored byte and nothing on the wire:

* :class:`common.ids.RecordId` replaces ``PydanticObjectId``;
* :class:`Record` replaces ``MongoDocument`` (fields, stamping, ``Settings``,
  ``verify_doc_exists``; no query methods: all reads and writes go through the
  repositories);
* :mod:`common.records.codec` replaces ``beanie_bridge``: :func:`encode`,
  :func:`decode` and :func:`row_values` produce and read the same ``doc``
  and checksum, proven against the golden fixtures of every mirrored
  document class (``*/tests/fixtures/codec_golden``) and the records ones
  (``common/tests/fixtures/codec_golden/records.json``).

Adopting it, one repository group at a time
-------------------------------------------
For each group (refdata, analytics, ai, actions, google, identity, auth,
forms, responses), in a pull request of its own:

1. **Models.** Change the base of the group's document classes from
   ``MongoDocument`` (or ``BaseDocument``) to ``Record``; drop Beanie's
   ``Indexed(...)`` annotations and ``Settings.indexes`` (Postgres indexes
   live in the migrations); keep ``Settings.name`` and ``Settings.bson_encoders``
   as they are: the encoders define stored bytes. Replace
   ``PydanticObjectId`` with ``RecordId`` in the group's models, DTOs and
   services. ``RecordId`` equals a ``PydanticObjectId`` of the same value,
   so a group can move while its neighbours still use Beanie.
2. **Repositories.** The Postgres twin becomes the repository, built on
   :class:`common.records.repository.RecordRepository`: it encodes
   with :func:`row_values` / :func:`decode` instead of the bridge, calls
   ``record.touch()`` where the Mongo original called ``save()``, and
   ``derived_id`` where it called ``derived_object_id``. The Mongo
   implementation, the ``RoutingRepository`` wrapper and the group's flags go.
3. **Proof.** The group's golden cases still pass unchanged (the fixtures
   are never regenerated for this), and the twin checks in
   :mod:`common.records.golden` pass for the group's classes before the
   switch.

Nothing in this package imports Beanie or ``common.db`` except
:mod:`common.records.repository` (the repository base, built on
``common.db``'s while Beanie groups remain; not imported here); ``bson`` stays
(ObjectId and the Extended JSON encoding) until the Mongo import path is
removed in 5.0.
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
