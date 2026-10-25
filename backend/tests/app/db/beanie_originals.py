"""The Beanie document classes of the groups that moved to ``Record``, frozen
as they were before the move (test support; removed together with Beanie).

* They are the reference of the wire check in ``test_record_codec_golden.py``:
  the ``Record`` classes now in ``backend.app.schemas`` must describe (JSON
  schema) and serialise every pinned document exactly as these did.
* They still name the 4.0 collections, so the tests of the migration and
  routing machinery keep exercising ``allowed_origins``,
  ``rate_limit_counters``, ``forms``, ``form_templates`` and the responder
  groups and workspace tags of ``responses`` (the last routed group, the
  routed fixture of ``tests/app/migrate/routed.py``) through the repositories
  below, as they were before the move, and plant 4.0 documents
  (``workspaces``, ``form_responses``) in Mongo for the import's tests.
"""

import datetime as dt
import re
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, Set, Union

from beanie import Indexed, PydanticObjectId
from bson import ObjectId
from common.clock import utcnow
from common.configs.mongo_document import MongoDocument
from common.db import (
    PostgresRepositoryBase,
    derived_object_id,
    to_bson_dict,
    write_op,
)
from common.models.consent import Consent
from common.models.standard_form import (
    ParameterValue,
    StandardForm,
    StandardFormResponse,
)
from common.enums.workspace_invitation_status import InvitationStatus
from pydantic import BaseModel, EmailStr, Field, field_validator
import pymongo
from pymongo import IndexModel, ReturnDocument

from backend.app.handlers.database import entity
from backend.app.models.enum.coupon_status import CouponStatus
from backend.app.models.form_plugin_config import FormProviderConfigDto
from backend.app.models.types.coupon_code import CouponCode
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.enum.workspace_roles import WorkspaceRoles
from backend.app.models.dtos.media_libraries_dto import MediaLibrary
from backend.app.models.enum.update_status import UpdateStatus
from backend.app.models.template import StandardFormTemplate
from backend.app.models.workspace import Workspace, WorkspaceFormSettings
from backend.app.schemas.form_import import ImportStatus, PageAnalysis
from backend.app.schemas.responder_group import GroupRoles, IdentifierType
from backend.app.schemas.standard_form_response import (
    DeclineReason,
    DeletionRequestClosure,
    DeletionRequestStatus,
)
from backend.app.schemas.action_document import ActionSettings
from backend.app.schemas.scim import ScimUserState
from backend.app.schemas.sso_connection import SsoConnectionStatus, SsoConnectionType
from backend.app.schemas.workspace_domain import DomainStatus
from backend.app.schemas.workspace_user import DISABLED_BY_PLAN
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.response_group_dto import ResponderGroupDto
from backend.app.repositories.postgres.forms import _oid, apply_form_update
from backend.app.services.form_concurrency import (
    ensure_not_changed_since,
    form_changed,
    next_updated_at,
)
from backend.db.models import (
    AllowedOriginRow,
    FormRow,
    FormTemplateRow,
    ResponderGroupFormRow,
    ResponderGroupMemberRow,
    ResponderGroupRow,
)
from beanie.odm.utils.dump import get_dict
from beanie.odm.utils.parsing import parse_obj
from common.db import from_row_doc
from common.db.beanie_bridge import row_values as bridge_row_values
from sqlalchemy import select, update

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


# -- identity --------------------------------------------------------------------


def _utc(value: Optional[dt.datetime]) -> Optional[dt.datetime]:
    # Mongo hands datetimes back without a zone; they are UTC
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


class UserTags(BaseModel):
    user_id: PydanticObjectId
    tags: List[UserTagType]



