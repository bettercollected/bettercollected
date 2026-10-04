"""workspace domains

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-04

Email domains a workspace claims and verifies with a DNS TXT record. A
domain is verified by at most one workspace (partial unique index on
``verified_domain``). New table only, so expand-only. Written by hand in the
shape autogenerate produces for a BaseRow table (autogenerate cannot run as
the backend role, and it does not compare a partial index's WHERE clause).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "workspace_domains"


def _spine(name: str, kind=sa.Text, fn: str = "bc_text") -> sa.Column:
    return sa.Column(
        name,
        kind(),
        sa.Computed(f"{SCHEMA}.{fn}(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        _spine("workspace_id"),
        _spine("domain"),
        _spine("status"),
        _spine("verified_domain"),
        _spine(
            "last_checked_at",
            lambda: postgresql.TIMESTAMP(timezone=True),
            "bc_ts",
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
            name=op.f("ck_workspace_domains_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f("ck_workspace_domains_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspace_domains")),
        sa.UniqueConstraint(
            "workspace_id",
            "domain",
            name=op.f("uq_workspace_domains_workspace_id_domain"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_workspace_domains_domain"),
        TABLE,
        ["domain"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        "uq_workspace_domains_verified_domain",
        TABLE,
        ["verified_domain"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("verified_domain IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_app_workspace_domains_status"),
        TABLE,
        ["status", "last_checked_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_workspace_domains_status"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_index(
        "uq_workspace_domains_verified_domain", table_name=TABLE, schema=SCHEMA
    )
    op.drop_index(
        op.f("ix_app_workspace_domains_domain"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
