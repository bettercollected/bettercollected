"""sso used states

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-04

Single sign-on callbacks already accepted, by the hash of the browser's
nonce, so each sign-in state is accepted once (docs/sso.md). Expired rows are
deleted on each claim. New table only, so expand-only. Written by hand in the
shape autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "sso_used_states"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column(
            "nonce_hash",
            sa.Text(),
            sa.Computed(f"{SCHEMA}.bc_text(doc -> 'nonce_hash')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            postgresql.TIMESTAMP(timezone=True),
            sa.Computed(f"{SCHEMA}.bc_ts(doc -> 'expires_at')", persisted=True),
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
            name=op.f("ck_sso_used_states_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_sso_used_states_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sso_used_states")),
        sa.UniqueConstraint("nonce_hash", name=op.f("uq_sso_used_states_nonce_hash")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_sso_used_states_expires_at"),
        TABLE,
        ["expires_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_sso_used_states_expires_at"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