class WorkspaceDocument(MongoDocument, Workspace):
    """
    WorkspaceDocument is a subclass of both MongoDocument and Workspace.
    It represents a collection of workspaces stored in a MongoDB database.

    Attributes:
        workspace_name (str): The name of the workspace. This field is
            indexed and unique.
        custom_domain (str, optional): The custom domain of the workspace.
            This field is indexed.
        default (bool): A flag indicating whether the workspace is the
            default workspace. Defaults to False.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    workspace_name: Annotated[str, Indexed(unique=True)]
    custom_domain: Optional[Annotated[str, Indexed()]] = None
    default: bool = False
    owner_id: Optional[str] = None
    custom_domain_disabled: Optional[bool] = False
    custom_domain_verified: Optional[bool] = False
    disabled: Optional[bool] = False

    class Settings:
        name = "workspaces"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


class WorkspaceUserDocument(MongoDocument):
    """
    WorkspaceUsers is a subclass of MongoDocument. It represents a
    collection of users in a workspace stored in a MongoDB database.

    Attributes:
        workspace_id (PydanticObjectId): The ID of the workspace.
        userId (PydanticObjectId): The ID of the user.
        roles (List[WorkspaceRoles | str]): The member's roles. ``[]`` (the
            default, memberships from before roles existed) is an Editor. A
            role this code doesn't know is kept as a string and grants
            nothing (backend.app.services.authorization_service), so a
            membership with a newer role still loads after a rollback.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for
                specific data types.
    """

    workspace_id: PydanticObjectId
    user_id: PydanticObjectId
    roles: List[Union[WorkspaceRoles, str]] = []
    disabled: bool = False
    # who created the membership when not an invitation: "sso" (a first
    # single sign-on, just in time) or "scim" (the workspace's directory).
    # A "scim" membership's role and status follow the directory while the
    # workspace has one (docs/sso.md, "Directory sync"); None = by hand.
    provisioned_by: Optional[str] = None
    # Why the membership is disabled: "plan" (the owner's plan was
    # downgraded), "directory" (the SCIM directory deactivated the user).
    # Each path lifts only its own reason; the membership is enabled again
    # once none is left. A disabled membership from before this field has
    # none recorded and counts as "plan" (the only path that disabled
    # members then).
    disabled_reasons: List[str] = []

    def disable_for(self, reason: str) -> bool:
        """Disable for ``reason``; whether anything changed."""
        if self.disabled and not self.disabled_reasons:
            # a legacy disabled row: the plan disabled it, keep that reason
            self.disabled_reasons = [DISABLED_BY_PLAN]
        changed = not self.disabled or reason not in self.disabled_reasons
        if reason not in self.disabled_reasons:
            self.disabled_reasons = [*self.disabled_reasons, reason]
        self.disabled = True
        return changed

    @property
    def holds_seat(self) -> bool:
        """Whether it counts toward the seat cap: every membership but one
        disabled only by the directory (a plan-disabled member comes back on
        upgrade without a seat check, so it keeps its seat; a legacy disabled
        row counts as plan)."""
        if not self.disabled or not self.disabled_reasons:
            return True
        return DISABLED_BY_PLAN in self.disabled_reasons

    def enable_for(self, reason: str) -> bool:
        """Lift ``reason``: enabled once no other reason is left. Whether
        anything changed. A membership disabled for other reasons only stays
        as it is."""
        if not self.disabled:
            return False
        reasons = list(self.disabled_reasons)
        if reason in reasons:
            reasons.remove(reason)
        elif reasons or reason != DISABLED_BY_PLAN:
            return False
        self.disabled_reasons = reasons
        self.disabled = bool(reasons)
        return True

    class Settings:
        name = "workspace_users"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


class WorkspaceUserInvitesDocument(MongoDocument):
    """
    WorkspaceUserInvitesDocument is a subclass of MongoDocument. It
    represents a collection of user invites for workspaces stored in
    a MongoDB database.

    Attributes:
        workspace_id (PydanticObjectId): The ID of the workspace.
        email (str): The email of the user being invited.
        invitation_status (InvitationStatus, optional): The status of the
            invitation. Defaults to InvitationStatus.PENDING.
        expiry (int): The expiration time of the invitation in seconds.
        invitation_token (str): The token for the invitation.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
            indexes (List[IndexModel]): A list of index models for the collection.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    workspace_id: PydanticObjectId
    email: str
    invitation_status: Optional[InvitationStatus] = InvitationStatus.PENDING
    # A role this code doesn't know loads as a string and grants nothing
    # once accepted (like workspace_users.roles).
    role: Optional[Union[WorkspaceRoles, str]] = WorkspaceRoles.COLLABORATOR
    # who sent it: accepting re-checks that they may still give the role
    invited_by: Optional[str] = None
    expiry: int
    invitation_token: str

    class Settings:
        name = "workspace_invites"
        indexes = [IndexModel([("workspace_id", 1), ("email", 1)], unique=True)]
        bson_encoders = {
            datetime: lambda o: datetime.isoformat(o),
        }


class WorkspaceAPIKeyDocument(MongoDocument):
    """A workspace-scoped API key (plan §2.5) — the credential MCP and the
    public API authenticate with.

    Only the SHA-256 of the token is stored; the full token is shown exactly
    once at creation. ``prefix`` (the first characters) is kept for display so
    a key can be recognized without being recoverable. Scopes gate what the
    key may do; ``created_by`` is the acting user for authorization checks.
    """

    workspace_id: PydanticObjectId
    name: str
    key_hash: Annotated[str, Indexed(unique=True)]
    prefix: str
    scopes: List[str] = []
    created_by: str
    revoked: bool = False
    # A key with responses:read gives an external AI client full, unredacted
    # answers; the admin who created it acknowledged that (#715).
    responses_read_acknowledged_by: Optional[str] = None
    responses_read_acknowledged_at: Optional[dt.datetime] = None
    last_used_at: Optional[dt.datetime] = None

    class Settings:
        name = "workspace_api_keys"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
        }


class WorkspaceDomainDocument(MongoDocument):
    """An email domain a workspace claims, proven by a DNS TXT record.

    ``verified_domain`` equals ``domain`` while the claim is verified and is
    unset otherwise; it is unique in both stores, so a domain is verified by
    at most one workspace and the first verification wins. Pending claims of
    the same domain by other workspaces can never verify while it is held.
    """

    workspace_id: PydanticObjectId
    domain: str  # canonical ASCII (punycode), lower case
    verification_token: str
    method: str = "dns_txt"
    status: DomainStatus = DomainStatus.PENDING
    verified_domain: Optional[str] = None
    created_by: str
    verified_at: Optional[dt.datetime] = None
    verified_by: Optional[str] = None
    last_checked_at: Optional[dt.datetime] = None
    # code of the last check's failure (dns_txt module constants), None on success
    last_check_error: Optional[str] = None
    # failed checks in a row; on a verified domain only those that found the
    # record missing or wrong count, not resolver timeouts or errors
    failed_checks: int = 0
    # set once a verified domain failed LOSS_AFTER_FAILED_CHECKS re-checks in a
    # row; it stays verified (no automatic transfer), a passing check clears it
    verification_lost_at: Optional[dt.datetime] = None

    @field_validator("verified_at", "last_checked_at", "verification_lost_at")
    @classmethod
    def _utc(cls, value: Optional[dt.datetime]) -> Optional[dt.datetime]:
        # Mongo hands datetimes back without a zone; they are UTC
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        name = "workspace_domains"
        indexes = [
            IndexModel([("workspace_id", 1), ("domain", 1)], unique=True),
            IndexModel([("domain", 1)]),
            IndexModel(
                [("verified_domain", 1)],
                unique=True,
                partialFilterExpression={"verified_domain": {"$type": "string"}},
            ),
            IndexModel([("status", 1), ("last_checked_at", 1)]),
        ]


