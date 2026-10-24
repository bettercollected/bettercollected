"""The ``doc`` bytes: BSON Extended JSON (relaxed) and its checksum, without Beanie.

The same encoding as :mod:`common.db.canonical`, statement for statement; it
is repeated here because importing anything under ``common.db`` still loads
Beanie (its package imports the Beanie bridge), and the record layer must
not. ``common/tests/test_record_codec.py`` holds the two to identical output
on every pinned golden case. Once the Beanie bridge is gone, one module
re-exports the other.

See :mod:`common.db.canonical` for the reasoning behind each rule: dates are
written as UTC instants, sets are refused, and the checksum is a sha256 over
the sorted, compact JSON.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

from bson import json_util
from bson.json_util import RELAXED_JSON_OPTIONS

CHECKSUM_PREFIX = "sha256:"

_RESTORE_OPTIONS = RELAXED_JSON_OPTIONS.with_options(tz_aware=True, tzinfo=timezone.utc)


def _prepare(value: Any, path: str = "$") -> Any:
    """Refuse sets; move aware datetimes to UTC (copying only what changes)."""
    if isinstance(value, (set, frozenset)):
        raise TypeError(f"cannot canonicalise a set at {path}; use a list")
    if isinstance(value, datetime):
        offset = value.utcoffset()
        if offset:
            return value.astimezone(timezone.utc)
        return value
    if isinstance(value, Mapping):
        items = {key: _prepare(item, f"{path}.{key}") for key, item in value.items()}
        if all(items[key] is item for key, item in value.items()):
            return value
        return items
    if isinstance(value, (list, tuple)):
        prepared = [_prepare(item, f"{path}[{i}]") for i, item in enumerate(value)]
        if all(new is old for new, old in zip(prepared, value)):
            return value
        return prepared
    return value


def canonical_document(doc: Mapping[str, Any]) -> dict[str, Any]:
    """BSON-shaped document -> the JSON-shaped ``doc`` a row stores."""
    doc = _prepare(doc)
    return json.loads(json_util.dumps(doc, json_options=RELAXED_JSON_OPTIONS))


def from_canonical_document(doc: Mapping[str, Any]) -> dict[str, Any]:
    """Inverse of :func:`canonical_document`: ObjectId, aware UTC datetime and bytes again."""
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
    """``sha256:<hex>`` of :func:`canonical_json` (the ``_bc_checksum`` column)."""
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return CHECKSUM_PREFIX + digest
