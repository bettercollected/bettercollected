"""notification outbox

Revision ID: 0006_notifications_outbox
Revises: 0005_settings_views
Create Date: 2026-10-18

Changes that must be announced to the admins (a critical setting changed)
enqueue a row here in the same transaction as the change. A sender sends them
after commit and marks them; until it exists the rows simply wait. Payloads
carry names, versions and tiers, never values.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0006_notifications_outbox"
down_revision: Union[str, None] = "0005_settings_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), **kw)


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        _ts("created_at", server_default=sa.text("now()"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("audit_seq", sa.BigInteger()),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        _ts("sent_at"),
        sa.CheckConstraint(
            "kind ~ '^[a-z][a-z0-9_.]{0,63}$'", name=op.f("ck_notifications_kind")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name=op.f("ck_notifications_status"),
        ),
        sa.CheckConstraint(
            "pg_column_size(payload) <= 4096", name=op.f("ck_notifications_payload")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        schema=S,
    )
    op.create_index(
        "ix_notifications_status_created_at",
        "notifications",
        ["status", "created_at"],
        schema=S,
    )
    grant(op, "GRANT SELECT, INSERT ON admin.notifications TO {role}")
    grant(
        op,
        "GRANT UPDATE (status, attempts, sent_at) ON admin.notifications TO {role}",
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
