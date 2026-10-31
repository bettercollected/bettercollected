"""form email actions, and the action type of the action log

Revision ID: 0026
Revises: 0024
Create Date: 2026-10-31

One new table (``backend/app/services/email_actions``): a form's email
actions (templates, team addresses, the question whose answer receives a copy).
And a generated spine column ``action_type`` on ``action_logs``, so the webhook
and the email sweeps and lists each read only their own rows. Expand-only: a
new table and a new nullable generated column (the table is small and kept 30
days); rows written before it read as ``webhook``. Numbered 0026 because the
responses list work takes 0025: whichever merges second sets its down-revision
to the other's. Written by hand in the shape
autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0026"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "form_email_actions"


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
        op.f("ix_app_form_email_actions_workspace_id"),
        TABLE,
        ["workspace_id", "form_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.add_column("action_logs", _spine("action_type"), schema=SCHEMA)


def downgrade() -> None:
    op.drop_column("action_logs", "action_type", schema=SCHEMA)
    op.drop_index(
        op.f("ix_app_form_email_actions_workspace_id"),
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_table(TABLE, schema=SCHEMA)
