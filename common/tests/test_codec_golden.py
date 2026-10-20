"""Golden fixtures of the ``doc`` codec for raw Mongo documents.

The migration (backfill, verify, reconcile) encodes documents as pymongo hands
them out, without a Beanie class: these cases pin that path, including the BSON
types no document class declares. Regenerate only on purpose, with
``scripts/regenerate-codec-golden.sh``.
"""

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bson import Binary, Decimal128, Int64, ObjectId

from common.db import canonical_document, canonical_json, checksum
from common.db.canonical import from_canonical_document
from common.db.codec_golden import (
    AWARE,
    LARGE_INT,
    NAIVE,
    TEXT,
    load,
    regenerating,
    write,
)
from common.db.migrate.engine import row_from_document

FIXTURE = Path(__file__).parent / "fixtures" / "codec_golden" / "raw.json"


def _cases() -> dict:
    oid = ObjectId("65f0a1b2c3d4e5f601234567")
    return {
        "scalars": {
            "_id": oid,
            "text": TEXT,
            "empty": "",
            "int": 7,
            "int64": Int64(2**62),
            "large_int": LARGE_INT,
            "negative": -LARGE_INT,
            "float": 0.1 + 0.2,
            "whole_float": 3.0,
            "tiny_float": 1e-7,
            "infinity": float("inf"),
            "minus_infinity": float("-inf"),
            "nan": float("nan"),
            "true": True,
            "false": False,
            "none": None,
        },
        "bson_types": {
            "_id": oid,
            "ref": ObjectId("65f0a1b2c3d4e5f60123456a"),
            "decimal": Decimal128("1234.5600"),
            "decimal_negative_zero": Decimal128("-0.00"),
            "bytes": b"\x00\x01binary\xff",
            "uuid": Binary(uuid.UUID("12345678-1234-5678-1234-567812345678").bytes, 4),
            "empty_bytes": b"",
        },
        "datetimes": {
            "_id": oid,
            "naive_utc": NAIVE,
            "aware_utc": NAIVE.replace(tzinfo=timezone.utc),
            "aware_offset": AWARE,
            "whole_second": datetime(2026, 1, 1),
            "before_epoch": datetime(1960, 1, 1, 12, 0),
            "far_future": datetime(9999, 12, 31, 23, 59, 59, 999000),
            "epoch": datetime(1970, 1, 1),
            "minus_offset": datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=-5))),
            "iso_string": "2026-03-04T05:06:07.891234+02:00",
        },
        "containers": {
            "_id": oid,
            "empty_object": {},
            "empty_list": [],
            "nested": {"z": 1, "a": {"y": [1, {"x": [None, oid]}]}},
            "mixed_list": [1, "two", 3.5, None, True, {"k": NAIVE}, [oid]],
            "keys": {"$weird": 1, "dotted.key": 2, "ünïcode": 3, "": 4},
            "tuple": (1, 2),
        },
    }


def _encoded() -> dict:
    out = {}
    for name, document in _cases().items():
        doc = canonical_document(document)
        row = row_from_document(document)
        assert row["doc"] == doc and row["_bc_checksum"] == checksum(doc)
        out[name] = {"document": "raw", "doc": doc, "checksum": checksum(doc)}
    return out


def test_raw_documents_encode_to_the_pinned_bytes():
    encoded = _encoded()
    if regenerating():
        write(FIXTURE, encoded)
    pinned = load(FIXTURE)
    assert sorted(pinned) == sorted(encoded)
    for name, case in encoded.items():
        assert canonical_json(case["doc"]) == canonical_json(pinned[name]["doc"]), name
        assert (
            case["checksum"]
            == pinned[name]["checksum"]
            == checksum(pinned[name]["doc"])
        )


def test_pinned_raw_documents_decode_and_encode_to_the_same_bytes():
    for name, case in load(FIXTURE).items():
        again = canonical_document(from_canonical_document(case["doc"]))
        assert canonical_json(again) == canonical_json(case["doc"]), name
