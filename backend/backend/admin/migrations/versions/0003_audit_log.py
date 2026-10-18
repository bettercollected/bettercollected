"""append-only, hash-chained audit log

Revision ID: 0003_audit_log
Revises: 0002_factors_and_recovery_codes
Create Date: 2026-10-18

Three layers keep the log append-only and tamper-evident:

* privileges: the runtime role gets INSERT and SELECT on the table and USAGE on
  its sequence, nothing else (no default privileges exist that could add more);
* triggers, which also bind the owner: BEFORE UPDATE / DELETE (per row) and
  BEFORE TRUNCATE raise; BEFORE INSERT takes the chain's advisory lock and
  refuses a row whose ``prev_hash`` is not the latest ``row_hash`` (or the
  genesis hash for the first row);
* the HMAC chain itself, computed by the application with a key the database
  never sees (``backend.admin.services.audit``), checked by ``audit-verify``.

The two constants below are duplicated in ``services/audit.py``; a test asserts
they agree. Revisions stay frozen, so they are literals here.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0003_audit_log"
down_revision: Union[str, None] = "0002_factors_and_recovery_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"
GENESIS_HASH_HEX = "49721f39819d393a7eb054f530ba3a3d317610b7ce438667a0580ce1df85badf"
CHAIN_LOCK_KEY = -1909258384265368190


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), **kw)


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("seq", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        _ts("at", nullable=False),
        sa.Column("actor_kind", sa.Text(), nullable=False),
        sa.Column("actor_email", sa.Text()),
        sa.Column("session_id", postgresql.UUID(as_uuid=True)),
        sa.Column("ip", postgresql.INET()),
        sa.Column("ua", sa.Text()),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text()),
        sa.Column("target_id", sa.Text()),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("before", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("after", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("detail", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("request_id", sa.Text()),
        # version of the admin/audit subkey that signed this row (hashed with it)
        sa.Column("key_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("prev_hash", sa.LargeBinary(), nullable=False),
        sa.Column("row_hash", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint(
            "actor_kind IN ('admin', 'cli', 'system', 'anonymous')",
            name=op.f("ck_audit_log_actor_kind"),
        ),
        sa.CheckConstraint(
            "length(prev_hash) = 32 AND length(row_hash) = 32",
            name=op.f("ck_audit_log_hash_lengths"),
        ),
        sa.PrimaryKeyConstraint("seq", name=op.f("pk_audit_log")),
        schema=S,
    )
    op.create_index("uq_audit_log_id", "audit_log", ["id"], unique=True, schema=S)
    op.create_index(
        "uq_audit_log_row_hash", "audit_log", ["row_hash"], unique=True, schema=S
    )
    op.create_index("ix_audit_log_at", "audit_log", ["at"], schema=S)

    op.execute(
        """
        CREATE FUNCTION admin.audit_log_refuse_change() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            RAISE EXCEPTION 'admin.audit_log is append-only (% refused)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_update_delete
        BEFORE UPDATE OR DELETE ON admin.audit_log
        FOR EACH ROW EXECUTE FUNCTION admin.audit_log_refuse_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_no_truncate
        BEFORE TRUNCATE ON admin.audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION admin.audit_log_refuse_change()
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION admin.audit_log_check_chain() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, admin AS $$
        DECLARE
            head bytea;
        BEGIN
            PERFORM pg_advisory_xact_lock({CHAIN_LOCK_KEY});
            SELECT row_hash INTO head FROM admin.audit_log ORDER BY seq DESC LIMIT 1;
            IF head IS NULL THEN
                head := decode('{GENESIS_HASH_HEX}', 'hex');
            END IF;
            IF NEW.prev_hash IS DISTINCT FROM head THEN
                RAISE EXCEPTION 'admin.audit_log: prev_hash is not the chain head'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_chain
        BEFORE INSERT ON admin.audit_log
        FOR EACH ROW EXECUTE FUNCTION admin.audit_log_check_chain()
        """
    )

    grant(op, "GRANT SELECT, INSERT ON admin.audit_log TO {role}")
    grant(op, "GRANT USAGE ON SEQUENCE admin.audit_log_seq_seq TO {role}")
    grant(op, "REVOKE UPDATE, DELETE, TRUNCATE ON admin.audit_log FROM {role}")


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
