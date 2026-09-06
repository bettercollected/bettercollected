"""Beanie document <-> Postgres row values, the shared shape every Postgres repository uses.

A Postgres repository speaks the same language as its Mongo twin: it accepts and
returns the Beanie ``Document`` classes the services already use. This module is
the only place that knows how a document becomes a row (and back):

* :func:`to_bson_dict` encodes exactly as ``Document.save()`` would - through
  Beanie's ``Encoder`` with the document's own ``bson_encoders`` - so the
  ``doc`` a Postgres row stores is byte-for-byte what Mongo would have stored,
  and :func:`common.db.canonical.document_checksum` agrees across both stores.
* :func:`row_values` produces the column values for an upsert (``id``, ``doc``,
  timestamps, source and checksum).
* :func:`from_row_doc` rebuilds the document from a row's ``doc``.

Documents can only be instantiated while Beanie is initialised (its
``Document.__init__`` asks for the collection); that holds for the whole
dual-run period. Removing Mongo (R3) turns these classes into plain pydantic
models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Type, TypeVar

from beanie import Document, PydanticObjectId
from beanie.odm.utils.encoder import Encoder

from common.db.base import SOURCE_APP
from common.db.canonical import canonical_document, checksum, from_canonical_document

D = TypeVar("D", bound=Document)


def ensure_id(document: Document) -> Document:
    """Beanie assigns ``_id`` client-side on insert; do the same before an upsert."""
    if document.id is None:
        document.id = PydanticObjectId()
    return document


def to_bson_dict(document: Document) -> dict[str, Any]:
    encoders = type(document).get_settings().bson_encoders
    return Encoder(custom_encoders=encoders).encode(document)


def _timestamp(value: Any) -> Optional[datetime]:
    """created_at/updated_at as stored: a datetime, or the ISO string bson_encoders produce."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def row_values(document: Document, *, source: str = SOURCE_APP) -> dict[str, Any]:
    """Column values for upserting ``document`` into its table."""
    ensure_id(document)
    bson = to_bson_dict(document)
    doc = canonical_document(bson)
    now = datetime.now(timezone.utc)
    return {
        "id": str(document.id),
        "doc": doc,
        "created_at": _timestamp(bson.get("created_at")) or now,
        "updated_at": _timestamp(bson.get("updated_at")) or now,
        "bc_source": source,
        "bc_checksum": checksum(doc),
    }


def from_row_doc(document_cls: Type[D], doc: Mapping[str, Any]) -> D:
    return document_cls.model_validate(from_canonical_document(doc))
