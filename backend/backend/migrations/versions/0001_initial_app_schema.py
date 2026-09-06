"""initial app schema

Revision ID: 0001
Revises:
Create Date: 2026-09-06 13:13:40.199412
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from common.db.alembic_support import (
    create_helper_functions,
    drop_helper_functions,
    ensure_schema,
)
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCHEMA = "app"


def upgrade() -> None:
    # The schema exists in deployments (postgres/init); CI and scratch databases get it here.
    ensure_schema(op, SCHEMA)
    # Spine columns are GENERATED from doc through these IMMUTABLE helpers, so they come first.
    create_helper_functions(op, SCHEMA)
    op.create_table(
        "actions",
        sa.Column(
            "name",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'name')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'created_by')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "type",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'type')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "predefined",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc -> 'predefined')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_actions_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_actions_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actions")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_actions_created_by"),
        "actions",
        ["created_by"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_actions_name"), "actions", ["name"], unique=False, schema="app"
    )
    op.create_table(
        "ai_preference_memories",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_ai_preference_memories_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_ai_preference_memories_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_preference_memories")),
        schema="app",
    )
    op.create_index(
        "ix_ai_preference_memories_workspace_user",
        "ai_preference_memories",
        ["workspace_id", "user_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "allowed_origins",
        sa.Column(
            "origin",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'origin')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_allowed_origins_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_allowed_origins_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allowed_origins")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_allowed_origins_origin"),
        "allowed_origins",
        ["origin"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "blacklisted_refresh_tokens",
        sa.Column(
            "token",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'token')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "expiry",
            postgresql.TIMESTAMP(timezone=True),
            sa.Computed("app.bc_ts(doc -> 'expiry')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_blacklisted_refresh_tokens_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_blacklisted_refresh_tokens_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_blacklisted_refresh_tokens")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_blacklisted_refresh_tokens_expiry"),
        "blacklisted_refresh_tokens",
        ["expiry"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_blacklisted_refresh_tokens_token"),
        "blacklisted_refresh_tokens",
        ["token"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "coupon_codes",
        sa.Column(
            "code",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'code')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'status')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "used_by",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'used_by')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_coupon_codes_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_coupon_codes_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_coupon_codes")),
        sa.UniqueConstraint("code", name=op.f("uq_coupon_codes_code")),
        schema="app",
    )
    op.create_table(
        "create_form_prompts",
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_create_form_prompts_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_create_form_prompts_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_create_form_prompts")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_create_form_prompts_form_id"),
        "create_form_prompts",
        ["form_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "form_ai_insights",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "generated_at",
            postgresql.TIMESTAMP(timezone=True),
            sa.Computed("app.bc_ts(doc -> 'generated_at')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_form_ai_insights_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_form_ai_insights_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_ai_insights")),
        schema="app",
    )
    op.create_index(
        "ix_form_ai_insights_workspace_form",
        "form_ai_insights",
        ["workspace_id", "form_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "form_ai_sessions",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'provider')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_form_ai_sessions_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_form_ai_sessions_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_ai_sessions")),
        schema="app",
    )
    op.create_index(
        "ix_form_ai_sessions_workspace_form_user",
        "form_ai_sessions",
        ["workspace_id", "form_id", "user_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "form_flow_events",
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "session_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'session_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "from_page",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'from_page')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "to_page",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'to_page')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_form_flow_events_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_form_flow_events_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_flow_events")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_flow_events_created_at"),
        "form_flow_events",
        ["created_at"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_flow_events_form_id"),
        "form_flow_events",
        ["form_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_flow_events_session_id"),
        "form_flow_events",
        ["session_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "form_responses",
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "response_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'response_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "submission_uuid",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'submission_uuid')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'provider')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "data_owner_identifier",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'dataOwnerIdentifier')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "anonymous_identity",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'anonymous_identity')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "form_version",
            sa.BigInteger(),
            sa.Computed("app.bc_int(doc -> 'form_version')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "expiration",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'expiration')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "expiration_type",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'expiration_type')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "state",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'state')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_form_responses_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_form_responses_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_responses")),
        sa.UniqueConstraint("response_id", name=op.f("uq_form_responses_response_id")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_responses_anonymous_identity"),
        "form_responses",
        ["anonymous_identity"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_responses_data_owner_identifier"),
        "form_responses",
        ["data_owner_identifier"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_responses_expiration"),
        "form_responses",
        ["expiration"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_responses_submission_uuid"),
        "form_responses",
        ["submission_uuid"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "ix_form_responses_form_created",
        "form_responses",
        ["form_id", "created_at"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "form_templates",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "category",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'category')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'created_by')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "imported_from",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'imported_from')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "type",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'type')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_form_templates_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_form_templates_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_templates")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_templates_category"),
        "form_templates",
        ["category"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_form_templates_workspace_id"),
        "form_templates",
        ["workspace_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "form_versions",
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "version",
            sa.BigInteger(),
            sa.Computed("app.bc_int(doc -> 'version')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "imported_form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'imported_form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_form_versions_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_form_versions_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_versions")),
        sa.UniqueConstraint(
            "form_id", "version", name=op.f("uq_form_versions_form_id_version")
        ),
        schema="app",
    )
    op.create_table(
        "forms",
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "imported_form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'imported_form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "title",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'title')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "type",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'type')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "builder_version",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'builder_version')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            sa.Computed("app.bc_text(doc #> '{settings,provider}')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "custom_url",
            sa.Text(),
            sa.Computed("app.bc_text(doc #> '{settings,custom_url}')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "published_at",
            postgresql.TIMESTAMP(timezone=True),
            sa.Computed("app.bc_ts(doc -> 'published_at')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_forms_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_forms_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forms")),
        sa.UniqueConstraint("form_id", name=op.f("uq_forms_form_id")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_forms_custom_url"),
        "forms",
        ["custom_url"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_forms_imported_form_id"),
        "forms",
        ["imported_form_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "forms_plugin_configs",
        sa.Column(
            "provider_name",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'provider_name')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc -> 'enabled')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_forms_plugin_configs_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_forms_plugin_configs_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forms_plugin_configs")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_forms_plugin_configs_provider_name"),
        "forms_plugin_configs",
        ["provider_name"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "mcp_audit_logs",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "key_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'key_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "tool",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'tool')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "ok",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc -> 'ok')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "at",
            postgresql.TIMESTAMP(timezone=True),
            sa.Computed("app.bc_ts(doc -> 'at')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_mcp_audit_logs_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_mcp_audit_logs_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_audit_logs")),
        schema="app",
    )
    op.create_index(
        "ix_mcp_audit_logs_workspace_at",
        "mcp_audit_logs",
        ["workspace_id", "at"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "media_libraries",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "media_name",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'media_name')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "media_type",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'media_type')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "s3_key",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 's3_key')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_media_libraries_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_media_libraries_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_libraries")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_media_libraries_workspace_id"),
        "media_libraries",
        ["workspace_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "mirror_write_failures",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("row_id", sa.Text(), nullable=False),
        sa.Column("op", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=False),
        sa.Column(
            "attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mirror_write_failures")),
        schema="app",
    )
    op.create_table(
        "price_suggestion",
        sa.Column(
            "user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "email",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'email')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_price_suggestion_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_price_suggestion_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price_suggestion")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_price_suggestion_user_id"),
        "price_suggestion",
        ["user_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "responder_group",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "name",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'name')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_responder_group_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_responder_group_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_responder_group")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_responder_group_workspace_id"),
        "responder_group",
        ["workspace_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "responder_group_form",
        sa.Column(
            "group_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'group_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "role",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'role')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_responder_group_form_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_responder_group_form_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_responder_group_form")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_responder_group_form_form_id"),
        "responder_group_form",
        ["form_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_responder_group_form_group_id"),
        "responder_group_form",
        ["group_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "responder_group_member",
        sa.Column(
            "group_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'group_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "identifier",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'identifier')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "identifier_type",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'identifierType')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_responder_group_member_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_responder_group_member_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_responder_group_member")),
        schema="app",
    )
    op.create_index(
        "ix_responder_group_member_group_identifier",
        "responder_group_member",
        ["group_id", "identifier"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "responses_deletion_requests",
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "response_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'response_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'provider')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'status')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "data_owner_identifier",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'dataOwnerIdentifier')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "anonymous_identity",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'anonymous_identity')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_responses_deletion_requests_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_responses_deletion_requests_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_responses_deletion_requests")),
        sa.UniqueConstraint(
            "form_id",
            "response_id",
            "provider",
            name=op.f("uq_responses_deletion_requests_form_id_response_id_provider"),
            postgresql_nulls_not_distinct=True,
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_responses_deletion_requests_status"),
        "responses_deletion_requests",
        ["status"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "scheduler_form_configs",
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'provider')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "imported_at",
            postgresql.TIMESTAMP(timezone=True),
            sa.Computed("app.bc_ts(doc -> 'imported_at')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_scheduler_form_configs_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_scheduler_form_configs_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduler_form_configs")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_scheduler_form_configs_form_id"),
        "scheduler_form_configs",
        ["form_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_scheduler_form_configs_workspace_id"),
        "scheduler_form_configs",
        ["workspace_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_user_feedback_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_user_feedback_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_feedback")),
        schema="app",
    )
    op.create_table(
        "user_tags",
        sa.Column(
            "user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_user_tags_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_user_tags_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_tags")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_user_tags_user_id"),
        "user_tags",
        ["user_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspace_actions",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "action_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'action_id')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_actions_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspace_actions_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_actions")),
        schema="app",
    )
    op.create_index(
        "ix_workspace_actions_workspace_action",
        "workspace_actions",
        ["workspace_id", "action_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspace_ai_profiles",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_ai_profiles_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_workspace_ai_profiles_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_ai_profiles")),
        sa.UniqueConstraint(
            "workspace_id", name=op.f("uq_workspace_ai_profiles_workspace_id")
        ),
        schema="app",
    )
    op.create_table(
        "workspace_api_keys",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "key_hash",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'key_hash')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "prefix",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'prefix')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'created_by')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "revoked",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc -> 'revoked')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_api_keys_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspace_api_keys_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_api_keys")),
        sa.UniqueConstraint("key_hash", name=op.f("uq_workspace_api_keys_key_hash")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_workspace_api_keys_workspace_id"),
        "workspace_api_keys",
        ["workspace_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspace_consent",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_consent_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspace_consent_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_consent")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_workspace_consent_workspace_id"),
        "workspace_consent",
        ["workspace_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspace_forms",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "form_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'form_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "custom_url",
            sa.Text(),
            sa.Computed("app.bc_text(doc #> '{settings,custom_url}')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "private",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc #> '{settings,private}')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "hidden",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc #> '{settings,hidden}')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "pinned",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc #> '{settings,pinned}')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_forms_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspace_forms_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_forms")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_workspace_forms_form_id"),
        "workspace_forms",
        ["form_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "ix_workspace_forms_workspace_custom_url",
        "workspace_forms",
        ["workspace_id", "custom_url"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "ix_workspace_forms_workspace_form",
        "workspace_forms",
        ["workspace_id", "form_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspace_invites",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "email",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'email')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "invitation_token",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'invitation_token')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "invitation_status",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'invitation_status')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "role",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'role')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "expiry",
            sa.BigInteger(),
            sa.Computed("app.bc_int(doc -> 'expiry')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_invites_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspace_invites_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_invites")),
        sa.UniqueConstraint(
            "workspace_id",
            "email",
            name=op.f("uq_workspace_invites_workspace_id_email"),
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_workspace_invites_invitation_token"),
        "workspace_invites",
        ["invitation_token"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspace_responder",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "email",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'email')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_responder_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspace_responder_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_responder")),
        schema="app",
    )
    op.create_index(
        "ix_workspace_responder_workspace_email",
        "workspace_responder",
        ["workspace_id", "email"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspace_tags",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "title",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'title')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_tags_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspace_tags_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_tags")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_workspace_tags_workspace_id"),
        "workspace_tags",
        ["workspace_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspace_users",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "disabled",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc -> 'disabled')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f("ck_workspace_users_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspace_users_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_users")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_workspace_users_user_id"),
        "workspace_users",
        ["user_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "ix_workspace_users_workspace_user",
        "workspace_users",
        ["workspace_id", "user_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "workspaces",
        sa.Column(
            "workspace_name",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_name')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "custom_domain",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'custom_domain')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "owner_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'owner_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc -> 'default')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "disabled",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc -> 'disabled')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "custom_domain_verified",
            sa.Boolean(),
            sa.Computed("app.bc_bool(doc -> 'custom_domain_verified')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_workspaces_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_workspaces_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint(
            "workspace_name", name=op.f("uq_workspaces_workspace_name")
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_workspaces_owner_id"),
        "workspaces",
        ["owner_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        "uq_workspaces_custom_domain",
        "workspaces",
        ["custom_domain"],
        unique=True,
        schema="app",
        postgresql_where=sa.text("custom_domain IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workspaces_custom_domain",
        table_name="workspaces",
        schema="app",
        postgresql_where=sa.text("custom_domain IS NOT NULL"),
    )
    op.drop_index(
        op.f("ix_app_workspaces_owner_id"), table_name="workspaces", schema="app"
    )
    op.drop_table("workspaces", schema="app")
    op.drop_index(
        "ix_workspace_users_workspace_user", table_name="workspace_users", schema="app"
    )
    op.drop_index(
        op.f("ix_app_workspace_users_user_id"),
        table_name="workspace_users",
        schema="app",
    )
    op.drop_table("workspace_users", schema="app")
    op.drop_index(
        op.f("ix_app_workspace_tags_workspace_id"),
        table_name="workspace_tags",
        schema="app",
    )
    op.drop_table("workspace_tags", schema="app")
    op.drop_index(
        "ix_workspace_responder_workspace_email",
        table_name="workspace_responder",
        schema="app",
    )
    op.drop_table("workspace_responder", schema="app")
    op.drop_index(
        op.f("ix_app_workspace_invites_invitation_token"),
        table_name="workspace_invites",
        schema="app",
    )
    op.drop_table("workspace_invites", schema="app")
    op.drop_index(
        "ix_workspace_forms_workspace_form", table_name="workspace_forms", schema="app"
    )
    op.drop_index(
        "ix_workspace_forms_workspace_custom_url",
        table_name="workspace_forms",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_workspace_forms_form_id"),
        table_name="workspace_forms",
        schema="app",
    )
    op.drop_table("workspace_forms", schema="app")
    op.drop_index(
        op.f("ix_app_workspace_consent_workspace_id"),
        table_name="workspace_consent",
        schema="app",
    )
    op.drop_table("workspace_consent", schema="app")
    op.drop_index(
        op.f("ix_app_workspace_api_keys_workspace_id"),
        table_name="workspace_api_keys",
        schema="app",
    )
    op.drop_table("workspace_api_keys", schema="app")
    op.drop_table("workspace_ai_profiles", schema="app")
    op.drop_index(
        "ix_workspace_actions_workspace_action",
        table_name="workspace_actions",
        schema="app",
    )
    op.drop_table("workspace_actions", schema="app")
    op.drop_index(
        op.f("ix_app_user_tags_user_id"), table_name="user_tags", schema="app"
    )
    op.drop_table("user_tags", schema="app")
    op.drop_table("user_feedback", schema="app")
    op.drop_index(
        op.f("ix_app_scheduler_form_configs_workspace_id"),
        table_name="scheduler_form_configs",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_scheduler_form_configs_form_id"),
        table_name="scheduler_form_configs",
        schema="app",
    )
    op.drop_table("scheduler_form_configs", schema="app")
    op.drop_index(
        op.f("ix_app_responses_deletion_requests_status"),
        table_name="responses_deletion_requests",
        schema="app",
    )
    op.drop_table("responses_deletion_requests", schema="app")
    op.drop_index(
        "ix_responder_group_member_group_identifier",
        table_name="responder_group_member",
        schema="app",
    )
    op.drop_table("responder_group_member", schema="app")
    op.drop_index(
        op.f("ix_app_responder_group_form_group_id"),
        table_name="responder_group_form",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_responder_group_form_form_id"),
        table_name="responder_group_form",
        schema="app",
    )
    op.drop_table("responder_group_form", schema="app")
    op.drop_index(
        op.f("ix_app_responder_group_workspace_id"),
        table_name="responder_group",
        schema="app",
    )
    op.drop_table("responder_group", schema="app")
    op.drop_index(
        op.f("ix_app_price_suggestion_user_id"),
        table_name="price_suggestion",
        schema="app",
    )
    op.drop_table("price_suggestion", schema="app")
    op.drop_table("mirror_write_failures", schema="app")
    op.drop_index(
        op.f("ix_app_media_libraries_workspace_id"),
        table_name="media_libraries",
        schema="app",
    )
    op.drop_table("media_libraries", schema="app")
    op.drop_index(
        "ix_mcp_audit_logs_workspace_at", table_name="mcp_audit_logs", schema="app"
    )
    op.drop_table("mcp_audit_logs", schema="app")
    op.drop_index(
        op.f("ix_app_forms_plugin_configs_provider_name"),
        table_name="forms_plugin_configs",
        schema="app",
    )
    op.drop_table("forms_plugin_configs", schema="app")
    op.drop_index(
        op.f("ix_app_forms_imported_form_id"), table_name="forms", schema="app"
    )
    op.drop_index(op.f("ix_app_forms_custom_url"), table_name="forms", schema="app")
    op.drop_table("forms", schema="app")
    op.drop_table("form_versions", schema="app")
    op.drop_index(
        op.f("ix_app_form_templates_workspace_id"),
        table_name="form_templates",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_form_templates_category"),
        table_name="form_templates",
        schema="app",
    )
    op.drop_table("form_templates", schema="app")
    op.drop_index(
        "ix_form_responses_form_created", table_name="form_responses", schema="app"
    )
    op.drop_index(
        op.f("ix_app_form_responses_submission_uuid"),
        table_name="form_responses",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_form_responses_expiration"),
        table_name="form_responses",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_form_responses_data_owner_identifier"),
        table_name="form_responses",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_form_responses_anonymous_identity"),
        table_name="form_responses",
        schema="app",
    )
    op.drop_table("form_responses", schema="app")
    op.drop_index(
        op.f("ix_app_form_flow_events_session_id"),
        table_name="form_flow_events",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_form_flow_events_form_id"),
        table_name="form_flow_events",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_form_flow_events_created_at"),
        table_name="form_flow_events",
        schema="app",
    )
    op.drop_table("form_flow_events", schema="app")
    op.drop_index(
        "ix_form_ai_sessions_workspace_form_user",
        table_name="form_ai_sessions",
        schema="app",
    )
    op.drop_table("form_ai_sessions", schema="app")
    op.drop_index(
        "ix_form_ai_insights_workspace_form",
        table_name="form_ai_insights",
        schema="app",
    )
    op.drop_table("form_ai_insights", schema="app")
    op.drop_index(
        op.f("ix_app_create_form_prompts_form_id"),
        table_name="create_form_prompts",
        schema="app",
    )
    op.drop_table("create_form_prompts", schema="app")
    op.drop_table("coupon_codes", schema="app")
    op.drop_index(
        op.f("ix_app_blacklisted_refresh_tokens_token"),
        table_name="blacklisted_refresh_tokens",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_blacklisted_refresh_tokens_expiry"),
        table_name="blacklisted_refresh_tokens",
        schema="app",
    )
    op.drop_table("blacklisted_refresh_tokens", schema="app")
    op.drop_index(
        op.f("ix_app_allowed_origins_origin"),
        table_name="allowed_origins",
        schema="app",
    )
    op.drop_table("allowed_origins", schema="app")
    op.drop_index(
        "ix_ai_preference_memories_workspace_user",
        table_name="ai_preference_memories",
        schema="app",
    )
    op.drop_table("ai_preference_memories", schema="app")
    op.drop_index(op.f("ix_app_actions_name"), table_name="actions", schema="app")
    op.drop_index(op.f("ix_app_actions_created_by"), table_name="actions", schema="app")
    op.drop_table("actions", schema="app")
    drop_helper_functions(op, SCHEMA)