class SsoConnectionDocument(MongoDocument):
    """A workspace's single sign-on connection: our reference to a connection
    held by Ory Polis (docs/sso.md).

    The Polis tenant is the workspace id, so everything Polis keeps for the
    workspace (SSO connections now, a SCIM directory later) hangs off the same
    tenant. Polis holds the IdP metadata and, for OIDC, the client secret;
    this document only names the connection and records its lifecycle. It
    applies to the workspace's verified email domains, never to others.

    At most one connection of a workspace is ``enabled`` at a time.
    """

    workspace_id: PydanticObjectId
    type: SsoConnectionType
    name: str
    status: SsoConnectionStatus = SsoConnectionStatus.DISABLED
    # Polis's identifiers: its connection clientID, tenant and product
    polis_client_id: str
    polis_tenant: str
    polis_product: str
    # what the admin gave, for display (never the OIDC client secret)
    idp_entity_id: Optional[str] = None
    metadata_url: Optional[str] = None
    oidc_discovery_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    # the checked endpoints of the OIDC discovery document (handed to Polis
    # as its metadata; re-checked before a test)
    oidc_endpoints: Optional[Dict[str, str]] = None
    created_by: str
    enabled_at: Optional[dt.datetime] = None
    enabled_by: Optional[str] = None
    disabled_at: Optional[dt.datetime] = None
    disabled_by: Optional[str] = None
    # the last "Test connection": a sign-in through the IdP that came back
    # with an address on one of the workspace's verified domains
    tested_at: Optional[dt.datetime] = None
    tested_by: Optional[str] = None
    last_test_at: Optional[dt.datetime] = None
    # code of the last test's failure, None when it passed
    last_test_error: Optional[str] = None
    # what a failed test saw, for the admin to diagnose it (docs/sso.md,
    # "Troubleshooting"); cleared by a passed test and a config change:
    # the domain of the address the IdP sent (never the address itself),
    # for ``sso_email_domain_not_allowed``
    last_test_domain: Optional[str] = None
    # the names of the claims the IdP sent (never their values)
    last_test_claims: Optional[List[str]] = None

    @field_validator(
        "enabled_at", "disabled_at", "tested_at", "last_test_at", mode="after"
    )
    @classmethod
    def _utc(cls, value: Optional[dt.datetime]) -> Optional[dt.datetime]:
        # Mongo hands datetimes back without a zone; they are UTC
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    @property
    def is_enabled(self) -> bool:
        return self.status == SsoConnectionStatus.ENABLED

    @property
    def is_tested(self) -> bool:
        return self.tested_at is not None and self.last_test_error is None

    class Settings:
        name = "sso_connections"
        indexes = [
            IndexModel([("workspace_id", 1), ("status", 1)]),
            IndexModel([("polis_client_id", 1)], unique=True),
        ]


class SsoUsedStateDocument(MongoDocument):
    """A single sign-on callback that was accepted, by the hash of its
    browser nonce (docs/sso.md): a state is accepted once. Kept until
    ``expires_at`` (well past the sign-in's own expiry)."""

    nonce_hash: str
    expires_at: dt.datetime

    @field_validator("expires_at", mode="after")
    @classmethod
    def _utc(cls, value: dt.datetime) -> dt.datetime:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        name = "sso_used_states"
        indexes = [
            IndexModel([("nonce_hash", 1)], unique=True),
            # Mongo drops a record once it expired; the Postgres twin deletes
            # expired rows on each claim
            IndexModel([("expires_at", 1)], expireAfterSeconds=0),
        ]


class ScimDirectoryDocument(MongoDocument):
    workspace_id: PydanticObjectId
    # Polis's identifiers: the directory id, its tenant (the workspace id)
    # and product
    polis_directory_id: str
    polis_tenant: str
    polis_product: str
    type: str
    name: str
    # the SCIM base URL the identity provider is configured with (not secret)
    scim_endpoint: str = ""
    # the secret Polis signs webhooks with, encrypted (Fernet,
    # AUTH_AES_HEX_KEY); never returned by the API or logged
    webhook_secret: str
    created_by: str
    rotated_at: Optional[dt.datetime] = None
    rotated_by: Optional[str] = None
    last_event_at: Optional[dt.datetime] = None
    last_event_type: Optional[str] = None
    last_resync_at: Optional[dt.datetime] = None
    last_resync_by: Optional[str] = None
    # counts of the last resync ({"users": n, "groups": n, "changed": n}),
    # or its error code
    last_resync_summary: Optional[Dict[str, Any]] = None
    last_resync_error: Optional[str] = None
    # a rotation could not delete the previous Polis directory: its token
    # may still be accepted by Polis until it is deleted (retried by the
    # owner and by every resync)
    stale_polis_directory_id: Optional[str] = None

    @field_validator("rotated_at", "last_event_at", "last_resync_at", mode="after")
    @classmethod
    def _zone(cls, value):
        return _utc(value)

    class Settings:
        name = "scim_directories"
        indexes = [
            IndexModel([("workspace_id", 1)], unique=True),
            IndexModel([("polis_directory_id", 1)], unique=True),
        ]


class ScimUserDocument(MongoDocument):
    directory_id: PydanticObjectId
    workspace_id: PydanticObjectId
    polis_user_id: str
    # lower-cased, as the identity provider sent it
    email: str
    active: bool = True
    deleted: bool = False
    # the account the email belongs to, once known
    user_id: Optional[str] = None
    state: ScimUserState = ScimUserState.PROVISIONED
    # why it is ignored or failed (a code from scim.reasons)
    reason: Optional[str] = None
    last_event_at: Optional[dt.datetime] = None
    # the directory was replaced in Polis (token rotation): this record waits
    # to be matched, by email, to the user the new directory sends
    replaced: bool = False

    @field_validator("last_event_at", mode="after")
    @classmethod
    def _zone(cls, value):
        return _utc(value)

    class Settings:
        name = "scim_users"
        indexes = [
            IndexModel([("directory_id", 1), ("polis_user_id", 1)], unique=True),
            IndexModel([("workspace_id", 1), ("email", 1)]),
            IndexModel([("directory_id", 1), ("state", 1)]),
        ]


