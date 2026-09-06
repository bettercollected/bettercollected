import hashlib
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from bson import ObjectId

from common.db import (
    canonical_document,
    canonical_json,
    checksum,
    document_checksum,
    from_canonical_document,
)


def test_key_order_does_not_change_the_checksum():
    assert checksum({"a": 1, "b": {"x": 1, "y": 2}}) == checksum(
        {"b": {"y": 2, "x": 1}, "a": 1}
    )


def test_none_and_missing_are_different_documents():
    assert checksum({"a": None}) != checksum({})


def test_canonical_json_is_compact_and_sorted():
    assert canonical_json({"b": [1, 2], "a": "é"}) == '{"a":"é","b":[1,2]}'


def test_checksum_is_prefixed_sha256_of_canonical_json():
    value = {"a": 1}
    expected = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    assert checksum(value) == "sha256:" + expected


def test_bson_types_get_extended_json_tags_and_json_types_stay():
    oid = ObjectId()
    when = datetime(2026, 9, 6, 10, 0, 0, 123000, tzinfo=timezone.utc)
    doc = canonical_document(
        {
            "_id": oid,
            "when": when,
            "n": 1,
            "f": 1.5,
            "s": "x",
            "b": True,
            "none": None,
            "l": [1, "a"],
        }
    )
    assert doc["_id"] == {"$oid": str(oid)}
    assert doc["when"] == {"$date": "2026-09-06T10:00:00.123Z"}
    assert {k: doc[k] for k in ("n", "f", "s", "b", "none", "l")} == {
        "n": 1,
        "f": 1.5,
        "s": "x",
        "b": True,
        "none": None,
        "l": [1, "a"],
    }


def test_naive_datetimes_are_treated_as_utc():
    naive = datetime(2026, 9, 6, 10, 0, 0)
    aware = datetime(2026, 9, 6, 10, 0, 0, tzinfo=timezone.utc)
    assert canonical_document({"t": naive}) == canonical_document({"t": aware})


def test_iso_string_dates_stay_strings():
    # form_responses stores datetimes as ISO strings (custom bson_encoders); they must not be reinterpreted.
    doc = canonical_document({"created_at": "2026-09-06T10:00:00.123456"})
    assert doc["created_at"] == "2026-09-06T10:00:00.123456"


def test_round_trip_restores_bson_types():
    original = {
        "_id": ObjectId(),
        "ref": ObjectId(),
        "when": datetime(2026, 9, 6, 10, 0, 0, 123000, tzinfo=timezone.utc),
        "blob": b"\x00\x01secret",  # stored as $binary subtype 00; decodes back to bytes
        "nested": {"ids": [ObjectId(), ObjectId()], "n": 3},
        "text": "plain",
    }
    restored = from_canonical_document(canonical_document(original))
    assert restored == original
    assert isinstance(restored["_id"], ObjectId)
    assert (
        isinstance(restored["when"], datetime) and restored["when"].tzinfo is not None
    )
    assert (
        restored["blob"] == b"\x00\x01secret"
    )  # subtype-0 Binary decodes to plain bytes


def test_naive_input_round_trips_to_the_aware_utc_equivalent():
    naive = datetime(2026, 9, 6, 10, 0, 0, 123000)
    restored = from_canonical_document(canonical_document({"t": naive}))
    assert restored["t"] == naive.replace(tzinfo=timezone.utc)


def test_document_checksum_equals_checksum_of_the_stored_doc():
    mongo_doc = {
        "_id": ObjectId(),
        "title": "t",
        "when": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    stored = canonical_document(mongo_doc)  # what a Postgres row keeps in `doc`
    assert document_checksum(mongo_doc) == checksum(stored)


@pytest.mark.parametrize("bad", [Decimal("1.5"), object(), {1, 2}])
def test_values_bson_cannot_represent_fail_loudly(bad):
    with pytest.raises(TypeError):
        canonical_document({"v": bad})
