"""``RecordId`` behaves exactly like Beanie's ``PydanticObjectId`` (common/common/ids.py).

Every comparison runs both types side by side: same parse results, same
validation errors, same JSON, same JSON schema. These tests go when Beanie
does; until then they are what keeps a group's switch invisible to clients.
"""

import json
import time
from typing import List, Optional

import pytest
from beanie import PydanticObjectId
from bson import ObjectId
from pydantic import BaseModel, TypeAdapter, ValidationError

from common.db.beanie_bridge import derived_object_id
from common.ids import RecordId, derived_id, is_record_id, new_id

HEX = "65f0a1b2c3d4e5f601234567"

PYTHON_INPUTS = [
    HEX,
    HEX.upper(),
    HEX.encode(),
    ObjectId(HEX),
    PydanticObjectId(HEX),
    RecordId(HEX),
    "",
    "not-an-id",
    HEX[:-1],
    HEX + "0",
    "zz" * 12,
    b"\xff" * 24,
    b"twelve bytes",
    12,
    1.5,
    None,
    [HEX],
    {"$oid": HEX},
]

JSON_INPUTS = [
    f'"{HEX}"',
    f'"{HEX.upper()}"',
    f'"{HEX[:-1]}"',
    '"not-an-id"',
    "123",
    "null",
    '{"$oid": "%s"}' % HEX,
]


def _outcome(validate, value):
    try:
        result = validate(value)
    except ValidationError as error:
        return "error", [
            (e["type"], e["msg"], e["loc"], repr(e.get("input")))
            for e in error.errors(include_url=False)
        ]
    if value is None:  # both mint a new id, as ObjectId(None) does
        return "ok", isinstance(result, ObjectId)
    return "ok", (str(result), isinstance(result, ObjectId))


@pytest.mark.parametrize("value", PYTHON_INPUTS, ids=repr)
def test_python_validation_matches_pydantic_object_id(value):
    new = _outcome(TypeAdapter(RecordId).validate_python, value)
    old = _outcome(TypeAdapter(PydanticObjectId).validate_python, value)
    assert new == old


@pytest.mark.parametrize("value", JSON_INPUTS)
def test_json_validation_matches_pydantic_object_id(value):
    new = _outcome(TypeAdapter(RecordId).validate_json, value)
    old = _outcome(TypeAdapter(PydanticObjectId).validate_json, value)
    assert new == old


def test_the_422_message_is_unchanged():
    with pytest.raises(ValidationError) as error:
        TypeAdapter(RecordId).validate_python("nope")
    assert error.value.errors()[0]["msg"] == (
        "Value error, Id must be of type PydanticObjectId"
    )


def test_validation_returns_a_record_id():
    for value in (HEX, HEX.encode(), ObjectId(HEX), PydanticObjectId(HEX)):
        parsed = TypeAdapter(RecordId).validate_python(value)
        assert type(parsed) is RecordId and str(parsed) == HEX


class New(BaseModel):
    id: RecordId
    maybe: Optional[RecordId] = None
    many: List[RecordId] = []


class Old(BaseModel):
    id: PydanticObjectId
    maybe: Optional[PydanticObjectId] = None
    many: List[PydanticObjectId] = []


def test_serialisation_matches_pydantic_object_id():
    data = {"id": HEX, "maybe": None, "many": [HEX, HEX.upper()]}
    new, old = New(**data), Old(**data)
    assert new.model_dump_json() == old.model_dump_json()
    assert new.model_dump(mode="json") == old.model_dump(mode="json")
    assert json.loads(new.model_dump_json())["id"] == HEX
    # python mode keeps the id object, as before
    assert type(new.model_dump()["id"]) is RecordId
    assert new.model_dump() == old.model_dump()


def test_json_schema_matches_pydantic_object_id():
    assert TypeAdapter(RecordId).json_schema() == (
        TypeAdapter(PydanticObjectId).json_schema()
    )
    new, old = New.model_json_schema(), Old.model_json_schema()
    old["title"] = new["title"]
    assert new == old
    assert "PydanticObjectId" in new["$defs"]  # the OpenAPI component keeps its name
    for mode in ("validation", "serialization"):
        assert TypeAdapter(RecordId).json_schema(mode=mode) == (
            TypeAdapter(PydanticObjectId).json_schema(mode=mode)
        )


def test_both_types_in_one_model_keep_their_own_class():
    class Mixed(BaseModel):
        old: PydanticObjectId
        new: RecordId
        news: List[RecordId]

    mixed = Mixed(old=HEX, new=HEX, news=[HEX])
    assert type(mixed.old) is PydanticObjectId
    assert type(mixed.new) is RecordId and type(mixed.news[0]) is RecordId
    schema = Mixed.model_json_schema()
    assert list(schema["$defs"]) == ["PydanticObjectId"]
    again = Mixed.model_validate_json(mixed.model_dump_json())
    assert type(again.old) is PydanticObjectId and type(again.new) is RecordId


def test_equal_and_hash_equal_to_other_object_ids():
    record_id = RecordId(HEX)
    for other in (ObjectId(HEX), PydanticObjectId(HEX)):
        assert record_id == other and other == record_id
        assert hash(record_id) == hash(other)
        assert other in {record_id}
    assert record_id != HEX  # an ObjectId never equals its string, as before
    assert str(record_id) == HEX and repr(record_id) == f"ObjectId('{HEX}')"


def test_new_ids_are_minted_like_mongo_ids():
    before = int(time.time())
    ids = [new_id() for _ in range(1000)]
    assert len(set(ids)) == 1000
    assert all(type(i) is RecordId and len(str(i)) == 24 for i in ids)
    assert all(str(i) == str(i).lower() for i in ids)
    assert before - 1 <= ids[0].generation_time.timestamp() <= time.time() + 1
    # same process: same random part, increasing counter -> sorted by creation
    assert [str(i) for i in ids] == sorted(str(i) for i in ids)
    assert type(RecordId()) is RecordId


def test_derived_ids_are_the_ones_stored_today():
    for parts in (("group", "member@example.org"), ("g", "f", 3), ()):
        assert derived_id(*parts) == derived_object_id(*parts)
        assert type(derived_id(*parts)) is RecordId
    assert derived_id("a", "b") != derived_id("a", "c")


@pytest.mark.parametrize(
    "value, expected",
    [
        (HEX, True),
        (HEX.encode(), True),
        (ObjectId(), True),
        ("nope", False),
        (b"\xff" * 24, False),
        (None, False),
        (12, False),
    ],
)
def test_is_record_id(value, expected):
    assert is_record_id(value) is expected
