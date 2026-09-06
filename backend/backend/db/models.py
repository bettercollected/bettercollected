"""One table per Mongo collection: typed spine columns + the ``doc`` body.

Spine columns are what the code filters, joins, sorts or requires unique on
(measured from the repositories); everything else stays inside ``doc``.
Indexes mirror the Mongo ``IndexModel``s plus the join keys. Two constraints
Mongo does not enforce today (``workspace_forms`` per workspace+form,
``workspace_users`` per workspace+user) are plain indexes here until the
migration preflight has proven the data is duplicate-free.
"""

from __future__ import annotations

from sqlalchemy import Index, UniqueConstraint, text

from backend.db.base import S, Base
from common.db import BaseRow, MirrorWriteFailureMixin


class WorkspaceRow(Base, BaseRow):
    __tablename__ = "workspaces"
    workspace_name = S.text("workspace_name")
    custom_domain = S.text("custom_domain")
    owner_id = S.text("owner_id")
    is_default = S.bool("default", name="is_default")
    disabled = S.bool("disabled")
    custom_domain_verified = S.bool("custom_domain_verified")
    __table_args__ = (
        UniqueConstraint("workspace_name"),
        Index(
            "uq_workspaces_custom_domain",
            "custom_domain",
            unique=True,
            postgresql_where=text("custom_domain IS NOT NULL"),
        ),
        Index(None, "owner_id"),
    )


class WorkspaceUserRow(Base, BaseRow):
    __tablename__ = "workspace_users"
    workspace_id = S.text("workspace_id")
    user_id = S.text("user_id")
    disabled = S.bool("disabled")
    __table_args__ = (
        Index("ix_workspace_users_workspace_user", "workspace_id", "user_id"),
        Index(None, "user_id"),
    )


class WorkspaceInviteRow(Base, BaseRow):
    __tablename__ = "workspace_invites"
    workspace_id = S.text("workspace_id")
    email = S.text("email")
    invitation_token = S.text("invitation_token")
    invitation_status = S.text("invitation_status")
    role = S.text("role")
    expiry = S.int("expiry")
    __table_args__ = (
        UniqueConstraint("workspace_id", "email"),
        Index(None, "invitation_token"),
    )


class WorkspaceApiKeyRow(Base, BaseRow):
    __tablename__ = "workspace_api_keys"
    workspace_id = S.text("workspace_id")
    key_hash = S.text("key_hash")
    prefix = S.text("prefix")
    created_by = S.text("created_by")
    revoked = S.bool("revoked")
    __table_args__ = (UniqueConstraint("key_hash"), Index(None, "workspace_id"))


class BlacklistedRefreshTokenRow(Base, BaseRow):
    __tablename__ = "blacklisted_refresh_tokens"
    token = S.text("token")
    expiry = S.ts("expiry")
    __table_args__ = (Index(None, "token"), Index(None, "expiry"))


class UserTagsRow(Base, BaseRow):
    __tablename__ = "user_tags"
    user_id = S.text("user_id")
    __table_args__ = (Index(None, "user_id"),)


class FormRow(Base, BaseRow):
    __tablename__ = "forms"
    form_id = S.text("form_id")
    imported_form_id = S.text("imported_form_id")
    title = S.text("title")
    type = S.text("type")
    builder_version = S.text("builder_version")
    provider = S.text("settings", "provider")
    custom_url = S.text("settings", "custom_url")
    published_at = S.ts("published_at")
    __table_args__ = (
        UniqueConstraint("form_id"),
        Index(None, "imported_form_id"),
        Index(None, "custom_url"),
    )


class FormVersionRow(Base, BaseRow):
    __tablename__ = "form_versions"
    form_id = S.text("form_id")
    version = S.int("version")
    imported_form_id = S.text("imported_form_id")
    __table_args__ = (UniqueConstraint("form_id", "version"),)


class FormTemplateRow(Base, BaseRow):
    __tablename__ = "form_templates"
    workspace_id = S.text("workspace_id")
    category = S.text("category")
    created_by = S.text("created_by")
    imported_from = S.text("imported_from")
    type = S.text("type")
    __table_args__ = (Index(None, "workspace_id"), Index(None, "category"))


