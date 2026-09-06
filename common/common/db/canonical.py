"""Lossless document encoding and content checksums.

A Postgres row's ``doc`` column holds the Mongo document as **BSON Extended
JSON, relaxed mode** (``bson.json_util``): ObjectIds become ``{"$oid": ...}``,
BSON dates ``{"$date": "...Z"}``, binaries ``{"$binary": {...}}``; strings,
numbers, booleans, nulls, arrays and plain objects stay as they are. It is the
standard lossless BSON↔JSON encoding with a reference decoder, which is what
the reverse mirror needs: :func:`from_canonical_document` gives back a document
with real BSON types, not strings that merely look like dates.

The checksum is a sha256 over the canonical JSON serialisation of that
structure (sorted keys, no whitespace). Computing it from a Mongo document and
from the ``doc`` a Postgres row stores yields the same value, which is what
lets the migration tooling compare the two stores row by row.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from datetime import timezone

from bson import json_util
from bson.json_util import RELAXED_JSON_OPTIONS

CHECKSUM_PREFIX = "sha256:"

# Decoding returns timezone-aware UTC datetimes. pymongo hands out naive UTC by
# default; BSON stores UTC milliseconds either way, so writing an aware value
# back to Mongo is identical — aware is simply the unambiguous form.
_RESTORE_OPTIONS = RELAXED_JSON_OPTIONS.with_options(tz_aware=True, tzinfo=timezone.utc)


def _reject_unordered(value: Any, path: str = "$") -> None:
    """``bson.json_util`` silently turns sets into lists in arbitrary order, which would make
    the checksum unstable. Mongo itself cannot encode a set, so refuse them the same way.
    """
    if isinstance(value, (set, frozenset)):
        raise TypeError(f"cannot canonicalise a set at {path}; use a list")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_unordered(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_unordered(item, f"{path}[{index}]")


def canonical_document(doc: Mapping[str, Any]) -> dict[str, Any]:
    """BSON-shaped document (as pymongo/Beanie hand it out) -> JSON-shaped dict.

    Only JSON types remain; BSON-specific values carry Extended JSON tags. The
    ``_id`` key is kept as-is. Raises ``TypeError`` for values BSON cannot
    represent (a pydantic model, a ``Decimal``, a ``set``): callers convert first, so a
    document that would not have round-tripped through Mongo fails loudly here
    instead of drifting between the stores.
    """
    _reject_unordered(doc)
    return json.loads(json_util.dumps(doc, json_options=RELAXED_JSON_OPTIONS))


def from_canonical_document(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Inverse of :func:`canonical_document`: restores ObjectId, datetime (aware UTC), bytes."""
    return json_util.loads(json.dumps(doc), json_options=_RESTORE_OPTIONS)


def canonical_json(value: Any) -> str:
    """Deterministic serialisation of a JSON-shaped value: sorted keys, compact."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def checksum(value: Any) -> str:
    """``sha256:<hex>`` of :func:`canonical_json`; the prefix leaves room to change algorithms."""
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return CHECKSUM_PREFIX + digest


def document_checksum(doc: Mapping[str, Any]) -> str:
    """Checksum of a BSON-shaped document — the form the migration tooling uses on the Mongo side."""
    return checksum(canonical_document(doc))
