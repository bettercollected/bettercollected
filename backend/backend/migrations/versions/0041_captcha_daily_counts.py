"""automatic spam check: the daily counts table

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-14

Expand only (behind ``CAPTCHA_ENABLED``; nothing reads or writes the table while
it is off, and a release before this one ignores it):

* ``captcha_daily_counts``: how many times each outcome of the proof of work
  (issued, verified, missing, invalid, expired, replayed, rate limited)
  happened on a UTC day for a form and purpose. One row per day, workspace, form,
  purpose and outcome (its id is a hash of those, so a count is one row); counts
  only, never a client, an address or a person. A table of its own with no
  foreign keys, like every table of this schema; it is swept after the retention
  of the flow events. New table, not imported from Mongo
  (``common/common/db/migrate/import_guard.py``).

Written by hand in the shape autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "captcha_daily_counts"


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
        *[_spine(n) for n in ("day", "workspace_id", "form_id")],
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
    # a workspace's and a form's counts over a range of days; the retention sweep
    op.create_index(
        op.f(f"ix_app_{TABLE}_workspace_id"),
        TABLE,
        ["workspace_id", "day"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_app_{TABLE}_form_id"),
        TABLE,
        ["form_id", "day"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_app_{TABLE}_day"), TABLE, ["day"], unique=False, schema=SCHEMA
    )


def downgrade() -> None:
    op.drop_index(op.f(f"ix_app_{TABLE}_day"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(op.f(f"ix_app_{TABLE}_form_id"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(
        op.f(f"ix_app_{TABLE}_workspace_id"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
