"""checkpoint of the automatic audit chain verification

Revision ID: 0017_audit_verify_state
Revises: 0016_outbox_and_state_guards
Create Date: 2026-10-19

The integrity loop now verifies the audit chain by itself, incrementally: it
remembers the last row it verified (``verified_seq`` and that row's ``row_hash``)
in this single-row table, checks on the next pass that the row is still there
with the same hash, and verifies the rows after it (bounded per pass). The
checkpoint only moves forward. A credential that writes junk into it cannot hide
anything: the next pass compares it with the log and reports a mismatch.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0017_audit_verify_state"
down_revision: Union[str, None] = "0016_outbox_and_state_guards"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"


def upgrade() -> None:
    op.create_table(
        "audit_verify_state",
        sa.Column("id", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("verified_seq", sa.BigInteger(), nullable=False),
        sa.Column("verified_hash", sa.LargeBinary(), nullable=False),
        sa.Column("rows_verified", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "verified_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_audit_verify_state_single")),
        sa.CheckConstraint(
            "length(verified_hash) = 32", name=op.f("ck_audit_verify_state_hash")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_verify_state")),
        schema=S,
    )
    op.execute(
        """
        CREATE FUNCTION admin.audit_verify_state_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            IF NEW.verified_seq < OLD.verified_seq THEN
                RAISE EXCEPTION 'admin.audit_verify_state: the checkpoint only moves forward'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_verify_state_guard BEFORE UPDATE ON admin.audit_verify_state "
        "FOR EACH ROW EXECUTE FUNCTION admin.audit_verify_state_guard()"
    )
    grant(op, "GRANT SELECT, INSERT ON admin.audit_verify_state TO {role}")
    grant(
        op,
        "GRANT UPDATE (verified_seq, verified_hash, rows_verified, verified_at) "
        "ON admin.audit_verify_state TO {role}",
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
