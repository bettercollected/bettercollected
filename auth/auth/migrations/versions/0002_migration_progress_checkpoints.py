"""migration progress checkpoints

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06 20:17:00.457793
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "migration_progress",
        sa.Column("collection", sa.Text(), nullable=False),
        sa.Column("last_id", sa.Text(), nullable=True),
        sa.Column("count", sa.BigInteger(), nullable=False),
        sa.Column("skipped", sa.BigInteger(), nullable=False),
        sa.Column("batch_size", sa.Integer(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("heartbeat_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("collection", name=op.f("pk_migration_progress")),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_table("migration_progress", schema="auth")
