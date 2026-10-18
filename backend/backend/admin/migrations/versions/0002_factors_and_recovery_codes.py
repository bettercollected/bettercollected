"""second-factor secrets and recovery codes

Revision ID: 0002_factors_and_recovery_codes
Revises: 0001_sessions_and_attempts
Create Date: 2026-10-18

``secret_blob`` is an authenticated-encryption envelope (``v1:<key_id>:...``),
never the secret itself; ``recovery_codes.code_hash`` is a keyed hash.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0002_factors_and_recovery_codes"
down_revision: Union[str, None] = "0001_sessions_and_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), **kw)


def upgrade() -> None:
    op.create_table(
        "factors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("secret_blob", sa.Text(), nullable=False),
        sa.Column("key_id", sa.Text(), nullable=False),
        _ts("confirmed_at"),
        sa.Column("last_used_step", sa.BigInteger()),
        _ts("created_at", server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_factors")),
        schema=S,
    )
    op.create_index("ix_factors_email", "factors", ["email"], schema=S)

    op.create_table(
        "recovery_codes",
        sa.Column("code_hash", sa.LargeBinary(), nullable=False),
        sa.Column("factor_id", postgresql.UUID(as_uuid=True), nullable=False),
        _ts("used_at"),
        _ts("created_at", server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["factor_id"],
            ["admin.factors.id"],
            name=op.f("fk_recovery_codes_factor_id_factors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("code_hash", name=op.f("pk_recovery_codes")),
        schema=S,
    )
    op.create_index(
        "ix_recovery_codes_factor_id", "recovery_codes", ["factor_id"], schema=S
    )

    for table in ("factors", "recovery_codes"):
        grant(op, f"GRANT SELECT, INSERT, UPDATE, DELETE ON admin.{table} TO {{role}}")


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
