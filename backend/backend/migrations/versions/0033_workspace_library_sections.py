"""workspace library sections (reusable groups of questions)

Revision ID: 0033
Revises: 0031
Create Date: 2026-11-02

One new table (``backend/app/services/reusable_sections``): a workspace's named
reusable sections, each a spec fragment (questions and layout containers) with
a version and its earlier versions. New table only, so expand-only: the
previous release does not read it, and a rollback keeps working. The unique
index keeps a section name once per workspace (``name_key`` is the folded
name, kept in the document). Written by hand in the shape autogenerate
produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "workspace_library_sections"


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
        _text("name_key"),
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
            name=op.f(f"ck_{TABLE}_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f(f"ck_{TABLE}_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TABLE}")),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_workspace_library_sections_name",
        TABLE,
        ["workspace_id", "name_key"],
        unique=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workspace_library_sections_name", table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
