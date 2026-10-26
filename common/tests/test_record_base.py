"""The ``Record`` base (common/common/records/base.py) behaves like ``MongoDocument``
in everything the repositories, services and API rely on, without Beanie."""

import datetime as dt
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest
from beanie import PydanticObjectId

from common.exceptions import NotFoundError
from common.ids import RecordId
from common.records import Record, RecordSettings, settings_of
from tests.record_samples import (
    ISO_ENCODERS,
    IsoRecord,
    SampleRecord,
    UnnamedRecord,
    fixed_clock,
    init_beanie_documents,
)

HEX = "65f0a1b2c3d4e5f601234567"
COMMON = Path(__file__).resolve().parents[1]


class Note(Record):
    body: str = ""
    author_id: Optional[RecordId] = None

    class Settings:
        name = "notes"


class ChildNote(Note):
    pass


def test_construction_stamps_both_timestamps_with_one_reading():
    with fixed_clock() as now:
        note = Note(body="x")
    assert note.created_at == note.updated_at == now
    assert note.id is None  # minted when stored


def test_given_timestamps_are_kept():
    created = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    note = Note(created_at=created)
    assert note.created_at == created and note.updated_at != created


async def test_stamping_matches_mongo_document():
    documents = await init_beanie_documents()
    with fixed_clock() as now:
        for cls in (UnnamedRecord, documents["UnnamedRecord"]):
            assert cls(note="x").created_at == now
            assert cls.model_validate({"note": "x"}).created_at == now
            assert cls.model_construct(note="x").created_at is None


def test_touch_moves_only_updated_at():
    note = Note(created_at=dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc))
    created = note.created_at
    with fixed_clock() as now:
        assert note.touch() is note
    assert note.updated_at == now and note.created_at == created


def test_ensure_id_mints_once():
    note = Note()
    note.ensure_id()
    minted = note.id
    assert isinstance(minted, RecordId)
    assert note.ensure_id().id == minted


def test_id_is_stored_as_underscore_id_and_accepts_both_names():
    by_name = Note(id=HEX)
    by_alias = Note(_id=HEX)
    assert by_name.id == by_alias.id == RecordId(HEX)
    assert type(by_alias.id) is RecordId
    assert Note(id=PydanticObjectId(HEX)).id == RecordId(HEX)
    dumped = by_name.model_dump(by_alias=True, mode="json")
    assert dumped["_id"] == HEX and "id" not in dumped
    assert by_name.model_dump(mode="json")["id"] == HEX


def test_settings():
    assert Note.get_settings() == RecordSettings(name="notes", bson_encoders={})
    assert Note.collection_name() == "notes"
    assert ChildNote.collection_name() == "notes"  # inherited, as in Beanie
    assert UnnamedRecord.collection_name() == "UnnamedRecord"
    assert IsoRecord.get_settings().bson_encoders == ISO_ENCODERS
    assert settings_of(Record).name == "Record"


async def test_settings_read_the_same_as_beanie():
    documents = await init_beanie_documents()
    for collection, document_cls in documents.items():
        beanie = document_cls.get_settings()
        ours = settings_of(document_cls)
        assert ours.name == beanie.name == collection
        assert ours.bson_encoders == beanie.bson_encoders


def test_verify_doc_exists_matches_mongo_document():
    from common.db.beanie_bridge import MongoDocument

    class FormResponseThing(Record):
        pass

    class FormResponseThingDocument(MongoDocument):
        pass

    note = Note()
    assert Note.verify_doc_exists(note, {"id": HEX}) is note
    messages = []
    for cls in (FormResponseThing, FormResponseThingDocument):
        with pytest.raises(NotFoundError) as error:
            cls.verify_doc_exists(None, {"id": HEX})
        messages.append(error.value.message)
    assert messages[0] == (
        "Error form response thing with ({'id': '%s'},) does not exist." % HEX
    )
    assert messages[1] == messages[0].replace("thing with", "thing document with")


async def test_json_schema_matches_mongo_document():
    documents = await init_beanie_documents()
    for collection, record_cls in (
        ("sample_records", SampleRecord),
        ("sample_iso_records", IsoRecord),
        ("UnnamedRecord", UnnamedRecord),
    ):
        for mode in ("validation", "serialization"):
            assert record_cls.model_json_schema(mode=mode) == (
                documents[collection].model_json_schema(mode=mode)
            )


def test_excluded_fields_are_left_out_of_the_schema_and_dumps():
    assert "internal" not in SampleRecord.model_json_schema()["properties"]
    sample = SampleRecord(text="t", internal="secret")
    assert "internal" not in sample.model_dump()


def test_the_record_layer_imports_neither_beanie_nor_common_db():
    code = (
        "import sys\n"
        "sys.modules['beanie'] = None  # any import of it fails\n"
        "import common.ids, common.records\n"
        "from common.records import Record, RecordId, decode, encode, row_values\n"
        "class N(Record):\n"
        "    body: str = ''\n"
        "values = row_values(N(body='x'))\n"
        "assert decode(N, values['doc']).body == 'x'\n"
        "assert not [m for m in sys.modules if m == 'common.db' or "
        "m.startswith('common.db.')], 'common.db imported'\n"
        "assert not [m for m in sys.modules if m.startswith('beanie.')]\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=COMMON,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
