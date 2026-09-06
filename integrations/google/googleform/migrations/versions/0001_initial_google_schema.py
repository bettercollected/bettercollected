"""initial google schema

Revision ID: 0001
Revises:
Create Date: 2026-09-06 13:17:04.070648
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


SCHEMA = "google"


def upgrade() -> None:
    # The schema exists in deployments (postgres/init); CI and scratch databases get it here.
    ensure_schema(op, SCHEMA)
    # Spine columns are GENERATED from doc through these IMMUTABLE helpers, so they come first.
    create_helper_functions(op, SCHEMA)
    op.create_table(
        "google_form_responses",
        sa.Column(
            "google_form_id",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'formId')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "google_response_id",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'responseId')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'provider')", persisted=True),
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
            name=op.f("ck_google_form_responses_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_google_form_responses_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_google_form_responses")),
        schema="google",
    )
    op.create_index(
        "ix_google_form_responses_form_response",
        "google_form_responses",
        ["google_form_id", "google_response_id"],
        unique=False,
        schema="google",
    )
    op.create_table(
        "google_forms",
        sa.Column(
            "google_form_id",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'formId')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'provider')", persisted=True),
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
            name=op.f("ck_google_forms_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_google_forms_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_google_forms")),
        schema="google",
    )
    op.create_index(
        op.f("ix_google_google_forms_google_form_id"),
        "google_forms",
        ["google_form_id"],
        unique=False,
        schema="google",
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
        schema="google",
    )
    op.create_table(
        "oauth_credentials",
        sa.Column(
            "email",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'email')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "provider",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'provider')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "state",
            sa.Text(),
            sa.Computed("google.bc_text(doc -> 'state')", persisted=True),
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
            name=op.f("ck_oauth_credentials_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_oauth_credentials_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_credentials")),
        schema="google",
    )
    op.create_index(
        op.f("ix_google_oauth_credentials_email"),
        "oauth_credentials",
        ["email"],
        unique=False,
        schema="google",
    )
    op.create_index(
        op.f("ix_google_oauth_credentials_user_id"),
        "oauth_credentials",
        ["user_id"],
        unique=False,
        schema="google",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_google_oauth_credentials_user_id"),
        table_name="oauth_credentials",
        schema="google",
    )
    op.drop_index(
        op.f("ix_google_oauth_credentials_email"),
        table_name="oauth_credentials",
        schema="google",
    )
    op.drop_table("oauth_credentials", schema="google")
    op.drop_table("mirror_write_failures", schema="google")
    op.drop_index(
        op.f("ix_google_google_forms_google_form_id"),
        table_name="google_forms",
        schema="google",
    )
    op.drop_table("google_forms", schema="google")
    op.drop_index(
        "ix_google_form_responses_form_response",
        table_name="google_form_responses",
        schema="google",
    )
    op.drop_table("google_form_responses", schema="google")
    drop_helper_functions(op, SCHEMA)
