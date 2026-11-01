"""workspace option lists (reference data for choice questions)

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-01

Two new tables. ``option_source_erasures`` is the queue of answers of another
form that were erased while offered as options (``services/option_sources/
erasure.py``): option ids only, deleted once the choices made from them are
redacted.

One new table (``backend/app/services/option_lists``): a workspace's named
lists of options (a label per item, an optional group key), which a dropdown or
multiple choice question can take its options from. New table only, so
expand-only: the previous release does not read it, and a rollback keeps
working. The unique index keeps a list name once per workspace (``name_key``
is the folded name, kept in the document). Written by hand in the shape
autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "workspace_option_lists"


def _text(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def _base_columns() -> list:
    return [
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
    ]


def _create_erasures() -> None:
    table = "option_source_erasures"
    op.create_table(
        table,
        _text("workspace_id"),
        _text("form_id"),
        *_base_columns(),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')", name=op.f(f"ck_{table}_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f(f"ck_{table}_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_{SCHEMA}_{table}_workspace_id"),
        table,
        ["workspace_id", "form_id"],
        schema=SCHEMA,
    )


def upgrade() -> None:
    _create_erasures()
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
        "uq_workspace_option_lists_name",
        TABLE,
        ["workspace_id", "name_key"],
        unique=True,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f(f"ix_{SCHEMA}_option_source_erasures_workspace_id"),
        table_name="option_source_erasures",
        schema=SCHEMA,
    )
    op.drop_table("option_source_erasures", schema=SCHEMA)
    op.drop_index("uq_workspace_option_lists_name", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
