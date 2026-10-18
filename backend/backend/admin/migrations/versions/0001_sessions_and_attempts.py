"""sessions, sign-in challenges and attempt counters

Revision ID: 0001_sessions_and_attempts
Revises:
Create Date: 2026-10-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0001_sessions_and_attempts"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), **kw)


def _id() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "sessions",
        _id(),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("mfa_state", sa.Text(), server_default="email_ok", nullable=False),
        _ts("stepup_at"),
        _ts("created_at", server_default=sa.text("now()"), nullable=False),
        _ts("last_seen_at", server_default=sa.text("now()"), nullable=False),
        _ts("idle_expires_at", nullable=False),
        _ts("abs_expires_at", nullable=False),
        sa.Column("ip", postgresql.INET()),
        sa.Column("ua_hash", sa.LargeBinary()),
        _ts("revoked_at"),
        sa.Column("revoked_reason", sa.Text()),
        sa.Column("revoked_by", sa.Text()),
        sa.CheckConstraint(
            "mfa_state IN ('email_ok', 'mfa_ok')", name=op.f("ck_sessions_mfa_state")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        schema=S,
    )
    op.create_index(
        "uq_sessions_token_hash", "sessions", ["token_hash"], unique=True, schema=S
    )
    op.create_index("ix_sessions_email", "sessions", ["email"], schema=S)

    op.create_table(
        "signin_challenges",
        _id(),
        sa.Column("email", sa.Text()),
        sa.Column("code_hash", sa.LargeBinary(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ip", postgresql.INET()),
        _ts("created_at", server_default=sa.text("now()"), nullable=False),
        _ts("expires_at", nullable=False),
        _ts("consumed_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signin_challenges")),
        schema=S,
    )
    op.create_index(
        "ix_signin_challenges_expires_at", "signin_challenges", ["expires_at"], schema=S
    )

    # (key, window_start) is the conflict target of the atomic
    # INSERT ... ON CONFLICT DO UPDATE SET count = count + 1 the limiter uses.
    op.create_table(
        "attempts",
        sa.Column("key", sa.Text(), nullable=False),
        _ts("window_start", nullable=False),
        sa.Column("count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("key", "window_start", name=op.f("pk_attempts")),
        schema=S,
    )

    grant(op, "GRANT USAGE ON SCHEMA admin TO {role}")
    grant(op, "GRANT SELECT ON admin.alembic_version TO {role}")
    for table in ("sessions", "signin_challenges", "attempts"):
        grant(op, f"GRANT SELECT, INSERT, UPDATE, DELETE ON admin.{table} TO {{role}}")


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