class ScimGroupDocument(MongoDocument):
    directory_id: PydanticObjectId
    workspace_id: PydanticObjectId
    polis_group_id: str
    name: str
    # the workspace role members of this group get (one role per group), or
    # None for a group that maps to nothing
    role: Optional[str] = None
    role_changed_by: Optional[str] = None
    # replaced directory (token rotation): matched to the new one by name
    replaced: bool = False
    # why the owner should look at this group's mapping: "duplicate_name"
    # (after a rotation several previous groups had its name, so none was
    # matched and no role carried over)
    needs_review: Optional[str] = None
    # TODO(member-groups): map to a member group too once member groups exist
    # (docs/enterprise-access-model.md §3, step c)

    class Settings:
        name = "scim_groups"
        indexes = [
            IndexModel([("directory_id", 1), ("polis_group_id", 1)], unique=True),
        ]


class ScimGroupMemberDocument(MongoDocument):
    """``id`` is ``derived_object_id(group_id, scim_user_id)``: one row per
    pair, the same in both stores."""

    directory_id: PydanticObjectId
    group_id: PydanticObjectId
    scim_user_id: PydanticObjectId

    class Settings:
        name = "scim_group_members"
        indexes = [
            IndexModel([("group_id", 1)]),
            IndexModel([("scim_user_id", 1)]),
            IndexModel([("directory_id", 1)]),
        ]


class ScimEventDocument(MongoDocument):
    """An accepted webhook event, by the SHA-256 of (directory, type, data,
    signature time): Polis gives events no id, and resends the same signed
    request when it retries."""

    event_key: str
    directory_id: PydanticObjectId
    event_type: str
    expires_at: dt.datetime

    @field_validator("expires_at", mode="after")
    @classmethod
    def _zone(cls, value):
        return _utc(value)

    class Settings:
        name = "scim_events"
        indexes = [
            IndexModel([("event_key", 1)], unique=True),
            # Mongo drops a record once it expired; the Postgres twin deletes
            # expired rows on each claim
            IndexModel([("expires_at", 1)], expireAfterSeconds=0),
        ]


class BlackListedRefreshTokens(MongoDocument):
    token: str
    expiry: dt.datetime

    class Settings:
        name = "blacklisted_refresh_tokens"
        bson_encoders = {
            dt.datetime: lambda o: dt.datetime.isoformat(o),
            dt.date: lambda o: dt.date.isoformat(o),
            dt.time: lambda o: dt.time.isoformat(o),
        }


class SessionDocument(MongoDocument):
    """One signed-in browser session: created at every sign-in, named by the
    ``sid`` claim of the tokens issued for it.

    Access tokens are checked without a database read; the refresh path reads
    this document, so revoking it ends the session within one access-token
    lifetime. ``refresh_jti`` is the refresh token currently valid for the
    session (rotated on each explicit refresh); ``previous_refresh_jti`` is the
    one it replaced, accepted for a short grace period after ``rotated_at`` so
    parallel tabs do not trip reuse detection. Any other jti presented for the
    session is a replayed (stolen) token and revokes it.
    """

    user_id: Annotated[str, Indexed()]
    refresh_jti: str
    previous_refresh_jti: Optional[str] = None
    rotated_at: Optional[dt.datetime] = None
    last_refreshed_at: Optional[dt.datetime] = None
    expires_at: dt.datetime
    # proven at sign-in (see common.models.user.User.email_verified)
    email_verified: bool = False
    # how the session signed in: "sso" (enterprise single sign-on) or None
    # (OTP, Google). An SSO session never grants the platform-admin role.
    method: Optional[str] = None
    # "respondent": limited to answering forms of ``scope_workspace_id``; it
    # grants no workspace permissions (common.models.user.User.session_scope)
    scope: Optional[str] = None
    scope_workspace_id: Optional[str] = None
    user_agent: Optional[str] = None
    revoked_at: Optional[dt.datetime] = None
    revoke_reason: Optional[str] = None

    @field_validator(
        "rotated_at", "last_refreshed_at", "expires_at", "revoked_at", mode="after"
    )
    @classmethod
    def _utc(cls, value: Optional[dt.datetime]) -> Optional[dt.datetime]:
        # Mongo hands datetimes back naive (UTC); keep them comparable
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=dt.timezone.utc)
        return value

    class Settings:
        # native dates (no ISO-string encoders): expiry and revocation compare them
        name = "sessions"
        # Mongo drops a session once its refresh token has expired; the
        # Postgres twin deletes expired rows on the list/revoke paths
        # (``SessionRepository.delete_expired``).
        indexes = [IndexModel([("expires_at", 1)], expireAfterSeconds=0)]


class UserTagsDocument(MongoDocument, UserTags):  # UserTags as it was in 4.0 (below)
    class Settings:
        name = "user_tags"


# -- forms -------------------------------------------------------------------------


class FormDocument(MongoDocument, StandardForm):
    class Settings:
        name = "forms"
        bson_encoders = _ISO_ENCODERS


class FormVersionsDocument(MongoDocument, StandardForm):
    version: int
    form_id: str

    class Settings:
        name = "form_versions"
        bson_encoders = _ISO_ENCODERS
        indexes = [
            IndexModel(
                [("form_id", pymongo.DESCENDING), ("version", pymongo.DESCENDING)],
                unique=True,
            )
        ]


class FormTemplateDocument(StandardFormTemplate, MongoDocument):
    class Settings:
        name = "form_templates"
        bson_encoders = _ISO_ENCODERS


class WorkspaceFormDocument(MongoDocument):
    """
    WorkspaceForms is a subclass of MongoDocument. It represents a
    collection of forms in a workspace stored in a MongoDB database.

    Attributes:
        workspace_id (PydanticObjectId): The ID of the workspace.
        form_id (str): The ID of the form.
        settings (WorkspaceFormSettings): The settings for the form in the workspace.

    Classes Attributes:
        Collection:
            name (str): The name of the collection in the database.
        Settings:
            name (str): The name of the settings for this document.
            bson_encoders (dict): A dictionary of bson encoders for specific data types.
    """

    workspace_id: PydanticObjectId
    form_id: str
    user_id: str
    settings: Optional[WorkspaceFormSettings] = None
    last_update_status: Optional[UpdateStatus] = None

    class Settings:
        name = "workspace_forms"
        bson_encoders = _ISO_ENCODERS


