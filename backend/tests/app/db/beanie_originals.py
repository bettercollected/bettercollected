"""The Beanie document classes of the groups that moved to ``Record``, frozen
as they were before the move (test support; removed together with Beanie).

* They are the reference of the wire check in ``test_record_codec_golden.py``:
  the ``Record`` classes now in ``backend.app.schemas`` must describe (JSON
  schema) and serialise every pinned document exactly as these did.
* They still name the 4.0 collections, so the tests of the migration and
  routing machinery keep exercising ``allowed_origins`` and
  ``rate_limit_counters`` through the repositories below, as they were
  before the move.
"""

import datetime as dt
from typing import Annotated, List, Optional

from beanie import Indexed, PydanticObjectId
from bson import ObjectId
from common.clock import utcnow
from common.configs.mongo_document import MongoDocument
from common.db import PostgresRepositoryBase, write_op
from pydantic import EmailStr, field_validator
from pymongo import ReturnDocument

from backend.app.handlers.database import entity
from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.models.types.coupon_code import CouponCode
from backend.db.models import AllowedOriginRow

_ISO_ENCODERS = {
    dt.datetime: lambda o: dt.datetime.isoformat(o),
    dt.date: lambda o: dt.date.isoformat(o),
    dt.time: lambda o: dt.time.isoformat(o),
}


# -- refdata ---------------------------------------------------------------------


class AllowedOriginsDocument(MongoDocument):
    """A custom MongoDocument subclass representing a document in the
    'allowedOrigins' collection.

    Attributes:
        origin (str): The origin of the document.

    Class Attributes:
        Collection: A nested class that defines the name of the collection
            for this document type.
        Settings: A nested class that defines the name of the settings for
            this document type, as well as bson encoder functions for
            certain datetime objects.
    """

    origin: str

    class Settings:
        name = "allowed_origins"
        bson_encoders = _ISO_ENCODERS


class FormPluginConfigDocument(MongoDocument, FormProviderConfigDto):
    class Settings:
        name = "forms_plugin_configs"
        bson_encoders = _ISO_ENCODERS


class CouponCodeDocument(MongoDocument):
    code: Annotated[CouponCode, Indexed(unique=True)]
    status: CouponStatus = CouponStatus.ACTIVE
    used_by: Optional[EmailStr] = None
    activated_at: Optional[dt.datetime] = None

    class Settings:
        name = "coupon_codes"
        bson_encoders = _ISO_ENCODERS


class PriceSuggestion(MongoDocument):
    user_id: PydanticObjectId
    email: EmailStr
    price: int

    class Settings:
        name = "price_suggestion"
        bson_encoders = _ISO_ENCODERS


class UserFeedbackDocument(MongoDocument):
    reason_for_deletion: str
    feedback: Optional[str] = None

    class Settings:
        name = "user_feedback"
        bson_encoders = _ISO_ENCODERS


# -- analytics -------------------------------------------------------------------


class FlowEventDocument(MongoDocument):
    """
    A single anonymous navigation step inside a form fill.

    Deliberately privacy-first: no answers, no identity — only a random
    client-generated session id and which page led to which. This is enough to
    aggregate per-branch traffic and drop-off without ever persisting content
    a responder hasn't chosen to submit.
    """

    form_id: str
    session_id: str
    from_page: str
    to_page: str

    class Settings:
        name = "form_flow_events"


class RateLimitCounterDocument(MongoDocument):
    """Requests one client made in one fixed window (services/rate_limiter.py).

    The id is derived from a keyed hash of the scope, the client and the
    window, so the record names no address. Kept until ``expires_at``, a
    window after its own ended."""

    hits: int = 0
    expires_at: dt.datetime

    @field_validator("expires_at", mode="after")
    @classmethod
    def _utc(cls, value: dt.datetime) -> dt.datetime:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        name = "rate_limit_counters"


ORIGINALS = (
    AllowedOriginsDocument,
    FormPluginConfigDocument,
    CouponCodeDocument,
    PriceSuggestion,
    UserFeedbackDocument,
    FlowEventDocument,
    RateLimitCounterDocument,
)

for _original in ORIGINALS:
    # set up with the application's Beanie documents: this module is imported
    # at collection, before the session starts the app
    entity(_original)


# -- the repositories of the dual run, over the originals ----------------------------


class AllowedOriginsRepository:
    """The Mongo repository of ``allowed_origins`` before 4.1."""

    async def list_origins(self) -> List[str]:
        return [doc.origin for doc in await AllowedOriginsDocument.find().to_list()]

    async def find_by_origin(self, origin: str) -> Optional[AllowedOriginsDocument]:
        return await AllowedOriginsDocument.find_one({"origin": origin})

    @write_op(replay=True)
    async def add(self, origin: str) -> AllowedOriginsDocument:
        return await AllowedOriginsDocument(origin=origin).save()

    @write_op
    async def delete_by_origin(self, origin: str) -> None:
        await AllowedOriginsDocument.find_one({"origin": origin}).delete()


class PostgresAllowedOriginsRepository(PostgresRepositoryBase):
    """Its Postgres twin before 4.1 (Beanie documents, through the bridge)."""

    row = AllowedOriginRow
    document = AllowedOriginsDocument

    async def list_origins(self) -> List[str]:
        return [doc.origin for doc in await self.many(order_by=(AllowedOriginRow.id,))]

    async def find_by_origin(self, origin: str) -> Optional[AllowedOriginsDocument]:
        return await self.one(AllowedOriginRow.origin == origin)

    async def add(self, origin: str) -> AllowedOriginsDocument:
        return await self.save_document(AllowedOriginsDocument(origin=origin))

    async def delete_by_origin(self, origin: str) -> None:
        await self.delete_one_where(AllowedOriginRow.origin == origin)


class RateLimitRepository:
    """The Mongo repository of ``rate_limit_counters`` before 4.1. Its
    Postgres side is ``PostgresRateLimitRepository`` as it is: ``hit`` runs
    on each store, nothing is replayed."""

    @write_op
    async def hit(
        self, counter_id: str, expires_at: dt.datetime, amount: int = 1
    ) -> int:
        now = utcnow()
        collection = RateLimitCounterDocument.get_pymongo_collection()
        counter = await collection.find_one_and_update(
            {"_id": ObjectId(counter_id)},
            {
                "$inc": {"hits": amount},
                "$set": {"updated_at": now},
                "$setOnInsert": {"expires_at": expires_at, "created_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
            projection={"hits": 1},
        )
        return int(counter["hits"])
