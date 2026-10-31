"""saved drafts of a form (save and continue later)

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-31

One new table (``backend/app/services/form_drafts``): a respondent's saved
draft of a form, answers encrypted. New table only, so expand-only. Written by
hand in the shape autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "form_drafts"


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
        _text("workspace_id"),
        _text("form_id"),
        _text("owner_id"),
        _text("email_key"),
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
        "uq_form_drafts_owner",
        TABLE,
        ["workspace_id", "form_id", "owner_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("owner_id IS NOT NULL"),
    )
    op.create_index(
        op.f("ix_app_form_drafts_workspace_id"),
        TABLE,
        ["workspace_id", "form_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_form_drafts_form_id"),
        TABLE,
        ["form_id", "email_key"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_form_drafts_owner_id"),
        TABLE,
        ["owner_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_form_drafts_expires_at"),
        TABLE,
        ["expires_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    for name in (
        "ix_app_form_drafts_expires_at",
        "ix_app_form_drafts_owner_id",
        "ix_app_form_drafts_form_id",
        "ix_app_form_drafts_workspace_id",
    ):
        op.drop_index(op.f(name), table_name=TABLE, schema=SCHEMA)
    op.drop_index("uq_form_drafts_owner", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