class FormImportDocument(MongoDocument):
    """One import of an uploaded PDF or image into a draft form.

    Created with the draft form, so the uploaded original lives in the form's
    private storage folder and is deleted with the form. ``stages`` holds each
    finished stage's checkpoint, so a retried job resumes instead of redoing
    work. Nothing a respondent may have written on the uploaded document is
    ever stored here: only structure.
    """

    workspace_id: PydanticObjectId
    form_id: Optional[str] = None
    created_by: str
    status: str = ImportStatus.QUEUED
    stage: Optional[str] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    file_name: str
    content_type: str
    size_bytes: int
    sha256: str
    source_key: str
    page_count: Optional[int] = None
    pages: List[PageAnalysis] = []
    stages: Dict[str, Any] = {}
    report: Dict[str, Any] = {}
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    ai_consent: bool = False
    ai_consent_at: Optional[datetime] = None
    ai_consent_by: Optional[str] = None
    heartbeat_at: Optional[datetime] = None

    class Settings:
        name = "form_imports"


class MediaLibraryDocument(MongoDocument, MediaLibrary):
    class Settings:
        name = "media_libraries"
        bson_encoders = _ISO_ENCODERS


class WorkspaceConsentDocument(Consent, MongoDocument):
    workspace_id: Optional[PydanticObjectId] = None

    class Settings:
        name = "workspace_consent"
        bson_encoders = _ISO_ENCODERS


# -- responses -----------------------------------------------------------------------


class FormResponseDocument(MongoDocument, StandardFormResponse):
    workspace_id: Optional[PydanticObjectId] = None

    class Settings:
        name = "form_responses"
        bson_encoders = _ISO_ENCODERS


class FormResponseDeletionRequest(MongoDocument):
    form_id: str
    response_id: str
    provider: Optional[str] = None
    dataOwnerIdentifier: Optional[str] = None
    anonymous_identity: Optional[str] = None
    status: DeletionRequestStatus = DeletionRequestStatus.PENDING
    workspace_id: Optional[PydanticObjectId] = None
    deleted_at: Optional[str] = None
    closed_by: Optional[str] = None
    closed_at: Optional[dt.datetime] = None
    decline_reason: Optional[DeclineReason] = None
    closures: List[DeletionRequestClosure] = Field(default_factory=list)

    class Settings:
        name = "responses_deletion_requests"
        bson_encoders = _ISO_ENCODERS


class WorkspaceTags(MongoDocument):
    workspace_id: PydanticObjectId
    title: str

    class Settings:
        name = "workspace_tags"


class WorkspaceResponderDocument(MongoDocument):
    workspace_id: PydanticObjectId
    user_id: Optional[str] = None
    email: str
    tags: Optional[List[PydanticObjectId]] = None
    metadata: Optional[Dict[str, str]] = None

    class Settings:
        name = "workspace_responder"


class ResponderGroupDocument(MongoDocument):
    name: Optional[str] = None
    workspace_id: PydanticObjectId
    description: Optional[str] = None
    regex: Optional[str] = None

    class Settings:
        name = "responder_group"
        bson_encoders = _ISO_ENCODERS


class ResponderGroupMemberDocument(MongoDocument):
    group_id: PydanticObjectId
    identifier: str
    identifierType: IdentifierType = IdentifierType.EMAIL

    class Settings:
        name = "responder_group_member"
        bson_encoders = _ISO_ENCODERS


class ResponderGroupFormDocument(MongoDocument):
    group_id: PydanticObjectId
    form_id: str
    role: GroupRoles = GroupRoles.VIEW

    class Settings:
        name = "responder_group_form"
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
    WorkspaceDocument,
    WorkspaceUserDocument,
    WorkspaceUserInvitesDocument,
    WorkspaceAPIKeyDocument,
    WorkspaceDomainDocument,
    SsoConnectionDocument,
    SsoUsedStateDocument,
    ScimDirectoryDocument,
    ScimUserDocument,
    ScimGroupDocument,
    ScimGroupMemberDocument,
    ScimEventDocument,
    BlackListedRefreshTokens,
    SessionDocument,
    UserTagsDocument,
    FormDocument,
    FormVersionsDocument,
    FormTemplateDocument,
    WorkspaceFormDocument,
    FormImportDocument,
    MediaLibraryDocument,
    WorkspaceConsentDocument,
    FormResponseDocument,
    FormResponseDeletionRequest,
    WorkspaceTags,
    WorkspaceResponderDocument,
    ResponderGroupDocument,
    ResponderGroupMemberDocument,
    ResponderGroupFormDocument,
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


class FormRepository:
    """The Mongo repository of ``forms`` before 4.1: the writes the tests of
    the mirror machinery (tests/app/migrate) race and repair."""

    async def get_form_document_by_id(self, form_id: str):
        return await FormDocument.find_one({"form_id": form_id})

    @write_op
    async def save_form(self, form: FormDocument):
        return await form.save()

    @write_op(replay=True)
    async def create_form(self, form: StandardForm) -> FormDocument:
        return await FormDocument(**form.model_dump(mode="json")).save()

    @write_op
    async def delete_form(self, form_id: str):
        form = await FormDocument.find_one({"form_id": form_id})
        if not form:
            raise HTTPException(status_code=404, content="Form not found")
        return await form.delete()

    @write_op
    async def delete_forms(self, form_ids: List[str]):
        return await FormDocument.find({"form_id": {"$in": form_ids}}).delete()

    @write_op(replay=True)
    async def update_form_if_unchanged(
        self, form_id, form: StandardForm, expected_updated_at: datetime
    ):
        raw = await FormDocument.get_pymongo_collection().find_one(
            {"form_id": str(form_id)}
        )
        if raw is None:
            return None
        form_document = parse_obj(FormDocument, raw)
        ensure_not_changed_since(form_document.updated_at, expected_updated_at)
        apply_form_update(form_document, form)
        form_document.updated_at = next_updated_at(form_document.updated_at)
        result = await FormDocument.get_pymongo_collection().update_one(
            {"_id": raw["_id"], "updated_at": raw.get("updated_at")},
            {
                "$set": get_dict(
                    form_document,
                    to_db=True,
                    exclude={"_id"},
                    keep_nulls=FormDocument.get_settings().keep_nulls,
                )
            },
        )
        if result.matched_count == 0:
            raise form_changed()
        return form_document

    @write_op
    async def set_form_logo(self, form_id: str, logo: Optional[str]):
        await FormDocument.find_one({"form_id": str(form_id)}).update(
            {"$set": {"logo": logo}}
        )
        return await FormDocument.find_one({"form_id": str(form_id)})


