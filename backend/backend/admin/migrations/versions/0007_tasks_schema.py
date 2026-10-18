"""data task runner schema: runs, run_events, checkpoints, locks

Revision ID: 0007_tasks_schema
Revises: 0006_notifications_outbox
Create Date: 2026-10-18

Schema ``tasks`` holds the task runner's state. Two roles touch it, each with
exactly what it needs and nothing by default:

* the admin service (``bc_admin``): INSERT and SELECT on ``runs`` and
  UPDATE(cancel_requested_at) only; SELECT on the other tables. A trigger
  forces every inserted run to ``queued`` with no runner-owned column set, and
  lets ``cancel_requested_at`` be set once, so the admin side can ask but never
  declare a run started, finished or successful.
* the runner (``bc_tasks``): column-level UPDATE on the runner-owned columns of
  ``runs``, INSERT on ``run_events`` and ``checkpoints``, INSERT/DELETE/SELECT
  on ``locks`` and INSERT/SELECT on ``admin.audit_log`` (its chain trigger and
  advisory lock keep integrity). Nothing else in ``admin``.

Triggers bind the table owner too: the request columns of a run are immutable
and the state machine only moves forward. A lock's lease is its run's
``heartbeat_at`` (60 s, taken over after a 30 s grace), so locks need no UPDATE.
The runner's audit rows must carry actor_kind 'system' (trigger). Size CHECKs: an event row 2 KB, a result 8 KB, a cursor 2 KB.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.admin.migration_support import grant, role_name
from common.db.alembic_support import create_schema_if_missing_sql

revision: str = "0007_tasks_schema"
down_revision: Union[str, None] = "0006_notifications_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

S = "tasks"
STATES = "'queued','running','succeeded','failed','refused','cancelled','interrupted'"
IMMUTABLE = (
    "id",
    "task",
    "version",
    "params",
    "params_hash",
    "dry_run",
    "requested_by",
    "requested_at",
    "nonce",
    "resumes_run_id",
    "request_sig",
    "sig_version",
    "created_at",
)


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, postgresql.TIMESTAMP(timezone=True), **kw)


def upgrade() -> None:
    op.execute(create_schema_if_missing_sql(S))

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("params_hash", sa.Text(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        _ts("requested_at", nullable=False),
        sa.Column("nonce", sa.Text(), nullable=False),
        sa.Column("resumes_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("request_sig", sa.LargeBinary(), nullable=False),
        sa.Column("sig_version", sa.Integer(), server_default="1", nullable=False),
        _ts("created_at", server_default=sa.text("now()"), nullable=False),
        sa.Column("state", sa.Text(), server_default="queued", nullable=False),
        _ts("cancel_requested_at"),
        _ts("started_at"),
        _ts("finished_at"),
        _ts("heartbeat_at"),
        sa.Column("runner_id", sa.Text()),
        sa.Column("progress", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("refusal_code", sa.Text()),
        sa.CheckConstraint(f"state IN ({STATES})", name=op.f("ck_runs_state")),
        sa.CheckConstraint(
            "length(request_sig) = 32 AND length(params_hash) = 64",
            name=op.f("ck_runs_sig_lengths"),
        ),
        sa.CheckConstraint(
            "octet_length(params::text) <= 8192", name=op.f("ck_runs_params_size")
        ),
        sa.CheckConstraint(
            "result IS NULL OR octet_length(result::text) <= 8192",
            name=op.f("ck_runs_result_size"),
        ),
        sa.CheckConstraint(
            "progress IS NULL OR octet_length(progress::text) <= 512",
            name=op.f("ck_runs_progress_size"),
        ),
        sa.CheckConstraint(
            "refusal_code IS NULL OR refusal_code ~ '^[a-z][a-z0-9_]{0,47}$'",
            name=op.f("ck_runs_refusal_code"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
        sa.ForeignKeyConstraint(
            ["resumes_run_id"], [f"{S}.runs.id"], name=op.f("fk_runs_resumes_run_id_runs")
        ),
        schema=S,
    )
    op.create_index("ix_runs_state_created_at", "runs", ["state", "created_at"], schema=S)
    op.create_index(
        "ix_runs_task_params_hash", "runs", ["task", "params_hash", "finished_at"], schema=S
    )

    op.create_table(
        "run_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        _ts("at", server_default=sa.text("now()"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("counts", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("ids", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error_class", sa.Text()),
        sa.CheckConstraint(
            "octet_length(code) + octet_length(coalesce(counts::text, '')) "
            "+ octet_length(coalesce(ids::text, '')) "
            "+ octet_length(coalesce(error_class, '')) <= 2048",
            name=op.f("ck_run_events_row_size"),
        ),
        sa.CheckConstraint(
            "code ~ '^[a-z][a-z0-9_]{0,47}$'", name=op.f("ck_run_events_code")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_events")),
        sa.ForeignKeyConstraint(
            ["run_id"], [f"{S}.runs.id"], name=op.f("fk_run_events_run_id_runs")
        ),
        schema=S,
    )
    op.create_index("uq_run_events_run_seq", "run_events", ["run_id", "seq"], unique=True, schema=S)
    op.create_index("ix_run_events_at", "run_events", ["at"], schema=S)

    op.create_table(
        "checkpoints",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        _ts("at", server_default=sa.text("now()"), nullable=False),
        sa.Column("cursor", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "octet_length(cursor::text) <= 2048", name=op.f("ck_checkpoints_cursor_size")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_checkpoints")),
        sa.ForeignKeyConstraint(
            ["run_id"], [f"{S}.runs.id"], name=op.f("fk_checkpoints_run_id_runs")
        ),
        schema=S,
    )
    op.create_index("ix_checkpoints_run_id_id", "checkpoints", ["run_id", "id"], schema=S)

    op.create_table(
        "locks",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("runner_id", sa.Text(), nullable=False),
        _ts("acquired_at", server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("name", name=op.f("pk_locks")),
        sa.ForeignKeyConstraint(
            ["run_id"], [f"{S}.runs.id"], name=op.f("fk_locks_run_id_runs")
        ),
        schema=S,
    )
    op.create_index("ix_locks_run_id", "locks", ["run_id"], schema=S)

    # -- runs: insert guard (all roles, the owner included) --------------------
    op.execute(
        """
        CREATE FUNCTION tasks.runs_guard_insert() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, tasks AS $$
        BEGIN
            IF NEW.state <> 'queued'
               OR NEW.cancel_requested_at IS NOT NULL
               OR NEW.started_at IS NOT NULL OR NEW.finished_at IS NOT NULL
               OR NEW.heartbeat_at IS NOT NULL OR NEW.runner_id IS NOT NULL
               OR NEW.progress IS NOT NULL OR NEW.result IS NOT NULL
               OR NEW.refusal_code IS NOT NULL THEN
                RAISE EXCEPTION 'tasks.runs: a run is inserted queued and untouched'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER runs_guard_insert BEFORE INSERT ON tasks.runs "
        "FOR EACH ROW EXECUTE FUNCTION tasks.runs_guard_insert()"
    )
    # -- runs: update guard: immutable request, forward-only state --------------
    immutable_test = " OR ".join(f"NEW.{c} IS DISTINCT FROM OLD.{c}" for c in IMMUTABLE)
    op.execute(
        f"""
        CREATE FUNCTION tasks.runs_guard_update() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, tasks AS $$
        BEGIN
            IF {immutable_test} THEN
                RAISE EXCEPTION 'tasks.runs: the request columns are immutable'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF OLD.cancel_requested_at IS NOT NULL
               AND NEW.cancel_requested_at IS DISTINCT FROM OLD.cancel_requested_at THEN
                RAISE EXCEPTION 'tasks.runs: cancel_requested_at is set once'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF NEW.state IS DISTINCT FROM OLD.state AND NOT (
                (OLD.state = 'queued' AND NEW.state IN ('running', 'refused', 'cancelled', 'failed'))
                OR (OLD.state = 'running'
                    AND NEW.state IN ('succeeded', 'failed', 'refused', 'cancelled', 'interrupted'))
            ) THEN
                RAISE EXCEPTION 'tasks.runs: illegal state change % -> %', OLD.state, NEW.state
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER runs_guard_update BEFORE UPDATE ON tasks.runs "
        "FOR EACH ROW EXECUTE FUNCTION tasks.runs_guard_update()"
    )
    # -- history is append-only for everyone ------------------------------------
    op.execute(
        """
        CREATE FUNCTION tasks.refuse_change() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            RAISE EXCEPTION 'tasks.% is append-only (% refused)', TG_TABLE_NAME, TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in ("run_events", "checkpoints"):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE ON tasks.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION tasks.refuse_change()"
        )

    # -- the runner may only write audit rows as itself ---------------------------
    # bc_tasks holds INSERT on admin.audit_log; this trigger (which also binds a
    # superuser connecting as that role) refuses any row it writes whose
    # actor_kind is not 'system', so a compromised runner cannot forge entries
    # that look like an admin's or the CLI's.
    runner = role_name("tasks")
    op.execute(
        f"""
        CREATE FUNCTION tasks.audit_actor_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            IF (session_user = '{runner}' OR current_user = '{runner}')
               AND NEW.actor_kind IS DISTINCT FROM 'system' THEN
                RAISE EXCEPTION 'the task runner writes audit rows as system only'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_log_runner_actor BEFORE INSERT ON admin.audit_log "
        "FOR EACH ROW EXECUTE FUNCTION tasks.audit_actor_guard()"
    )

    # -- grants (explicit per table; no default privileges) -----------------------
    grant(op, "GRANT USAGE ON SCHEMA tasks TO {role}", "runtime")
    grant(op, "GRANT USAGE ON SCHEMA tasks TO {role}", "tasks")
    grant(op, "GRANT SELECT, INSERT ON tasks.runs TO {role}", "runtime")
    grant(op, "GRANT UPDATE (cancel_requested_at) ON tasks.runs TO {role}", "runtime")
    for table in ("run_events", "checkpoints", "locks"):
        grant(op, f"GRANT SELECT ON tasks.{table} TO {{role}}", "runtime")

    grant(op, "GRANT SELECT ON tasks.runs TO {role}", "tasks")
    grant(
        op,
        "GRANT UPDATE (state, progress, heartbeat_at, result, refusal_code, runner_id, "
        "started_at, finished_at) ON tasks.runs TO {role}",
        "tasks",
    )
    grant(op, "GRANT SELECT, INSERT ON tasks.run_events, tasks.checkpoints TO {role}", "tasks")
    grant(
        op,
        "GRANT USAGE ON SEQUENCE tasks.run_events_id_seq, tasks.checkpoints_id_seq TO {role}",
        "tasks",
    )
    grant(op, "GRANT SELECT, INSERT, DELETE ON tasks.locks TO {role}", "tasks")
    grant(op, "GRANT SELECT, INSERT ON admin.audit_log TO {role}", "tasks")
    grant(op, "GRANT USAGE ON SEQUENCE admin.audit_log_seq_seq TO {role}", "tasks")
    grant(op, "REVOKE UPDATE, DELETE, TRUNCATE ON admin.audit_log FROM {role}", "tasks")


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
