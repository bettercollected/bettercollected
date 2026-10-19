"""locks only the admin roles can take: lock rows and loop leases

Revision ID: 0013_lock_rows_and_leases
Revises: 0012_setup_state
Create Date: 2026-10-19

Advisory locks live in one cluster-wide namespace and ``pg_advisory_lock`` is
executable by every role, so any database login (the backend, the auth service,
the user-code executor's role) could take the repository's constant lock keys
and stall audit writes, settings writes, the setup token and the background
loops. This revision replaces them with things an outsider cannot touch:

* ``admin.lock_rows``: one row per serialisation point (``audit_chain``,
  ``settings_writer``, ``signin``, ``setup_token``), changed by nobody. A lock is
  ``SELECT ... FOR UPDATE`` on its row, which needs UPDATE privilege on the table
  that only the owner holds; ``admin.take_lock(name)`` (SECURITY DEFINER, pinned
  search_path) does it on behalf of the admin roles and gives up after 5 s
  (``lock_timeout``) instead of waiting for ever, so a stuck holder is an error
  with a clear SQLSTATE (55P03) rather than a hang.
* the audit chain's insert trigger takes the same row lock (it is now a definer
  function: it no longer depends on what the inserting role may touch).
* ``admin.loop_leases``: leadership of a background loop is a row with an expiry
  (a lease the leader renews on every pass), not a session advisory lock.

Expand-only: nothing is removed, the constants simply stop being used by the code.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant

revision: str = "0013_lock_rows_and_leases"
down_revision: Union[str, None] = "0012_setup_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "admin"
GENESIS_HASH_HEX = "49721f39819d393a7eb054f530ba3a3d317610b7ce438667a0580ce1df85badf"
LOCKS = ("audit_chain", "settings_writer", "signin", "setup_token")


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), **kw)


def upgrade() -> None:
    op.create_table(
        "lock_rows",
        sa.Column("name", sa.Text(), nullable=False),
        sa.CheckConstraint("name ~ '^[a-z_]{1,32}$'", name=op.f("ck_lock_rows_name")),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_lock_rows")),
        schema=S,
    )
    for name in LOCKS:
        op.execute(f"INSERT INTO admin.lock_rows (name) VALUES ('{name}')")
    op.execute(
        """
        CREATE FUNCTION admin.refuse_change() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            RAISE EXCEPTION 'admin.% does not allow % (fixed rows)', TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER lock_rows_frozen BEFORE INSERT OR UPDATE OR DELETE ON admin.lock_rows "
        "FOR EACH ROW EXECUTE FUNCTION admin.refuse_change()"
    )
    op.execute(
        "CREATE TRIGGER lock_rows_no_truncate BEFORE TRUNCATE ON admin.lock_rows "
        "FOR EACH STATEMENT EXECUTE FUNCTION admin.refuse_change()"
    )
    # FOR UPDATE does not fire UPDATE triggers (no row changes), so the row can be
    # locked and never changed
    op.execute(
        """
        CREATE FUNCTION admin.take_lock(p_name text) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, admin, pg_temp
        SET lock_timeout = '5s' AS $$
        BEGIN
            PERFORM 1 FROM admin.lock_rows WHERE name = p_name FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'admin.take_lock: unknown lock'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
        END $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION admin.take_lock(text) FROM PUBLIC")
    grant(op, "GRANT EXECUTE ON FUNCTION admin.take_lock(text) TO {role}")

    # the chain trigger: definer (owner: the migration role), the same row lock
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION admin.audit_log_check_chain() RETURNS trigger
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, admin, pg_temp
        SET lock_timeout = '5s' AS $$
        DECLARE
            head bytea;
            issued bigint;
        BEGIN
            PERFORM 1 FROM admin.lock_rows WHERE name = 'audit_chain' FOR UPDATE;
            BEGIN
                issued := currval('admin.audit_log_seq_seq');
            EXCEPTION WHEN object_not_in_prerequisite_state THEN
                issued := NULL;
            END;
            IF NEW.seq IS DISTINCT FROM issued THEN
                RAISE EXCEPTION 'admin.audit_log: seq must come from the identity'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
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

    op.create_table(
        "loop_leases",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("holder", sa.Text(), nullable=False),
        _ts("acquired_at", server_default=sa.text("clock_timestamp()"), nullable=False),
        _ts("expires_at", nullable=False),
        sa.CheckConstraint(
            "name ~ '^[a-z][a-z0-9_]{0,31}$'", name=op.f("ck_loop_leases_name")
        ),
        sa.CheckConstraint(
            "length(holder) BETWEEN 1 AND 128", name=op.f("ck_loop_leases_holder")
        ),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_loop_leases")),
        schema=S,
    )
    grant(op, "GRANT SELECT, INSERT ON admin.loop_leases TO {role}")
    grant(
        op,
        "GRANT UPDATE (holder, acquired_at, expires_at) ON admin.loop_leases TO {role}",
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
