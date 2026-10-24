"""Record <-> Postgres row: the ``doc`` codec, without Beanie.

A row stores its document in ``doc`` as BSON Extended JSON (relaxed) with a
checksum in ``_bc_checksum``; verification compares those checksums, and
every row already written was encoded by Beanie (``Document.save()`` on the
Mongo side, :mod:`common.db.beanie_bridge` on the Postgres side). This codec
must therefore produce the same bytes for the same document. It does so by
following Beanie's ``Encoder`` (beanie 2.x, ``beanie/odm/utils/encoder.py``)
rule for rule, in the same order:

1. the class's ``Settings.bson_encoders`` (exact type first, then the first
   ``isinstance`` match in declaration order) — today's documents turn
   ``datetime``/``date``/``time`` into ISO strings this way;
2. BSON scalars as they are (``None``, ``str``, ``int``/``bool``, ``float``,
   ``datetime``, ``ObjectId`` (a :class:`~common.ids.RecordId` included), ...);
3. the default encoders: enum -> value, ``bytes`` -> Binary, ``Decimal`` ->
   Decimal128, ``UUID`` -> Binary (subtype 4), ``date`` -> midnight datetime,
   ``timedelta`` -> seconds, secrets, URLs, paths and IP types -> ``str``;
4. a nested :class:`~common.records.base.Record` (or Beanie document) with
   its own encoders; other pydantic models field by field under their aliases, ``exclude=True``
   fields left out, ``None`` kept; mappings with ``str`` keys (enum keys
   as they are); any other iterable (list, tuple, set) as a list.

Beanie features no stored document uses (links, union documents,
inheritance class ids, revision ids) are not reproduced.

The functions accept any pydantic model with the document shape, so a
Beanie document encodes to the same bytes here too; the golden tests rely on
that to compare the two codecs on every pinned case.
"""

from __future__ import annotations

import datetime
import decimal
import enum
import ipaddress
import operator
import pathlib
import re
import sys
import uuid
from collections.abc import Iterable, Mapping
from datetime import timezone
from typing import Any, Callable, Dict, Iterator, Optional, Tuple, Type, TypeVar

import bson
import pydantic
from pydantic import AnyUrl, BaseModel, RootModel
from pydantic_core import Url

from common.ids import RecordId
from common.records.base import Record, settings_of
from common.records.canonical import (
    canonical_document,
    checksum,
    from_canonical_document,
)

M = TypeVar("M", bound=BaseModel)

#: ``_bc_source`` of rows the application writes (``common.db.base.SOURCE_APP``).
SOURCE_APP = "app"

Encoders = Mapping[Any, Callable[[Any], Any]]

# Beanie's DEFAULT_CUSTOM_ENCODERS, same entries in the same order (its ``Link``
# entry aside: no stored document holds a link).
DEFAULT_ENCODERS: Dict[type, Callable[[Any], Any]] = {
    ipaddress.IPv4Address: str,
    ipaddress.IPv4Interface: str,
    ipaddress.IPv4Network: str,
    ipaddress.IPv6Address: str,
    ipaddress.IPv6Interface: str,
    ipaddress.IPv6Network: str,
    pathlib.PurePath: str,
    pydantic.SecretBytes: pydantic.SecretBytes.get_secret_value,
    pydantic.SecretStr: pydantic.SecretStr.get_secret_value,
    datetime.date: lambda d: datetime.datetime.combine(d, datetime.time.min),
    datetime.timedelta: operator.methodcaller("total_seconds"),
    enum.Enum: operator.attrgetter("value"),
    bytes: bson.Binary,
    decimal.Decimal: bson.Decimal128,
    uuid.UUID: bson.Binary.from_uuid,
    re.Pattern: bson.Regex.from_native,
    Url: str,
    AnyUrl: str,
}

BSON_SCALAR_TYPES = (
    type(None),
    str,
    int,
    float,
    datetime.datetime,
    bson.Binary,
    bson.DBRef,
    bson.Decimal128,
    bson.MaxKey,
    bson.MinKey,
    bson.ObjectId,
    bson.Regex,
)


