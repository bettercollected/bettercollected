"""setup tokens: the first-run token the host operator prints once

Revision ID: 0011_setup_tokens
Revises: 0010_background_loops
Create Date: 2026-10-19

``setup-token`` (host command) stores only a keyed hash of a one-time token
that unlocks the first-run setup. At most one token is active at a time (a
partial unique index). The runtime role may insert a row and update the
columns that record redemption, failed attempts, revocation and locking; it can
never read a token (none is stored) and never delete a row.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0011_setup_tokens"
down_revision: Union[str, None] = "0010_background_loops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), **kw)


def upgrade() -> None:
    op.create_table(
        "setup_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("token_mac", sa.LargeBinary(), nullable=False),
        sa.Column("issued_by", sa.Text(), nullable=False),
        _ts("created_at", server_default=sa.text("now()"), nullable=False),
        _ts("expires_at", nullable=False),
        _ts("consumed_at"),
        _ts("revoked_at"),
        _ts("locked_at"),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "length(token_mac) = 32", name=op.f("ck_setup_tokens_token_mac")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_setup_tokens")),
        schema=S,
    )
    op.create_index(
        "uq_setup_tokens_active",
        "setup_tokens",
        [sa.text("(true)")],
        unique=True,
        schema=S,
        postgresql_where=sa.text(
            "consumed_at IS NULL AND revoked_at IS NULL AND locked_at IS NULL"
        ),
    )
    grant(op, "GRANT SELECT, INSERT ON admin.setup_tokens TO {role}")
    grant(
        op,
        "GRANT UPDATE (consumed_at, revoked_at, locked_at, failed_attempts) "
        "ON admin.setup_tokens TO {role}",
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