class WorkspaceFormRow(Base, BaseRow):
    __tablename__ = "workspace_forms"
    workspace_id = S.text("workspace_id")
    form_id = S.text("form_id")
    user_id = S.text("user_id")
    custom_url = S.text("settings", "custom_url")
    private = S.bool("settings", "private")
    hidden = S.bool("settings", "hidden")
    pinned = S.bool("settings", "pinned")
    __table_args__ = (
        Index("ix_workspace_forms_workspace_form", "workspace_id", "form_id"),
        Index(None, "form_id"),
        Index("ix_workspace_forms_workspace_custom_url", "workspace_id", "custom_url"),
    )


class MediaLibraryRow(Base, BaseRow):
    __tablename__ = "media_libraries"
    workspace_id = S.text("workspace_id")
    media_name = S.text("media_name")
    media_type = S.text("media_type")
    s3_key = S.text("s3_key")
    __table_args__ = (Index(None, "workspace_id"),)


class WorkspaceConsentRow(Base, BaseRow):
    __tablename__ = "workspace_consent"
    workspace_id = S.text("workspace_id")
    __table_args__ = (Index(None, "workspace_id"),)


class SchedulerFormConfigRow(Base, BaseRow):
    __tablename__ = "scheduler_form_configs"
    form_id = S.text("form_id")
    workspace_id = S.text("workspace_id")
    provider = S.text("provider")
    imported_at = S.ts("imported_at")
    __table_args__ = (Index(None, "form_id"), Index(None, "workspace_id"))


class FormResponseRow(Base, BaseRow):
    __tablename__ = "form_responses"
    form_id = S.text("form_id")
    response_id = S.text("response_id")
    submission_uuid = S.text("submission_uuid")
    provider = S.text("provider")
    data_owner_identifier = S.text("dataOwnerIdentifier", name="data_owner_identifier")
    anonymous_identity = S.text("anonymous_identity")
    form_version = S.int("form_version")
    expiration = S.text("expiration")
    expiration_type = S.text("expiration_type")
    state = S.text("state")
    __table_args__ = (
        UniqueConstraint("response_id"),
        Index("ix_form_responses_form_created", "form_id", "created_at"),
        Index(None, "submission_uuid"),
        Index(None, "data_owner_identifier"),
        Index(None, "anonymous_identity"),
        Index(None, "expiration"),
    )


class ResponseDeletionRequestRow(Base, BaseRow):
    __tablename__ = "responses_deletion_requests"
    form_id = S.text("form_id")
    response_id = S.text("response_id")
    provider = S.text("provider")
    status = S.text("status")
    data_owner_identifier = S.text("dataOwnerIdentifier", name="data_owner_identifier")
    anonymous_identity = S.text("anonymous_identity")
    __table_args__ = (
        # Mongo's unique index treats a missing provider as one value; NULLS NOT DISTINCT keeps that.
        UniqueConstraint(
            "form_id", "response_id", "provider", postgresql_nulls_not_distinct=True
        ),
        Index(None, "status"),
    )


class WorkspaceResponderRow(Base, BaseRow):
    __tablename__ = "workspace_responder"
    workspace_id = S.text("workspace_id")
    user_id = S.text("user_id")
    email = S.text("email")
    __table_args__ = (
        Index("ix_workspace_responder_workspace_email", "workspace_id", "email"),
    )


class WorkspaceTagRow(Base, BaseRow):
    __tablename__ = "workspace_tags"
    workspace_id = S.text("workspace_id")
    title = S.text("title")
    __table_args__ = (Index(None, "workspace_id"),)


class ResponderGroupRow(Base, BaseRow):
    __tablename__ = "responder_group"
    workspace_id = S.text("workspace_id")
    name = S.text("name")
    __table_args__ = (Index(None, "workspace_id"),)


class ResponderGroupFormRow(Base, BaseRow):
    __tablename__ = "responder_group_form"
    group_id = S.text("group_id")
    form_id = S.text("form_id")
    role = S.text("role")
    __table_args__ = (Index(None, "group_id"), Index(None, "form_id"))


