"""form imports

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-27

One row per import of an uploaded PDF or image into a draft form. Written by
hand in the shape autogenerate produces for a BaseRow table (autogenerate
cannot run as the backend role: it inspects the other services' schemas).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "form_imports"


def _spine(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        _spine("workspace_id"),
        _spine("form_id"),
        _spine("status"),
        _spine("sha256"),
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
            name=op.f("ck_form_imports_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_form_imports_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_form_imports")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_form_imports_workspace_id"),
        TABLE,
        ["workspace_id", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_form_imports_form_id"),
        TABLE,
        ["form_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_app_form_imports_form_id"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(
        op.f("ix_app_form_imports_workspace_id"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