def _encoder_for(value: Any, encoders: Encoders) -> Optional[Callable[[Any], Any]]:
    found = encoders.get(type(value))
    if found is not None:
        return found
    for cls, encoder in encoders.items():
        if isinstance(value, cls):
            return encoder
    return None


def _model_items(model: BaseModel) -> Iterator[Tuple[str, Any]]:
    """(stored key, value) of every field and extra, ``exclude=True`` fields skipped."""
    fields = type(model).model_fields
    for key, value in model.__iter__():
        info = fields.get(key)
        if info is not None:
            key = info.alias or key
            if info.exclude is True:
                continue
        yield key, value


def _is_record(value: Any) -> bool:
    """A record (or, while both exist, a Beanie document) nested in another:
    encoded with its own ``bson_encoders``, as Beanie encodes a nested document.
    Beanie is only consulted when something else already imported it."""
    if isinstance(value, Record):
        return True
    beanie = sys.modules.get("beanie")
    return beanie is not None and isinstance(value, beanie.Document)


class _Encoder:
    def __init__(self, encoders: Encoders) -> None:
        self.encoders = encoders

    def encode(self, value: Any) -> Any:
        if self.encoders:
            encoder = _encoder_for(value, self.encoders)
            if encoder is not None:
                return encoder(value)
        if isinstance(value, BSON_SCALAR_TYPES):
            return value
        encoder = _encoder_for(value, DEFAULT_ENCODERS)
        if encoder is not None:
            return encoder(value)
        if _is_record(value):
            return to_bson(value)
        if isinstance(value, RootModel):
            return self.encode(value.root)
        if isinstance(value, BaseModel):
            return {key: self.encode(item) for key, item in _model_items(value)}
        if isinstance(value, Mapping):
            return {
                key if isinstance(key, enum.Enum) else str(key): self.encode(item)
                for key, item in value.items()
            }
        if isinstance(value, Iterable):
            return [self.encode(item) for item in value]
        raise ValueError(f"Cannot encode {value!r}")


def to_bson(record: BaseModel) -> Dict[str, Any]:
    """The BSON-shaped document (Python values) Mongo would have stored."""
    encoder = _Encoder(settings_of(type(record)).bson_encoders)
    return {key: encoder.encode(value) for key, value in _model_items(record)}


def encode(record: BaseModel) -> Dict[str, Any]:
    """The row's ``doc``: :func:`to_bson` as BSON Extended JSON (relaxed)."""
    return canonical_document(to_bson(record))


def decode(record_cls: Type[M], doc: Mapping[str, Any]) -> M:
    """A row's ``doc`` back into ``record_cls``. Like Beanie (pydantic runs the
    model's ``__init__`` on validation), a ``doc`` without timestamps gets
    them stamped; every stored ``doc`` has them."""
    return record_cls.model_validate(from_canonical_document(doc))


def ensure_id(record: M) -> M:
    """Mint an id if ``record`` has none, as an insert does."""
    if getattr(record, "id", None) is None:
        record.id = RecordId()
    return record


def _timestamp(value: Any) -> Optional[datetime.datetime]:
    """created_at/updated_at as encoded: a datetime, or the ISO string that
    ``bson_encoders`` produce; aware UTC either way."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def row_values(record: BaseModel, *, source: str = SOURCE_APP) -> Dict[str, Any]:
    """Column values for upserting ``record`` (``id``, ``doc``, timestamps,
    ``bc_source``, ``bc_checksum``), minting an id if it has none."""
    ensure_id(record)
    bson_doc = to_bson(record)
    doc = canonical_document(bson_doc)
    now = datetime.datetime.now(timezone.utc)
    return {
        "id": str(record.id),
        "doc": doc,
        "created_at": _timestamp(bson_doc.get("created_at")) or now,
        "updated_at": _timestamp(bson_doc.get("updated_at")) or now,
        "bc_source": source,
        "bc_checksum": checksum(doc),
    }