class ResponderGroupMemberRow(Base, BaseRow):
    __tablename__ = "responder_group_member"
    group_id = S.text("group_id")
    identifier = S.text("identifier")
    identifier_type = S.text("identifierType", name="identifier_type")
    __table_args__ = (
        Index("ix_responder_group_member_group_identifier", "group_id", "identifier"),
    )


class ActionRow(Base, BaseRow):
    __tablename__ = "actions"
    name = S.text("name")
    created_by = S.text("created_by")
    type = S.text("type")
    predefined = S.bool("predefined")
    __table_args__ = (Index(None, "created_by"), Index(None, "name"))


class WorkspaceActionRow(Base, BaseRow):
    __tablename__ = "workspace_actions"
    workspace_id = S.text("workspace_id")
    action_id = S.text("action_id")
    __table_args__ = (
        Index("ix_workspace_actions_workspace_action", "workspace_id", "action_id"),
    )


class AiPreferenceMemoryRow(Base, BaseRow):
    __tablename__ = "ai_preference_memories"
    workspace_id = S.text("workspace_id")
    user_id = S.text("user_id")
    __table_args__ = (
        Index("ix_ai_preference_memories_workspace_user", "workspace_id", "user_id"),
    )


class FormAiSessionRow(Base, BaseRow):
    __tablename__ = "form_ai_sessions"
    workspace_id = S.text("workspace_id")
    form_id = S.text("form_id")
    user_id = S.text("user_id")
    provider = S.text("provider")
    __table_args__ = (
        Index(
            "ix_form_ai_sessions_workspace_form_user",
            "workspace_id",
            "form_id",
            "user_id",
        ),
    )


class FormAiInsightRow(Base, BaseRow):
    __tablename__ = "form_ai_insights"
    workspace_id = S.text("workspace_id")
    form_id = S.text("form_id")
    generated_at = S.ts("generated_at")
    __table_args__ = (
        Index("ix_form_ai_insights_workspace_form", "workspace_id", "form_id"),
    )


class WorkspaceAiProfileRow(Base, BaseRow):
    __tablename__ = "workspace_ai_profiles"
    workspace_id = S.text("workspace_id")
    __table_args__ = (UniqueConstraint("workspace_id"),)


class McpAuditLogRow(Base, BaseRow):
    __tablename__ = "mcp_audit_logs"
    workspace_id = S.text("workspace_id")
    key_id = S.text("key_id")
    tool = S.text("tool")
    ok = S.bool("ok")
    at = S.ts("at")
    __table_args__ = (Index("ix_mcp_audit_logs_workspace_at", "workspace_id", "at"),)


class CreateFormPromptRow(Base, BaseRow):
    __tablename__ = "create_form_prompts"
    form_id = S.text("form_id")
    __table_args__ = (Index(None, "form_id"),)


class FormFlowEventRow(Base, BaseRow):
    __tablename__ = "form_flow_events"
    form_id = S.text("form_id")
    session_id = S.text("session_id")
    from_page = S.text("from_page")
    to_page = S.text("to_page")
    __table_args__ = (
        Index(None, "form_id"),
        Index(None, "session_id"),
        Index(None, "created_at"),
    )


class AllowedOriginRow(Base, BaseRow):
    __tablename__ = "allowed_origins"
    origin = S.text("origin")
    __table_args__ = (Index(None, "origin"),)


class FormPluginConfigRow(Base, BaseRow):
    __tablename__ = "forms_plugin_configs"
    provider_name = S.text("provider_name")
    enabled = S.bool("enabled")
    __table_args__ = (Index(None, "provider_name"),)


class CouponCodeRow(Base, BaseRow):
    __tablename__ = "coupon_codes"
    code = S.text("code")
    status = S.text("status")
    used_by = S.text("used_by")
    __table_args__ = (UniqueConstraint("code"),)


class PriceSuggestionRow(Base, BaseRow):
    __tablename__ = "price_suggestion"
    user_id = S.text("user_id")
    email = S.text("email")
    __table_args__ = (Index(None, "user_id"),)


class UserFeedbackRow(Base, BaseRow):
    __tablename__ = "user_feedback"


class MirrorWriteFailure(Base, MirrorWriteFailureMixin):
    __tablename__ = "mirror_write_failures"


ROW_MODELS = [cls for cls in Base.__subclasses__() if issubclass(cls, BaseRow)]
