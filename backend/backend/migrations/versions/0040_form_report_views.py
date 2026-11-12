"""saved report views: the table

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-12

Expand only (behind ``REPORTING_ENABLED``; nothing reads or writes the table
while it is off, except the clean-up that deletes a form's or a removed member's
rows, and a release before this one ignores it):

* ``form_report_views``: a saved view of a form's report, one row each: its
  ``name``, its ``scope`` (``private``: its owner's notebook, or ``form``: for
  everyone who may open the report), its ``owner_id``, a ``revision`` (a change
  made from a stale copy is refused) and the validated ``definition`` (question
  and option ids, numbers, dates and enums, never an answer or a respondent).
  A table of its own with no foreign keys, like every table of this schema: a
  form's views go with the form, a removed member's private views with the member
  (``services/reporting/views.py``). New table, not imported from Mongo
  (``common/common/db/migrate/import_guard.py``).

Written by hand in the shape autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "form_report_views"


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
        *[_spine(n) for n in ("workspace_id", "form_id", "owner_id", "scope")],
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
    # a form's views (the list), and a person's (their notebook, the member clean-up)
    op.create_index(
        op.f(f"ix_app_{TABLE}_workspace_id"),
        TABLE,
        ["workspace_id", "form_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_app_{TABLE}_owner_id"), TABLE, ["owner_id"], unique=False, schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index(op.f(f"ix_app_{TABLE}_owner_id"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(
        op.f(f"ix_app_{TABLE}_workspace_id"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
