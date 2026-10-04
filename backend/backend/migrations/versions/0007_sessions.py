"""sessions

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-04

One row per signed-in session (the ``sid`` claim of the tokens issued for it),
read on every token refresh so a revoked session ends at the next refresh.
Written by hand in the shape autogenerate produces for a BaseRow table.
Expand-only: ``blacklisted_refresh_tokens`` is no longer used but stays until a
later release.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "sessions"


def _text(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def _ts(name: str) -> sa.Column:
    return sa.Column(
        name,
        postgresql.TIMESTAMP(timezone=True),
        sa.Computed(f"{SCHEMA}.bc_ts(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        _text("user_id"),
        _text("refresh_jti"),
        _ts("revoked_at"),
        _ts("expires_at"),
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
            name=op.f("ck_sessions_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_sessions_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_sessions_user_id"),
        TABLE,
        ["user_id", "revoked_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_sessions_expires_at"),
        TABLE,
        ["expires_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_app_sessions_expires_at"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(op.f("ix_app_sessions_user_id"), table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
