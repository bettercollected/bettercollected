"""store migration marker

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19

The "migration verified" marker (common/db/marker.py): one row per clean
``verify`` of a repository group, and the service-wide marker a later startup
guard checks. Written only by the migration CLI's verify. New table only, so
expand-only.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "auth"
TABLE = "store_migration"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("service", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("groups", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "collections", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("verified_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("code_version", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("based_on", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_store_migration")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_auth_store_migration_scope"),
        TABLE,
        ["scope", "verified_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_store_migration_scope"), table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
