"""background loops: outbox delivery state and the retention grants

Revision ID: 0010_background_loops
Revises: 0008_report_state_prune
Create Date: 2026-10-18

The notification sender needs to remember, per outbox row, when to try again
(``next_attempt_at``), which admins already got the mail (``delivered_to``:
truncated digests, never addresses), a fixed error code (``last_error_code``)
and, for incident notices, a ``dedupe_key``. The runtime role may update
exactly those columns besides the ones it could already update.

The retention loop runs as the admin role, so it gets DELETE on the two task
tables the runner can only append to (``tasks.run_events`` and
``tasks.checkpoints``) and on ``settings.service_state`` (to drop services that
stopped reporting). Nothing else gains DELETE: not ``admin.audit_log``, not
``settings.entries``, ``settings.history`` or ``settings.manifest``.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0010_background_loops"
down_revision: Union[str, None] = "0008_report_state_prune"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column(
            "next_attempt_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        schema=S,
    )
    op.add_column("notifications", sa.Column("last_error_code", sa.Text()), schema=S)
    op.add_column("notifications", sa.Column("dedupe_key", sa.Text()), schema=S)
    op.add_column(
        "notifications",
        sa.Column(
            "delivered_to",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        schema=S,
    )
    op.create_check_constraint(
        op.f("ck_notifications_last_error_code"),
        "notifications",
        "last_error_code IS NULL OR last_error_code ~ '^[a-z][a-z0-9_]{0,31}$'",
        schema=S,
    )
    op.create_check_constraint(
        op.f("ck_notifications_dedupe_key"),
        "notifications",
        "dedupe_key IS NULL OR dedupe_key ~ '^[A-Za-z0-9_.:-]{1,128}$'",
        schema=S,
    )
    op.create_check_constraint(
        op.f("ck_notifications_delivered_to"),
        "notifications",
        "cardinality(delivered_to) <= 50",
        schema=S,
    )
    op.create_index(
        "ix_notifications_status_next_attempt_at",
        "notifications",
        ["status", "next_attempt_at"],
        schema=S,
    )
    op.create_index(
        "ix_notifications_dedupe_key", "notifications", ["dedupe_key"], schema=S
    )
    grant(
        op,
        "GRANT UPDATE (next_attempt_at, last_error_code, delivered_to) "
        "ON admin.notifications TO {role}",
    )
    grant(op, "GRANT DELETE ON tasks.run_events, tasks.checkpoints TO {role}")
    grant(op, "GRANT DELETE ON settings.service_state TO {role}")


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
