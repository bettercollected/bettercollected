"""``Record``: the base of every stored document, without Beanie.

A drop-in for the 4.0 ``MongoDocument`` (``common.db.beanie_bridge``) as far as
the repositories, services and API are concerned (see the package docstring
for what is deliberately left out). It keeps:

* ``id`` (a :class:`common.ids.RecordId`), aliased ``_id`` with population by
  name, as Beanie configures it: ``Model(id=...)`` and ``Model(_id=...)`` both
  work, a dump by alias (FastAPI's default) writes ``_id``, and the field keeps
  its OpenAPI description;
* ``created_at`` / ``updated_at``, stamped from :func:`common.clock.utcnow`
  when not given. pydantic runs ``__init__`` on ``model_validate`` too, so a
  stored document without them is stamped on read, exactly as with Beanie;
  ``model_construct`` stamps nothing;
* :meth:`touch`, the clock move ``MongoDocument.save()`` makes before a write;
* the nested ``Settings`` class (``name``, ``bson_encoders``) read by
  :meth:`get_settings`, so model files keep their declarations unchanged;
* :meth:`pretty_class_name` and :meth:`verify_doc_exists`, with the same
  ``NotFoundError`` message.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from common.clock import utcnow
from common.exceptions import NotFoundError
from common.ids import RecordId

R = TypeVar("R", bound="Record")


def _alias(name: str) -> str:
    """``id`` is stored as ``_id``; every other field under its own name."""
    return "_id" if name == "id" else name


def _drop_excluded(schema: Dict[str, Any], model: Type[BaseModel]) -> None:
    """Fields marked ``exclude=True`` are never sent, so the JSON schema
    leaves them out too (Beanie does the same)."""
    properties = schema.get("properties")
    if not properties:
        return
    for name, info in model.model_fields.items():
        key = info.alias or name
        if key in properties and info.exclude:
            del properties[key]


@dataclass(frozen=True)
class RecordSettings:
    """What a record class declares in its nested ``Settings`` class.

    ``name``           the collection / table the record is stored in (the
                       class name when not set, as in Beanie);
    ``bson_encoders``  per-type encoders applied when the record is encoded
                       to its ``doc`` (in declaration order, exact type
                       first): today's documents store dates as ISO strings
                       this way, and the codec must keep doing so.
    """

    name: str
    bson_encoders: Dict[Any, Callable[[Any], Any]] = field(default_factory=dict)


def settings_of(cls: type) -> RecordSettings:
    """The settings of any document class: a :class:`Record` or (while both
    exist) a Beanie document, read from its nested ``Settings`` class the way
    Beanie reads it (inherited attributes included)."""
    declared = getattr(cls, "Settings", None)
    return RecordSettings(
        name=getattr(declared, "name", None) or cls.__name__,
        bson_encoders=dict(getattr(declared, "bson_encoders", None) or {}),
    )


class Record(BaseModel):
    """Base class of a stored document (see the module docstring)."""

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=_alias,
        json_schema_extra=_drop_excluded,
    )

    id: Optional[RecordId] = Field(
        default=None, description="MongoDB document ObjectID"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Subclasses declare ``class Settings: name = ...; bson_encoders = {...}``.

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        # utcnow(): one instant for every stamp made within one write
        now = utcnow()
        self.created_at = self.created_at if self.created_at else now
        self.updated_at = self.updated_at if self.updated_at else now

    # -- settings ----------------------------------------------------------------
    @classmethod
    def get_settings(cls) -> RecordSettings:
        return settings_of(cls)

    @classmethod
    def collection_name(cls) -> str:
        """The collection (and Postgres table) this record is stored in."""
        return settings_of(cls).name

    # -- writes ------------------------------------------------------------------
    def ensure_id(self: R) -> R:
        """Mint an id if the record has none (an insert does this)."""
        if self.id is None:
            self.id = RecordId()
        return self

    def touch(self: R) -> R:
        """Move ``updated_at`` to now: what a save does before storing."""
        self.updated_at = utcnow()
        return self

    # -- lookups -----------------------------------------------------------------
    @classmethod
    def pretty_class_name(cls) -> str:
        """``FormResponseDocument`` -> ``form response document`` (for messages)."""
        return re.sub(r"([a-z])([A-Z])", r"\1 \2", cls.__name__).lower()

    @classmethod
    def verify_doc_exists(cls, doc: Optional[R], *args: Any) -> R:
        """``doc``, or ``NotFoundError`` naming the lookup that found nothing."""
        if doc is None:
            raise NotFoundError(
                f"Error {cls.pretty_class_name()} with {args} does not exist."
            )
        return doc
