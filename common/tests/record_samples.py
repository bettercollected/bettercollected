"""Sample record classes for the record codec tests, each also written as the
Beanie document it replaces (same fields, same ``Settings``).

Together they cover what the services' document classes use, plus encoder
rules no service class happens to exercise: the scalars the default encoders
map (enums of three kinds, bytes, UUID, timedelta, date, secrets, URLs;
Decimal inside untyped mappings only, as no stored class types one), aliases
other than ``_id``, ``exclude=True`` fields, root models, enum-keyed and
untyped mappings, a record nested in a record (encoded with its own
``bson_encoders``), and ``bson_encoders`` that match by ``isinstance`` only
(a ``date`` encoder applied to datetimes).
"""

import datetime as dt
import uuid
from contextlib import contextmanager
from enum import Enum
from functools import lru_cache
from typing import Any, Dict, Iterator, List, Optional, Tuple
from unittest import mock

from pydantic import BaseModel, Field, HttpUrl, RootModel, SecretStr

from common.ids import RecordId
from common.records import Record



@contextmanager
def fixed_clock() -> Iterator[dt.datetime]:
    """Hold the clock the stamps read still, so a test can compare a stamp
    with one reading (``common.clock.utcnow`` is read by ``Record`` and by the
    4.0 ``MongoDocument``, which the codec tests compare it with)."""
    now = dt.datetime.now(dt.timezone.utc)
    with mock.patch("common.records.base.utcnow", lambda: now), mock.patch(
        "common.db.beanie_bridge.utcnow", lambda: now
    ):
        yield now


ISO_ENCODERS = {
    dt.datetime: lambda o: dt.datetime.isoformat(o),
    dt.date: lambda o: dt.date.isoformat(o),
    dt.time: lambda o: dt.time.isoformat(o),
}
DATE_ONLY_ENCODERS = {dt.date: lambda o: dt.date.isoformat(o)}


class Colour(str, Enum):
    RED = "red"
    BLUE = "blue"


class Level(int, Enum):
    LOW = 1
    HIGH = 2


class Plain(Enum):
    A = "a"
    B = "b"


class Address(BaseModel):
    street: str
    since: Optional[dt.datetime] = None
    tags: List[str] = []
    display: Optional[str] = Field(default=None, alias="displayName")


class Numbers(RootModel[List[int]]):
    pass


class AllTypes(BaseModel):
    """The fields of the sample classes (a plain model, as ``StandardForm`` is)."""

    text: str
    quantity: int = 0
    ratio: Optional[float] = None
    flag: bool = False
    when: Optional[dt.datetime] = None
    day: Optional[dt.date] = None
    blob: Optional[bytes] = None
    token: Optional[uuid.UUID] = None
    ttl: Optional[dt.timedelta] = None
    colour: Optional[Colour] = None
    level: Optional[Level] = None
    plain: Optional[Plain] = None
    ref: Optional[RecordId] = None
    refs: List[RecordId] = []
    address: Optional[Address] = None
    addresses: List[Address] = []
    by_colour: Dict[Colour, int] = {}
    extra: Dict[str, Any] = {}
    pair: Optional[Tuple[int, ...]] = None
    secret: Optional[SecretStr] = None
    link: Optional[HttpUrl] = None
    numbers: Optional[Numbers] = None
    label: Optional[str] = Field(default=None, alias="displayLabel")
    internal: Optional[str] = Field(default=None, exclude=True)


# -- records ----------------------------------------------------------------------


class SampleRecord(Record, AllTypes):
    class Settings:
        name = "sample_records"


class IsoRecord(Record, AllTypes):
    at_time: Optional[dt.time] = None

    class Settings:
        name = "sample_iso_records"
        bson_encoders = ISO_ENCODERS


class DateOnlyRecord(Record):
    when: Optional[dt.datetime] = None
    day: Optional[dt.date] = None
    nested: Optional[Address] = None

    class Settings:
        name = "sample_date_only_records"
        bson_encoders = DATE_ONLY_ENCODERS


class HolderRecord(Record):
    title: str
    child: Optional[IsoRecord] = None
    when: Optional[dt.datetime] = None

    class Settings:
        name = "sample_holder_records"


class UnnamedRecord(Record):
    # no Settings: the collection is the class name

    note: str = ""


RECORDS = {
    "sample_records": SampleRecord,
    "sample_iso_records": IsoRecord,
    "sample_date_only_records": DateOnlyRecord,
    "sample_holder_records": HolderRecord,
    "UnnamedRecord": UnnamedRecord,
}

# Values the golden synthesizer cannot guess, per collection.
OVERRIDES = {
    collection: {
        "token": uuid.UUID("12345678-1234-5678-1234-567812345678"),
        "ttl": dt.timedelta(days=1, seconds=2, microseconds=3),
        "numbers": [3, 1, 2],
        "internal": "never stored",
    }
    for collection in ("sample_records", "sample_iso_records")
}


@lru_cache(maxsize=None)
def beanie_documents() -> Dict[str, type]:
    """The same classes as Beanie documents (``MongoDocument``), written out by
    hand: they define the bytes the fixture pins. Built on first use, since
    Beanie must then be initialised for them (see ``init_beanie_documents``)."""
    from common.db.beanie_bridge import MongoDocument

    class SampleRecord(MongoDocument, AllTypes):
        class Settings:
            name = "sample_records"

    class IsoRecord(MongoDocument, AllTypes):
        at_time: Optional[dt.time] = None

        class Settings:
            name = "sample_iso_records"
            bson_encoders = ISO_ENCODERS

    class DateOnlyRecord(MongoDocument):
        when: Optional[dt.datetime] = None
        day: Optional[dt.date] = None
        nested: Optional[Address] = None

        class Settings:
            name = "sample_date_only_records"
            bson_encoders = DATE_ONLY_ENCODERS

    class HolderRecord(MongoDocument):
        title: str
        child: Optional[IsoRecord] = None
        when: Optional[dt.datetime] = None

        class Settings:
            name = "sample_holder_records"

    class UnnamedRecord(MongoDocument):
        note: str = ""

    return {
        "sample_records": SampleRecord,
        "sample_iso_records": IsoRecord,
        "sample_date_only_records": DateOnlyRecord,
        "sample_holder_records": HolderRecord,
        "UnnamedRecord": UnnamedRecord,
    }


async def init_beanie_documents() -> Dict[str, type]:
    """Initialise Beanie for the sample documents without a Mongo server."""
    from common.db.beanie_bridge import init_documents, offline_client

    documents = beanie_documents()
    database = offline_client()["record_samples"]
    await init_documents(database, list(documents.values()), required=False)
    return documents