class PostgresFormRepository(PostgresRepositoryBase):
    """Its Postgres twin before 4.1 (Beanie documents, through the bridge)."""

    row = FormRow
    document = FormDocument

    async def get_form_document_by_id(self, form_id: str):
        return await self.one(FormRow.form_id == form_id)

    async def save_form(self, form: FormDocument):
        form.updated_at = utcnow()
        return await self.upsert(form)

    async def create_form(self, form: StandardForm) -> FormDocument:
        return await self.save_document(FormDocument(**form.model_dump(mode="json")))

    async def delete_form(self, form_id: str):
        form = await self.one(FormRow.form_id == form_id)
        if not form:
            raise HTTPException(status_code=404, content="Form not found")
        return await self.delete_by_id(form.id)

    async def delete_forms(self, form_ids: List[str]):
        return await self.delete_where(FormRow.form_id.in_(form_ids))

    async def update_form_if_unchanged(
        self, form_id, form: StandardForm, expected_updated_at: datetime
    ):
        async with self._session() as session:
            found = (
                await session.execute(
                    select(FormRow.id, FormRow.doc, FormRow.updated_at)
                    .where(FormRow.form_id == str(form_id))
                    .order_by(FormRow.created_at, FormRow.id)
                    .limit(1)
                )
            ).one_or_none()
        if found is None:
            return None
        form_document = from_row_doc(FormDocument, found.doc)
        ensure_not_changed_since(form_document.updated_at, expected_updated_at)
        apply_form_update(form_document, form)
        form_document.updated_at = next_updated_at(form_document.updated_at)
        values = bridge_row_values(form_document)
        unchanged = (
            FormRow.updated_at.is_(None)
            if found.updated_at is None
            else FormRow.updated_at == found.updated_at
        )
        self._touch(FormRow, [found.id])
        async with self._session() as session, session.begin():
            result = await session.execute(
                update(FormRow)
                .where(FormRow.id == found.id, unchanged)
                .values(
                    {
                        FormRow.doc: values["doc"],
                        FormRow.updated_at: values["updated_at"],
                        FormRow.bc_source: values["bc_source"],
                        FormRow.bc_checksum: values["bc_checksum"],
                    }
                )
                .execution_options(synchronize_session=False)
            )
        if result.rowcount != 1:
            raise form_changed()
        return form_document

    async def set_form_logo(self, form_id: str, logo: Optional[str]):
        form_document = await self.one(FormRow.form_id == str(form_id))
        if form_document is None:
            return None
        form_document.logo = logo
        return await self.upsert(form_document)


class FormTemplateRepository:
    """The Mongo repository of ``form_templates`` before 4.1 (the writes the
    mirror tests use)."""

    async def get_template_by_id(self, template_id):
        return await FormTemplateDocument.find_one({"_id": template_id})

    @write_op(replay=True)
    async def create_new_template(
        self, workspace_id, template_body: StandardFormTemplate, user
    ):
        template = FormTemplateDocument(**template_body.model_dump(mode="json"))
        template.workspace_id = workspace_id
        template.created_by = user.id
        return await template.save()

    @write_op
    async def update_template(self, template_id, template_body: StandardFormTemplate):
        template = await FormTemplateDocument.find_one({"_id": template_id})
        _apply_template(template, template_body)
        return await template.save()


class PostgresFormTemplateRepository(PostgresRepositoryBase):
    """Its Postgres twin before 4.1 (Beanie documents, through the bridge)."""

    row = FormTemplateRow
    document = FormTemplateDocument

    async def get_template_by_id(self, template_id):
        return await self.one(FormTemplateRow.id == str(template_id))

    async def create_new_template(
        self, workspace_id, template_body: StandardFormTemplate, user
    ):
        template = FormTemplateDocument(**template_body.model_dump(mode="json"))
        template.workspace_id = workspace_id
        template.created_by = user.id
        return await self.save_document(template)

    async def update_template(self, template_id, template_body: StandardFormTemplate):
        template = await self.get_template_by_id(template_id)
        _apply_template(template, template_body)
        return await self.save_document(template)


def _apply_template(template, body: StandardFormTemplate) -> None:
    template.fields = body.fields
    template.settings = body.settings
    template.title = body.title
    template.description = body.description
    template.button_text = body.button_text
    template.logo = body.logo
    template.cover_image = body.cover_image


# -- responses: the Mongo repositories of the routed fixture ---------------------------


class WorkspaceRespondersRepository:
    """The Mongo repository of ``workspace_tags`` and ``workspace_responder``
    before 4.1 (the routed fixture of tests/app/migrate/routed.py)."""

    @write_op(replay=True)
    async def create_workspace_tag(self, workspace_id: PydanticObjectId, title: str):
        workspace_tag = await WorkspaceTags.find_one(
            {"workspace_id": workspace_id, "title": title}
        )
        if not workspace_tag:
            workspace_tag = WorkspaceTags(workspace_id=workspace_id, title=title)
        return await workspace_tag.save()

    async def get_workspace_tags(self, workspace_id: PydanticObjectId):
        return await WorkspaceTags.find({"workspace_id": workspace_id}).to_list()

    @write_op(replay=True)
    async def get_responder_by_email_and_workspace_id(
        self, workspace_id: PydanticObjectId, email: str
    ):
        workspace_responder = await WorkspaceResponderDocument.find_one(
            {"workspace_id": workspace_id, "email": email}
        )
        if not workspace_responder:
            workspace_responder = WorkspaceResponderDocument(
                workspace_id=workspace_id, email=email
            )
        return await workspace_responder.save()


