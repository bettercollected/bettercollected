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
from typing import Annotated, Any, Dict, List, Optional

from beanie import Indexed, PydanticObjectId
from bson import ObjectId
from common.clock import utcnow
from common.configs.mongo_document import MongoDocument
from common.db import PostgresRepositoryBase, write_op
from common.models.standard_form import ParameterValue
from pydantic import EmailStr, field_validator
from pymongo import ReturnDocument

from backend.app.handlers.database import entity
from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.models.types.coupon_code import CouponCode
from backend.app.schemas.action_document import ActionSettings
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


# -- ai --------------------------------------------------------------------------

_DATETIME_ISO = {dt.datetime: lambda o: dt.datetime.isoformat(o)}


class UserAIPreferenceMemoryDocument(MongoDocument):
    """The AI's memory of how ONE creator likes forms, in ONE workspace
    (plan §2.4) — a living document the user owns.

    One fact per entry ("prefers pages under 5 questions", "titles in
    sentence case"), extracted from AI sessions or added by hand, each with a
    timestamp and source. Injected at the LOWEST precedence: the user's
    request and the org profile always override. Deliberately not embeddings —
    the user can read, edit and delete every line.
    """

    workspace_id: PydanticObjectId
    user_id: str
    entries: List[Dict[str, Any]] = []
    learn_preferences: bool = False
    learn_preferences_at: Optional[dt.datetime] = None

    class Settings:
        name = "ai_preference_memories"
        bson_encoders = _DATETIME_ISO


class FormAISessionDocument(MongoDocument):
    """One AI form-editing conversation (plan §2.2).

    Powers chat history for context, per-workspace usage accounting, and the
    preference-memory extraction later (P1.7). Messages hold role/content plus
    the ops the assistant applied and their results — the auditable record of
    what the AI actually changed.
    """

    workspace_id: PydanticObjectId
    form_id: str
    user_id: str
    provider: Optional[str] = None
    messages: List[Dict[str, Any]] = []

    class Settings:
        name = "form_ai_sessions"
        bson_encoders = _DATETIME_ISO


class FormAIInsightDocument(MongoDocument):
    """Cached AI summary of a form's responses (plan §2 'response summaries',
    phase P3). One document per form, replaced on each regeneration.

    Exists so viewing insights is free after the one explicit, creator-
    triggered generation — the AI reads respondent data ONLY at that moment,
    never in the background.
    """

    workspace_id: PydanticObjectId
    form_id: str
    payload: Dict[str, Any]
    response_count: int
    total_responses: int
    generated_by: Optional[str] = None
    generated_at: dt.datetime

    class Settings:
        name = "form_ai_insights"
        bson_encoders = _DATETIME_ISO


class WorkspaceAIProfileDocument(MongoDocument):
    """The workspace's AI profile — the org context every AI call is grounded
    in (see plans/ai-native-form-builder.md §2.3).

    Three plain-markdown sections, deliberately a visible document the
    workspace owns rather than hidden embeddings:
    - ``about``      — tone of voice, audience, languages, vocabulary
    - ``guidelines`` — dos/don'ts for forms
    - ``compliance`` — hard requirements (injected with elevated wording;
                       the AI must not violate these even if asked)

    ``revisions`` keeps the last few versions — it's a policy document, so
    auditability matters more than storage.
    """

    workspace_id: Annotated[PydanticObjectId, Indexed(unique=True)]
    about: str = ""
    guidelines: str = ""
    compliance: str = ""
    updated_by: Optional[str] = None
    revisions: List[Dict[str, Any]] = []

    class Settings:
        name = "workspace_ai_profiles"
        bson_encoders = _DATETIME_ISO


class MCPAuditLogDocument(MongoDocument):
    """Every MCP tool call, auditable (plan §2.5): which key did what, when,
    and whether it succeeded. Pairs with the trust story — external AI access
    is visible, not implied."""

    workspace_id: PydanticObjectId
    key_id: str
    tool: str
    ok: bool
    detail: Optional[str] = None
    at: dt.datetime

    class Settings:
        name = "mcp_audit_logs"
        bson_encoders = _DATETIME_ISO


class CreateFormPrompt(MongoDocument):
    prompt: str
    openai_response: Dict[str, Any]
    created_form: Dict[str, Any]
    form_id: PydanticObjectId

    class Settings:
        name = "create_form_prompts"
        bson_encoders = _ISO_ENCODERS


class ApiIdempotencyRecordDocument(MongoDocument):
    """One ``Idempotency-Key`` an API key sent to the public API
    (services/idempotency.py): the request it was first used for and, once
    that finished, a summary of its response, from which a retry with the
    same key is answered.

    The id is derived from the API key's id and the client's key, so a key
    is claimed by inserting it. Kept until ``expires_at`` (24 hours)."""

    key_id: str
    request_hash: str
    state: str = "pending"
    status_code: Optional[int] = None
    body: Optional[str] = None
    etag: Optional[str] = None
    expires_at: dt.datetime

    @field_validator("expires_at", mode="after")
    @classmethod
    def _utc(cls, value: dt.datetime) -> dt.datetime:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        name = "api_idempotency_keys"


# -- actions ---------------------------------------------------------------------


class ActionDocument(MongoDocument):
    name: str
    title: Optional[str] = None
    description: Optional[str] = None
    action_code: str
    created_by: PydanticObjectId
    parameters: Optional[List[ParameterValue]] = None
    secrets: Optional[List[ParameterValue]] = None
    type: Optional[str] = None
    predefined: Optional[bool] = None
    url: Optional[str] = None

    class Settings:
        name = "actions"
        bson_encoders = _ISO_ENCODERS


class WorkspaceActionsDocument(MongoDocument):
    workspace_id: PydanticObjectId
    action_id: PydanticObjectId
    settings: Optional[ActionSettings] = ActionSettings()
    parameters: Optional[List[ParameterValue]] = None
    secrets: Optional[List[ParameterValue]] = None

    class Settings:
        name = "workspace_actions"
        bson_encoders = _ISO_ENCODERS


ORIGINALS = (
    AllowedOriginsDocument,
    FormPluginConfigDocument,
    CouponCodeDocument,
    PriceSuggestion,
    UserFeedbackDocument,
    FlowEventDocument,
    RateLimitCounterDocument,
    UserAIPreferenceMemoryDocument,
    FormAISessionDocument,
    FormAIInsightDocument,
    WorkspaceAIProfileDocument,
    MCPAuditLogDocument,
    CreateFormPrompt,
    ApiIdempotencyRecordDocument,
    ActionDocument,
    WorkspaceActionsDocument,
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
