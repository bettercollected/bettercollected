"""The record codec (common/common/records): the same bytes as the Beanie codec.

* ``fixtures/codec_golden/records.json`` pins what the *current* codec stores
  for the sample classes of ``tests/record_samples.py`` (written as Beanie
  documents); the record classes must encode and decode to exactly those
  bytes. Regenerate only on purpose, after adding a sample:
  ``BC_CODEC_GOLDEN_WRITE=1 uv run pytest tests/test_record_codec.py``, then
  review the diff (an existing case must never change).
* The record layer's copy of the canonical encoding equals
  ``common.db.canonical`` on every pinned ``doc`` in the repository.
* Round trips, ids and timestamps as the Postgres twins handle them today.

The services' document classes are covered by each service's
``test_record_codec_golden.py`` against its own fixture.
"""

import datetime as dt
import json
import math
from pathlib import Path

import pytest
from bson import ObjectId

from common.clock import write_clock
from common.db import beanie_bridge
from common.db import canonical as db_canonical
from common.db.base import SOURCE_APP
from common.db.codec_golden import build_cases, check, load
from common.ids import RecordId
from common.records import (
    canonical,
    decode,
    encode,
    golden,
    row_values,
    to_bson,
)
from common.records.codec import DEFAULT_ENCODERS
from tests.record_samples import (
    OVERRIDES,
    RECORDS,
    Address,
    Colour,
    HolderRecord,
    IsoRecord,
    SampleRecord,
    init_beanie_documents,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "codec_golden" / "records.json"
ALL_FIXTURES = sorted(ROOT.glob("*/tests/fixtures/codec_golden/*.json")) + sorted(
    ROOT.glob("integrations/*/tests/fixtures/codec_golden/*.json")
)


@pytest.fixture
async def documents():
    return await init_beanie_documents()


# -- golden: the sample classes -----------------------------------------------------


async def test_the_beanie_codec_gives_the_pinned_bytes(documents):
    """Pins (or, regenerating, writes) the bytes of today's codec."""
    assert check(FIXTURE, build_cases(documents, OVERRIDES)) == []


async def test_the_record_codec_gives_the_pinned_bytes_for_the_documents(documents):
    assert golden.check_encoding(FIXTURE, build_cases(documents, OVERRIDES)) == []


def test_records_encode_to_the_pinned_bytes():
    cases = build_cases(RECORDS, OVERRIDES)
    assert golden.check_encoding(FIXTURE, cases) == []
    # Beanie's encoder agrees on records too, except on a nested record: it
    # only gives its own Documents their own encoders.
    flat = {k: v for k, v in cases.items() if not k.startswith("sample_holder")}
    assert [p for p in check(FIXTURE, flat) if "no longer built" not in p] == []


def test_pinned_docs_decode_into_records_and_encode_back():
    classes = {cls.__name__: cls for cls in RECORDS.values()}
    assert golden.check_round_trip(FIXTURE, classes) == []


async def test_the_twin_of_each_sample_document_is_the_record(documents):
    twins = golden.twins(documents)
    assert golden.check_encoding(FIXTURE, build_cases(twins, OVERRIDES)) == []
    for collection, record_cls in RECORDS.items():
        twin_schema = twins[collection].model_json_schema()
        assert twin_schema == record_cls.model_json_schema()


async def test_records_look_the_same_on_the_wire(documents):
    classes = {cls.__name__: cls for cls in documents.values()}
    assert golden.check_wire(FIXTURE, classes, beanie_bridge.from_row_doc) == []


def test_the_fixture_covers_every_sample_in_every_variant():
    pinned = load(FIXTURE)
    assert len(pinned) == len(RECORDS) * 4
    doc = pinned["sample_records/full"]["doc"]
    assert doc["displayLabel"] and "internal" not in doc  # alias kept, exclude honoured
    assert doc["token"]["$binary"]["subType"] == "04"
    assert doc["ttl"] == 86402.000003 and doc["numbers"] == [3, 1, 2]
    iso = pinned["sample_iso_records/full"]["doc"]
    assert isinstance(iso["when"], str) and isinstance(iso["at_time"], str)
    holder = pinned["sample_holder_records/full"]["doc"]
    assert isinstance(holder["child"]["when"], str)  # the child's own encoders
    assert "$date" in holder["when"]  # the holder has none


# -- the canonical encoding is the same module twice ----------------------------------


def _pinned_docs():
    for path in ALL_FIXTURES:
        for name, case in load(path).items():
            yield f"{path.parent.parent.parent.name}:{path.name}:{name}", case


def test_every_fixture_file_is_compared():
    names = {path.name for path in ALL_FIXTURES}
    assert {"raw.json", "records.json", "backend.json", "auth.json"} <= names
    assert "google.json" in names


def test_the_canonical_copy_matches_common_db_on_every_pinned_doc():
    count = 0
    for name, case in _pinned_docs():
        restored = canonical.from_canonical_document(case["doc"])
        assert canonical.canonical_document(restored) == (
            db_canonical.canonical_document(
                db_canonical.from_canonical_document(case["doc"])
            )
        ), name
        assert canonical.canonical_json(case["doc"]) == db_canonical.canonical_json(
            case["doc"]
        )
        assert canonical.checksum(case["doc"]) == case["checksum"], name
        count += 1
    assert count > 200


def test_the_canonical_copy_matches_common_db_on_raw_bson_values():
    from tests.test_codec_golden import _cases

    for name, document in _cases().items():
        assert canonical.canonical_document(document) == (
            db_canonical.canonical_document(document)
        ), name


def test_the_canonical_copy_refuses_sets_like_common_db():
    for module in (canonical, db_canonical):
        with pytest.raises(TypeError, match="cannot canonicalise a set"):
            module.canonical_document({"tags": {"a"}})


def test_source_app_matches_the_row_base():
    from common.records import SOURCE_APP as RECORD_SOURCE_APP

    assert RECORD_SOURCE_APP == SOURCE_APP


def test_default_encoders_follow_beanie():
    from beanie.odm.utils.encoder import DEFAULT_CUSTOM_ENCODERS
    from beanie.odm.fields import Link

    beanie_types = [t for t in DEFAULT_CUSTOM_ENCODERS if t is not Link]
    assert list(DEFAULT_ENCODERS) == beanie_types


# -- round trips -----------------------------------------------------------------------


def _sample(**overrides):
    values = dict(
        text="hello",
        quantity=3,
        when=dt.datetime(2026, 5, 6, 7, 8, 9, 123456, tzinfo=dt.timezone.utc),
        colour=Colour.BLUE,
        ref=RecordId("65f0a1b2c3d4e5f601234567"),
        address=Address(street="Main", displayName="Home"),
        extra={"n": 2**53 + 1, "f": 0.1 + 0.2, "nested": {"b": [1, None]}},
    )
    values.update(overrides)
    return SampleRecord(**values)


def test_row_values_of_a_record():
    record = _sample()
    values = row_values(record)
    assert set(values) == {
        "id",
        "doc",
        "created_at",
        "updated_at",
        "bc_source",
        "bc_checksum",
    }
    assert values["id"] == str(record.id) == values["doc"]["_id"]["$oid"]
    assert values["bc_source"] == "app"
    assert values["bc_checksum"] == canonical.checksum(values["doc"])
    assert values["created_at"] == record.created_at
    assert values["updated_at"] == record.updated_at
    assert values["doc"]["created_at"] == {"$date": "%sZ" % _millis(record.created_at)}
    assert row_values(record, source="backfill")["bc_source"] == "backfill"


def _millis(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def test_row_values_mint_an_id_when_missing():
    record = _sample()
    assert record.id is None
    values = row_values(record)
    assert isinstance(record.id, RecordId)
    assert values["id"] == str(record.id)


def test_row_values_read_timestamps_stored_as_iso_strings():
    created = dt.datetime(
        2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone(dt.timedelta(hours=2))
    )
    record = IsoRecord(text="x", created_at=created, updated_at=created)
    values = row_values(record)
    assert values["doc"]["created_at"] == "2026-01-02T03:04:05+02:00"
    assert values["created_at"] == created
    assert values["created_at"].tzinfo == dt.timezone.utc


def test_row_values_without_timestamps_use_now():
    record = SampleRecord.model_construct(text="never stamped")
    assert record.created_at is None
    before = dt.datetime.now(dt.timezone.utc)
    values = row_values(record)
    assert values["doc"]["created_at"] is None
    assert values["created_at"] >= before and values["updated_at"] >= before


def test_a_record_round_trips_through_its_row():
    record = _sample(refs=[RecordId(), RecordId()], pair=(1, 2))
    values = row_values(record)
    again = decode(SampleRecord, values["doc"])
    # BSON dates keep milliseconds: everything else comes back as it was
    lossy = {"when", "created_at", "updated_at"}
    assert again.model_dump(exclude=lossy) == record.model_dump(exclude=lossy)
    assert again.when == record.when.replace(microsecond=123000)
    assert isinstance(again.id, RecordId) and isinstance(again.refs[0], RecordId)
    assert again.extra["n"] == 2**53 + 1 and math.isclose(again.extra["f"], 0.3)
    assert row_values(again)["doc"] == values["doc"]


def test_a_nested_record_round_trips_with_its_own_encoders():
    child = IsoRecord(text="child", at_time=dt.time(1, 2, 3))
    holder = HolderRecord(title="t", child=child)
    doc = row_values(holder)["doc"]
    assert isinstance(doc["child"]["created_at"], str)
    assert doc["child"]["at_time"] == "01:02:03"
    again = decode(HolderRecord, doc)
    assert again.child.at_time == child.at_time and again.child.text == "child"
    assert encode(again) == doc


async def test_decoding_a_doc_without_timestamps_stamps_it_like_beanie(documents):
    doc = encode(SampleRecord.model_construct(text="x", id=RecordId()))
    assert doc["created_at"] is None
    with write_clock() as now:
        record = decode(SampleRecord, doc)
        document = beanie_bridge.from_row_doc(documents["sample_records"], doc)
    assert record.created_at == record.updated_at == document.created_at == now


def test_to_bson_keeps_bson_values():
    record = _sample()
    record.ensure_id()
    bson = to_bson(record)
    assert type(bson["_id"]) is RecordId and isinstance(bson["_id"], ObjectId)
    assert bson["colour"] == "blue" and bson["address"]["displayName"] == "Home"
    assert "id" not in bson and "internal" not in bson


def test_a_time_without_an_encoder_cannot_be_stored_as_with_beanie():
    from beanie.odm.utils.encoder import Encoder

    from common.records.codec import _Encoder

    for encoder in (Encoder(), _Encoder({})):
        with pytest.raises(ValueError, match="Cannot encode"):
            encoder.encode({"at": dt.time(1, 2)})


def test_one_clock_for_every_stamp_within_a_write():
    with write_clock() as now:
        record = _sample()
    assert record.created_at == record.updated_at == now
    assert json.loads(json.dumps(row_values(record)["doc"]))  # JSON-safe