class ResponderGroupsRepository:
    """The Mongo repository of the responder groups before 4.1 (the writes the
    routed fixture's tests use)."""

    @staticmethod
    def member(
        group_id: PydanticObjectId, identifier: str
    ) -> ResponderGroupMemberDocument:
        """A member's identity is the (group, identifier) pair; its id follows."""
        return ResponderGroupMemberDocument(
            id=derived_object_id("responder_group_member", group_id, identifier),
            group_id=group_id,
            identifier=identifier,
        )

    @staticmethod
    def link(group_id: PydanticObjectId, form_id: str) -> ResponderGroupFormDocument:
        return ResponderGroupFormDocument(
            id=derived_object_id("responder_group_form", group_id, form_id),
            group_id=group_id,
            form_id=form_id,
        )

    @write_op(replay=True)
    async def create_group(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        description: Optional[str] = None,
        regex: Optional[str] = None,
    ):
        return await ResponderGroupDocument(
            name=name, workspace_id=workspace_id, description=description, regex=regex
        ).save()

    @write_op
    async def update_group(
        self,
        workspace_id: PydanticObjectId,
        name: Optional[str] = None,
        description: Optional[str] = None,
        emails: List[EmailStr] = None,
        group_id: PydanticObjectId = None,
        regex: Optional[str] = None,
    ):
        responder_group = await ResponderGroupDocument.find_one(
            {"workspace_id": workspace_id, "_id": group_id}
        )
        if emails and len(emails) != 0:
            # replace the membership wholesale
            await ResponderGroupMemberDocument.find({"group_id": group_id}).delete()
            await ResponderGroupMemberDocument.insert_many(
                [self.member(group_id, email) for email in set(emails)]
            )
        if responder_group:
            if name:
                responder_group.name = name
            if description:
                responder_group.description = description
            responder_group.regex = regex
        return await responder_group.save()

    @write_op
    async def add_emails_to_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        emails = list(set(emails))
        existing = [
            m.identifier
            for m in await ResponderGroupMemberDocument.find(
                {"group_id": group_id, "identifier": {"$in": emails}}
            ).to_list()
        ]
        new_members = [self.member(group_id, e) for e in emails if e not in existing]
        if new_members:
            await ResponderGroupMemberDocument.insert_many(new_members)

    @write_op
    async def add_group_to_form(self, form_id: str, group_id: PydanticObjectId):
        existing = await ResponderGroupFormDocument.find_one(
            {"form_id": form_id, "group_id": group_id}
        )
        if not existing:
            return await self.link(group_id, form_id).save()

    async def get_emails_in_group(self, group_id: PydanticObjectId):
        members = await ResponderGroupMemberDocument.find(
            {"group_id": group_id}
        ).to_list()
        group = await ResponderGroupDocument.find_one({"_id": group_id})
        if group is None:
            return None
        return {"emails": [m.identifier for m in members], "name": group.name}


