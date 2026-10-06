"""rate limit counters

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-06

Fixed-window request counters shared by every replica (#767): one row per
client, scope and window, its id a keyed hash of the three (no address is
stored). Expired rows are deleted whenever a new counter starts. New table
only, so expand-only. Written by hand in the shape autogenerate produces for
a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "rate_limit_counters"


def upgrade() -> None:
    op.create_table(
        TABLE,
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
            name=op.f("ck_rate_limit_counters_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_rate_limit_counters_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_counters")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_rate_limit_counters_expires_at"),
        TABLE,
        ["expires_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_rate_limit_counters_expires_at"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
