"""Record ids: the 24-hex ObjectId every stored document is keyed by.

:class:`RecordId` replaces Beanie's ``PydanticObjectId`` without depending on
Beanie. Everything a caller or a client can observe stays the same:

* **stored data:** an id is a 12-byte BSON ObjectId, written as 24 lowercase
  hex characters (the ``id`` column of every Postgres row, ``doc._id.$oid``);
* **new ids** are minted the way Mongo and Beanie mint them (4-byte timestamp,
  per-process random value, counter), so they still sort by creation time;
* **validation:** an ``ObjectId`` (a ``PydanticObjectId`` included), a 24-hex
  ``str`` or the same as UTF-8 ``bytes`` (and ``None`` mints a new id, as
  ``ObjectId(None)`` does); anything else fails with the error the API
  returns today, word for word (it names ``PydanticObjectId``, which is part
  of the 422 body clients may match on);
* **serialisation:** a ``str`` in JSON, the id object itself in Python mode;
* **JSON schema / OpenAPI:** the same string schema (pattern, length,
  example) under the same component name, ``PydanticObjectId``.

The class subclasses ``bson.ObjectId``, exactly as ``PydanticObjectId`` does,
so a ``RecordId`` and a ``PydanticObjectId`` with the same value compare and
hash equal, and both encode to ``{"$oid": ...}`` in a row's ``doc``. That is
what lets the repository groups move to it one at a time while the others
still hand out Beanie documents. ``bson`` stays a dependency of the codec
until the 5.0 removal of the Mongo import path.
"""

from __future__ import annotations

import hashlib
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema

__all__ = ["RecordId", "derived_id", "is_record_id", "new_id"]

#: Pattern of a serialised id (``id`` columns carry the same CHECK).
ID_PATTERN = r"^[0-9a-f]{24}$"
#: The message of today's 422 for a malformed id (from ``PydanticObjectId``).
INVALID_ID_MESSAGE = "Id must be of type PydanticObjectId"
#: The example shown in the OpenAPI schema.
EXAMPLE = "5eb7cf5a86d9755df3a6c593"

# The core schema reference. pydantic names the JSON schema component after
# the part before the colon, so the OpenAPI document keeps its
# ``PydanticObjectId`` component; the suffix keeps this definition apart from
# Beanie's while both types are in use, so each validates to its own class.
_CORE_REF = "PydanticObjectId:common.ids.RecordId"


class RecordId(ObjectId):
    """A document id. ``RecordId()`` mints a new one; ``RecordId(value)``
    parses a 24-hex string or copies another ObjectId.

    No ``__slots__``, like ``PydanticObjectId``: FastAPI's ``jsonable_encoder``
    falls back to ``vars()`` for a bare id in an untyped response and writes
    ``{}``; keeping that (odd) result keeps such responses unchanged."""

    @classmethod
    def validate(cls, value: Any) -> "RecordId":
        """Parse ``value`` the way the API always has (see the module docstring)."""
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        try:
            return cls(value)
        except (InvalidId, TypeError):
            raise ValueError(INVALID_ID_MESSAGE)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        definition = core_schema.definition_reference_schema(_CORE_REF)
        return core_schema.definitions_schema(
            definition,
            [
                core_schema.json_or_python_schema(
                    python_schema=core_schema.no_info_plain_validator_function(
                        cls.validate
                    ),
                    json_schema=core_schema.no_info_after_validator_function(
                        cls.validate,
                        core_schema.str_schema(
                            pattern=ID_PATTERN, min_length=24, max_length=24
                        ),
                    ),
                    serialization=core_schema.plain_serializer_function_ser_schema(
                        lambda instance: str(instance), when_used="json"
                    ),
                    ref=_CORE_REF,
                )
            ],
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        handler.resolve_ref_schema(json_schema).update(example=EXAMPLE)
        return json_schema


def new_id() -> RecordId:
    """A freshly minted id (what an insert assigns when the record has none)."""
    return RecordId()


def derived_id(*parts: Any) -> RecordId:
    """An id that is a function of ``parts``, for records whose identity *is* a
    relation (a group member, a group-form link): writing the same relation
    twice addresses the same row. Same digest as
    ``common.db.beanie_bridge.derived_object_id``, so existing rows keep their ids."""
    digest = hashlib.sha1("\x00".join(str(p) for p in parts).encode()).digest()
    return RecordId(digest[:12])


def is_record_id(value: Any) -> bool:
    """Whether ``value`` is an id or parses as one. ``None`` is not, although
    validation turns it into a new id (as ``ObjectId(None)`` and Beanie do)."""
    if value is None:
        return False
    try:
        RecordId.validate(value)
    except ValueError:  # a UnicodeDecodeError included
        return False
    return True