class PostgresResponderGroupsRepository(PostgresRepositoryBase):
    """The Postgres twin of the responder groups before 4.1 (Beanie documents,
    through the bridge): the routed fixture's twin."""

    row = ResponderGroupRow
    document = ResponderGroupDocument

    @staticmethod
    def member(
        group_id: PydanticObjectId, identifier: str
    ) -> ResponderGroupMemberDocument:
        return ResponderGroupMemberDocument(
            id=derived_object_id("responder_group_member", group_id, identifier),
            group_id=group_id,
            identifier=identifier,
        )

    @staticmethod
    def link(group_id: PydanticObjectId, form_id: str) -> ResponderGroupFormDocument:
        return ResponderGroupFormDocument(
            id=derived_object_id("responder_group_form", group_id, form_id),
            group_id=group_id,
            form_id=form_id,
        )

    async def _members(self, *where) -> List[ResponderGroupMemberDocument]:
        return await self.many(
            *where, row=ResponderGroupMemberRow, document=ResponderGroupMemberDocument
        )

    async def _links(self, *where) -> List[ResponderGroupFormDocument]:
        return await self.many(
            *where, row=ResponderGroupFormRow, document=ResponderGroupFormDocument
        )

    async def create_group(
        self,
        workspace_id: PydanticObjectId,
        name: str,
        description: Optional[str] = None,
        regex: Optional[str] = None,
    ):
        if description and len(description) > 280:
            return {"message": "description should be less than 280 characters"}
        return await self.save_document(
            ResponderGroupDocument(
                name=name,
                workspace_id=workspace_id,
                description=description,
                regex=regex,
            )
        )

    async def update_group(
        self,
        workspace_id: PydanticObjectId,
        name: Optional[str] = None,
        description: Optional[str] = None,
        emails: List[EmailStr] = None,
        group_id: PydanticObjectId = None,
        regex: Optional[str] = None,
    ):
        responder_group = await self.get_group_in_workspace(workspace_id, group_id)
        if emails and len(emails) != 0:
            await self.delete_where(
                ResponderGroupMemberRow.group_id == _oid(group_id),
                row=ResponderGroupMemberRow,
            )
            await self.upsert_many(
                [self.member(group_id, email) for email in set(emails)],
                row=ResponderGroupMemberRow,
            )
        if responder_group:
            if name:
                responder_group.name = name
            if description:
                responder_group.description = description
            responder_group.regex = regex
        return await self.save_document(responder_group)

    async def get_group_in_workspace(
        self, workspace_id: PydanticObjectId, group_id: PydanticObjectId
    ):
        return await self.one(
            ResponderGroupRow.workspace_id == _oid(workspace_id),
            ResponderGroupRow.id == _oid(group_id),
        )

    async def add_emails_to_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        emails = list(set(emails))
        existing = {
            member.identifier
            for member in await self._members(
                ResponderGroupMemberRow.group_id == _oid(group_id),
                ResponderGroupMemberRow.identifier.in_(emails),
            )
        }
        new_members = [self.member(group_id, e) for e in emails if e not in existing]
        if new_members:
            await self.upsert_many(new_members, row=ResponderGroupMemberRow)

    async def remove_emails_from_group(
        self, group_id: PydanticObjectId, emails: List[EmailStr]
    ):
        await self.delete_where(
            ResponderGroupMemberRow.group_id == _oid(group_id),
            ResponderGroupMemberRow.identifier.in_(list(emails)),
            row=ResponderGroupMemberRow,
        )

    async def _projected(self, groups: List[ResponderGroupDocument]) -> List[dict]:
        """The $project of get_emails_in_group / get_groups_in_workspace."""
        ids = [_oid(g.id) for g in groups]
        members = await self._members(ResponderGroupMemberRow.group_id.in_(ids))
        links = await self._links(ResponderGroupFormRow.group_id.in_(ids))
        out = []
        for group in groups:
            out.append(
                {
                    "_id": group.id,
                    "name": group.name,
                    "workspace_id": group.workspace_id,
                    "emails": [m.identifier for m in members if m.group_id == group.id],
                    "description": group.description,
                    "regex": group.regex,
                    "forms": [l.form_id for l in links if l.group_id == group.id],
                }
            )
        return out

    async def get_emails_in_group(self, group_id: PydanticObjectId):
        group = await self.one(ResponderGroupRow.id == _oid(group_id))
        if group is None:
            return None
        return (await self._projected([group]))[0]

    async def remove_responder_group(self, group_id: PydanticObjectId):
        await self.delete_by_id(group_id)
        await self.delete_where(
            ResponderGroupMemberRow.group_id == _oid(group_id),
            row=ResponderGroupMemberRow,
        )
        await self.delete_where(
            ResponderGroupFormRow.group_id == _oid(group_id), row=ResponderGroupFormRow
        )

    async def get_groups_in_workspace(self, workspace_id: PydanticObjectId):
        groups = await self.many(ResponderGroupRow.workspace_id == _oid(workspace_id))
        return [ResponderGroupDto(**row) for row in await self._projected(groups)]

    async def get_groups_by_form_ids(
        self, form_ids: List[str]
    ) -> Dict[str, List[dict]]:
        links = await self._links(ResponderGroupFormRow.form_id.in_(list(form_ids)))
        groups = {
            group.id: to_bson_dict(group)
            for group in await self.many(
                ResponderGroupRow.id.in_([_oid(l.group_id) for l in links] or ["-"])
            )
        }
        by_form: Dict[str, List[dict]] = {form_id: [] for form_id in form_ids}
        for link in links:
            if link.group_id in groups:
                by_form.setdefault(link.form_id, []).append(groups[link.group_id])
        return by_form

    async def get_form_ids_accessible_to(
        self,
        form_ids: List[str],
        identifier: str,
        workspace_id: Optional[PydanticObjectId] = None,
    ) -> Set[str]:
        """The subset of ``form_ids`` whose responder groups admit
        ``identifier``: a member with that identifier in any of the form's
        groups, or a regex it matches of one of ``workspace_id``'s groups (any
        group's when None), as 4.0's listing did."""
        links = await self._links(ResponderGroupFormRow.form_id.in_(list(form_ids)))
        group_ids = [_oid(g) for g in {link.group_id for link in links}]
        if not group_ids:
            return set()
        member_of = {
            member.group_id
            for member in await self._members(
                ResponderGroupMemberRow.group_id.in_(group_ids),
                ResponderGroupMemberRow.identifier == identifier,
            )
        }
        for group in await self.many(ResponderGroupRow.id.in_(group_ids)):
            if not group.regex:
                continue
            if workspace_id is not None and str(group.workspace_id) != str(workspace_id):
                continue
            try:
                if re.search(group.regex, identifier):
                    member_of.add(group.id)
            except re.error:
                continue
        return {link.form_id for link in links if link.group_id in member_of}

    async def add_group_to_form(self, form_id: str, group_id: PydanticObjectId):
        existing = await self._links(
            ResponderGroupFormRow.form_id == form_id,
            ResponderGroupFormRow.group_id == _oid(group_id),
        )
        if not existing:
            return await self.save_document(
                self.link(group_id, form_id), row=ResponderGroupFormRow
            )

    async def add_groups_to_form(self, form_id: str, group_ids: List[PydanticObjectId]):
        ids_to_add = list(group_ids)
        existing_groups = await self._links(ResponderGroupFormRow.form_id == form_id)
        ids_to_remove = [group.group_id for group in existing_groups]
        for group_id in list(ids_to_remove):
            if group_id in ids_to_add:
                ids_to_remove.remove(group_id)
                ids_to_add.remove(group_id)
        for group_id in ids_to_remove:
            await self.remove_group_from_form(form_id, group_id)
        for group_id in ids_to_add:
            await self.add_group_to_form(form_id, group_id)
        return await self._links(ResponderGroupFormRow.form_id == form_id)

    async def remove_group_from_form(self, form_id: str, group_id: PydanticObjectId):
        await self.delete_one_where(
            ResponderGroupFormRow.form_id == form_id,
            ResponderGroupFormRow.group_id == _oid(group_id),
            row=ResponderGroupFormRow,
        )

    async def delete_workspace_form_groups(self, form_id: str):
        await self.delete_where(
            ResponderGroupFormRow.form_id == form_id, row=ResponderGroupFormRow
        )

    async def delete_responder_groups(self, workspace_ids: List[PydanticObjectId]):
        groups = await self.many(
            ResponderGroupRow.workspace_id.in_([_oid(w) for w in workspace_ids])
        )
        group_ids = [_oid(group.id) for group in groups] or ["-"]
        await self.delete_where(
            ResponderGroupFormRow.group_id.in_(group_ids), row=ResponderGroupFormRow
        )
        await self.delete_where(
            ResponderGroupMemberRow.group_id.in_(group_ids), row=ResponderGroupMemberRow
        )
        await self.delete_where(ResponderGroupRow.id.in_(group_ids))
