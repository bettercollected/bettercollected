"""deletion tombstones

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24

The ids deleted from this schema's tables, with the time of the delete
(common/db/tombstones.py): reconcile never copies a deleted record back into
either store, and verify reports a deleted record that is still present.
Ids only, no document content. New table only, so expand-only.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "auth"
TABLE = "deletion_tombstones"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("collection", sa.Text(), nullable=False),
        sa.Column("row_id", sa.Text(), nullable=False),
        sa.Column("deleted_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "collection", "row_id", name=op.f("pk_deletion_tombstones")
        ),
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_auth_deletion_tombstones_deleted_at"),
        TABLE,
        ["deleted_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_auth_deletion_tombstones_deleted_at"),
        table_name=TABLE,
        schema=SCHEMA,
    )
    op.drop_table(TABLE, schema=SCHEMA)
