"""sso connections

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-04

A workspace's single sign-on connections: references to connections held by
Ory Polis (docs/sso.md). New table only, so expand-only. Written by hand in
the shape autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "sso_connections"


def _text(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        _text("workspace_id"),
        _text("status"),
        _text("polis_client_id"),
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
            name=op.f("ck_sso_connections_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_sso_connections_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sso_connections")),
        sa.UniqueConstraint(
            "polis_client_id", name=op.f("uq_sso_connections_polis_client_id")
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_sso_connections_workspace_id"),
        TABLE,
        ["workspace_id", "status"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_sso_connections_workspace_id"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
