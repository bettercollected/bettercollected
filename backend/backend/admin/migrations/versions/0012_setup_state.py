"""setup wizard state, and the "setup" session state

Revision ID: 0012_setup_state
Revises: 0011_setup_tokens
Create Date: 2026-10-19

* ``admin.setup_state`` holds at most one row: when the first-run setup was
  started (a setup token was redeemed), by which admin address, and when it was
  finished. The runtime role can read it, insert the one row and update the
  completion columns; it can never delete it.
* A session created by redeeming a setup token has ``mfa_state = 'setup'``: it
  may only reach the setup pages and second-factor enrolment. The check
  constraint is widened (expand-only: older code never writes the new value).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0012_setup_state"
down_revision: Union[str, None] = "0011_setup_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), **kw)


def upgrade() -> None:
    op.drop_constraint(op.f("ck_sessions_mfa_state"), "sessions", schema=S, type_="check")
    op.create_check_constraint(
        op.f("ck_sessions_mfa_state"),
        "sessions",
        "mfa_state IN ('email_ok', 'mfa_ok', 'setup')",
        schema=S,
    )
    op.create_table(
        "setup_state",
        sa.Column("singleton", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("started_by", sa.Text(), nullable=False),
        _ts("started_at", server_default=sa.text("now()"), nullable=False),
        _ts("mail_step_at"),
        sa.Column("mail_step", sa.Text()),
        _ts("completed_at"),
        sa.Column("completed_by", sa.Text()),
        sa.CheckConstraint("singleton", name=op.f("ck_setup_state_singleton")),
        sa.CheckConstraint(
            "mail_step IS NULL OR mail_step IN ('saved', 'skipped')",
            name=op.f("ck_setup_state_mail_step"),
        ),
        sa.PrimaryKeyConstraint("singleton", name=op.f("pk_setup_state")),
        schema=S,
    )
    grant(op, "GRANT SELECT, INSERT ON admin.setup_state TO {role}")
    grant(
        op,
        "GRANT UPDATE (mail_step, mail_step_at, completed_at, completed_by) "
        "ON admin.setup_state TO {role}",
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
