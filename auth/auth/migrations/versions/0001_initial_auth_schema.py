"""initial auth schema

Revision ID: 0001
Revises:
Create Date: 2026-09-06 13:14:27.697770
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


SCHEMA = "auth"


def upgrade() -> None:
    # The schema exists in deployments (postgres/init); CI and scratch databases get it here.
    ensure_schema(op, SCHEMA)
    # Spine columns are GENERATED from doc through these IMMUTABLE helpers, so they come first.
    create_helper_functions(op, SCHEMA)
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
        schema="auth",
    )
    op.create_table(
        "providers",
        sa.Column(
            "provider_name",
            sa.Text(),
            sa.Computed("auth.bc_text(doc -> 'provider_name')", persisted=True),
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
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_providers_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_providers_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_providers")),
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_providers_provider_name"),
        "providers",
        ["provider_name"],
        unique=False,
        schema="auth",
    )
    op.create_table(
        "users",
        sa.Column(
            "email",
            sa.Text(),
            sa.Computed("auth.bc_text(doc -> 'email')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "stripe_customer_id",
            sa.Text(),
            sa.Computed("auth.bc_text(doc -> 'stripe_customer_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "stripe_payment_id",
            sa.Text(),
            sa.Computed("auth.bc_text(doc -> 'stripe_payment_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "otp_code_for",
            sa.Text(),
            sa.Computed("auth.bc_text(doc -> 'otp_code_for')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "plan",
            sa.Text(),
            sa.Computed("auth.bc_text(doc -> 'plan')", persisted=True),
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
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_users_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_users_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_users_stripe_customer_id"),
        "users",
        ["stripe_customer_id"],
        unique=False,
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_users_stripe_payment_id"),
        "users",
        ["stripe_payment_id"],
        unique=False,
        schema="auth",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_auth_users_stripe_payment_id"), table_name="users", schema="auth"
    )
    op.drop_index(
        op.f("ix_auth_users_stripe_customer_id"), table_name="users", schema="auth"
    )
    op.drop_table("users", schema="auth")
    op.drop_index(
        op.f("ix_auth_providers_provider_name"), table_name="providers", schema="auth"
    )
    op.drop_table("providers", schema="auth")
    op.drop_table("mirror_write_failures", schema="auth")
    drop_helper_functions(op, SCHEMA)
