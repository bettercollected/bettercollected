"""the task runner writes audit rows through narrow definer functions only

Revision ID: 0015_runner_audit_functions
Revises: 0014_history_immutable
Create Date: 2026-10-19

Until now the runner's role (``bc_tasks``) held INSERT and SELECT on the whole
audit log, so a database credential alone could write any ``system`` audit row,
including the "audit row for this write" that ``task_write_keyset`` demanded, and
could read every admin's address, IP and user agent. This revision removes both:

* ``tasks.begin_audit(settings)``: takes the writer and chain row locks (settings
  first, then the chain, the order the portal uses) and returns the chain head
  (hash and seq only) and the database clock.
* ``tasks.audit_append(...)``: appends one ``system`` row of a fixed kind. Run
  lifecycle rows (``task.run.started``, ``task.run.finished``) are accepted only
  for a run whose state changed in THIS transaction (started: now ``running``;
  finished: now terminal), once per run, with a fixed set of scalar detail keys; the
  aggregate ``task.run.quarantined`` row only for as many runs refused as
  ``bad_signature`` in this transaction; a task's own ``task.<name>`` event only for a
  run that is ``running``, capped per run. The portal's role may not write the
  reserved lifecycle actions (trigger), so a ``task.run.started`` row is evidence
  that the runner's function saw a run start.
* ``settings.task_write_keyset(...)`` is replaced (the old signature is dropped):
  it writes the ``settings.task_set`` audit row itself, from parameters it
  validates, and writes the keyset only for a ``running`` APPLY run of the task
  matching the action whose start was audited by the function above, at most once
  per run. ``settings.task_notify_reencrypt`` checks the same recorded start
  instead of an audit row the caller could have inserted.
* the functions are owned by ``bc_tasks_def`` (NOLOGIN; the roles script makes it and
  gives it only what the functions need), pin ``search_path``, and are executable by
  the runner's role alone.
* ``tasks.runs`` gets ``claim_attempts`` (the runner counts failed claims), the insert
  trigger stamps ``created_at`` with the database clock (queue order is no longer
  chosen by the inserter), zeroes ``claim_attempts`` and refuses an insert into a
  full queue (500 queued runs).

What the database cannot do is verify an HMAC (the keys are not in it): a row the
runner's function accepts carries the hash the caller computed, and an invalid one
is found by the audit chain verification (revision 0017) and ``settings.verify``.
"""

from typing import Sequence, Union

from alembic import op

from backend.admin.migration_support import (
    grant,
    hand_functions_to,
    role_name,
)

revision: str = "0015_runner_audit_functions"
down_revision: Union[str, None] = "0014_history_immutable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_WRITE_SIGNATURE = (
    "text, integer, bigint, text, text[], text, text, timestamptz, text, text, "
    "text, jsonb, text, text, text, jsonb"
)
WRITE_SIGNATURE = (
    OLD_WRITE_SIGNATURE + ", uuid, timestamptz, bytea, bytea, integer, jsonb, jsonb, jsonb"
)
NOTIFY_SIGNATURE = "text, bigint"
BEGIN_SIGNATURE = "boolean"
APPEND_SIGNATURE = (
    "text, text, text, text, jsonb, jsonb, jsonb, text, uuid, timestamptz, bytea, bytea, integer"
)
UUID = "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'"
IMMUTABLE = (
    "id", "task", "version", "params", "params_hash", "dry_run", "requested_by",
    "requested_at", "nonce", "resumes_run_id", "request_sig", "sig_version", "created_at",
)

def _reader_check(name: str) -> str:
    """The first statement of every runner function: only the runner's role."""
    return f"""
            IF NOT EXISTS (SELECT 1 FROM settings.reader_roles
                           WHERE role = session_user AND service = 'tasks') THEN
                RAISE EXCEPTION '{name}: not the task runner'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;"""


def upgrade() -> None:
    runtime = role_name("runtime")

    # ---- runs: claim attempts, DB-stamped created_at, bounded queue -------------
    op.execute("ALTER TABLE tasks.runs ADD COLUMN claim_attempts integer NOT NULL DEFAULT 0")
    grant(op, "GRANT UPDATE (claim_attempts) ON tasks.runs TO {role}", "tasks")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION tasks.runs_guard_insert() RETURNS trigger
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
            -- the queue is ordered by the database's clock, never by a value the
            -- inserter supplies
            NEW.created_at := clock_timestamp();
            NEW.claim_attempts := 0;
            IF (SELECT count(*) FROM tasks.runs WHERE state = 'queued') >= 500 THEN
                RAISE EXCEPTION 'tasks.runs: the queue is full'
                    USING ERRCODE = 'program_limit_exceeded';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    immutable_test = " OR ".join(f"NEW.{c} IS DISTINCT FROM OLD.{c}" for c in IMMUTABLE)
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION tasks.runs_guard_update() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, tasks AS $$
        BEGIN
            IF {immutable_test} THEN
                RAISE EXCEPTION 'tasks.runs: the request columns are immutable'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF NEW.claim_attempts < OLD.claim_attempts OR NEW.claim_attempts > OLD.claim_attempts + 1 THEN
                RAISE EXCEPTION 'tasks.runs: claim_attempts only counts up, one at a time'
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
    op.execute("CREATE INDEX ix_audit_log_request_id ON admin.audit_log (request_id, action)")

    # ---- the portal's role may not write the runner's lifecycle actions ---------
    op.execute(
        f"""
        CREATE FUNCTION admin.audit_reserved_actions() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            IF current_user = '{runtime}' AND NEW.action IN
               ('task.run.started', 'task.run.finished', 'task.run.quarantined', 'settings.task_set') THEN
                RAISE EXCEPTION 'audit action % is written by the task runner only', NEW.action
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_log_reserved_actions BEFORE INSERT ON admin.audit_log "
        "FOR EACH ROW EXECUTE FUNCTION admin.audit_reserved_actions()"
    )

    # ---- the runner's functions ---------------------------------------------------
    op.execute(
        f"""
        CREATE FUNCTION tasks.begin_audit(p_settings boolean)
        RETURNS TABLE (o_head bytea, o_seq bigint, o_now timestamptz)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp AS $$
        BEGIN{_reader_check('tasks.begin_audit')}
            IF p_settings THEN
                PERFORM admin.take_lock('settings_writer');
            END IF;
            PERFORM admin.take_lock('audit_chain');
            RETURN QUERY
                SELECT a.row_hash, a.seq, clock_timestamp()
                FROM (SELECT 1) one LEFT JOIN LATERAL
                     (SELECT l.row_hash, l.seq FROM admin.audit_log l ORDER BY l.seq DESC LIMIT 1) a
                     ON true;
        END $$
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION tasks.audit_append(
            p_action text, p_target_type text, p_target_id text, p_outcome text,
            p_before jsonb, p_after jsonb, p_detail jsonb, p_request_id text,
            p_id uuid, p_at timestamptz, p_prev bytea, p_hash bytea, p_key_version integer
        ) RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp AS $$
        DECLARE
            lifecycle_keys constant text[] := ARRAY['run_id', 'task', 'version', 'requested_by',
                'dry_run', 'runner', 'state', 'reason', 'error_class', 'events', 'truncated',
                'taken_over_by', 'previous_runner', 'count'];
            new_seq bigint;
        BEGIN{_reader_check('tasks.audit_append')}
            IF p_outcome IS NULL OR NOT (p_outcome = ANY (ARRAY['success', 'failure', 'denied']))
               OR p_id IS NULL OR p_at IS NULL OR p_key_version IS NULL
               OR p_key_version NOT BETWEEN 1 AND 1000
               OR p_prev IS NULL OR p_hash IS NULL OR length(p_prev) <> 32 OR length(p_hash) <> 32
               OR abs(extract(epoch FROM (clock_timestamp() - p_at))) > 120
               OR p_detail IS NULL OR jsonb_typeof(p_detail) <> 'object'
               OR octet_length(p_detail::text) >= 8192
               OR (p_before IS NOT NULL AND (jsonb_typeof(p_before) <> 'object' OR octet_length(p_before::text) >= 8192))
               OR (p_after IS NOT NULL AND (jsonb_typeof(p_after) <> 'object' OR octet_length(p_after::text) >= 8192))
               OR length(coalesce(p_target_type, '')) > 64 OR length(coalesce(p_target_id, '')) > 128 THEN
                RAISE EXCEPTION 'tasks.audit_append: invalid row' USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF p_action = 'task.run.quarantined' THEN
                IF p_target_type IS DISTINCT FROM 'task_runs' OR p_target_id IS NOT NULL
                   OR p_request_id IS NOT NULL
                   OR p_before IS NOT NULL OR p_after IS NOT NULL
                   OR coalesce(p_detail ->> 'count', '') !~ '^[0-9]{{1,2}}$'
                   OR (p_detail ->> 'count')::int NOT BETWEEN 1 AND 50
                   OR EXISTS (SELECT 1 FROM jsonb_each(p_detail) e
                              WHERE e.key <> ALL (ARRAY['count', 'runner'])
                                 OR jsonb_typeof(e.value) IN ('object', 'array')) THEN
                    RAISE EXCEPTION 'tasks.audit_append: invalid quarantine row'
                        USING ERRCODE = 'invalid_parameter_value';
                END IF;
                IF (SELECT count(*) FROM tasks.runs r
                    WHERE r.xmin = pg_current_xact_id()::xid AND r.state = 'refused'
                      AND r.refusal_code = 'bad_signature') < (p_detail ->> 'count')::int THEN
                    RAISE EXCEPTION 'tasks.audit_append: no such refusals in this transaction'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            ELSIF p_request_id IS NULL OR p_request_id !~ {UUID} THEN
                RAISE EXCEPTION 'tasks.audit_append: a run row names its run'
                    USING ERRCODE = 'invalid_parameter_value';
            ELSIF p_action IN ('task.run.started', 'task.run.finished') THEN
                IF p_target_type IS DISTINCT FROM 'task_run' OR p_target_id IS DISTINCT FROM p_request_id
                   OR p_before IS NOT NULL OR p_after IS NOT NULL
                   OR p_detail ->> 'run_id' IS DISTINCT FROM p_request_id
                   OR EXISTS (SELECT 1 FROM jsonb_each(p_detail) e
                              WHERE e.key <> ALL (lifecycle_keys)
                                 OR jsonb_typeof(e.value) IN ('object', 'array')
                                 OR length(e.value::text) > 400) THEN
                    RAISE EXCEPTION 'tasks.audit_append: invalid run row'
                        USING ERRCODE = 'invalid_parameter_value';
                END IF;
                IF p_action = 'task.run.started' THEN
                    IF p_outcome <> 'success' OR NOT EXISTS (
                        SELECT 1 FROM tasks.runs r
                        WHERE r.id = p_request_id::uuid AND r.state = 'running'
                          AND r.xmin = pg_current_xact_id()::xid) THEN
                        RAISE EXCEPTION 'tasks.audit_append: the run did not start in this transaction'
                            USING ERRCODE = 'insufficient_privilege';
                    END IF;
                ELSIF NOT EXISTS (
                    SELECT 1 FROM tasks.runs r
                    WHERE r.id = p_request_id::uuid AND r.finished_at IS NOT NULL
                      AND r.state IN ('succeeded', 'failed', 'refused', 'cancelled', 'interrupted')
                      AND r.xmin = pg_current_xact_id()::xid) THEN
                    RAISE EXCEPTION 'tasks.audit_append: the run did not end in this transaction'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                IF EXISTS (SELECT 1 FROM admin.audit_log a
                           WHERE a.request_id = p_request_id AND a.action = p_action) THEN
                    RAISE EXCEPTION 'tasks.audit_append: already recorded for this run'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
            ELSIF p_action ~ '^task\\.[a-z0-9_.-]{{1,100}}$' AND p_action NOT LIKE 'task.run.%' THEN
                IF p_detail ->> 'run_id' IS DISTINCT FROM p_request_id
                   OR NOT EXISTS (SELECT 1 FROM tasks.runs r
                                  WHERE r.id = p_request_id::uuid AND r.state = 'running')
                   OR (SELECT count(*) FROM admin.audit_log a WHERE a.request_id = p_request_id) >= 1000 THEN
                    RAISE EXCEPTION 'tasks.audit_append: no running run for this event'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
            ELSE
                RAISE EXCEPTION 'tasks.audit_append: action not allowed'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            INSERT INTO admin.audit_log
                (id, at, actor_kind, action, target_type, target_id, outcome,
                 before, after, detail, request_id, key_version, prev_hash, row_hash)
            VALUES (p_id, p_at, 'system', p_action, p_target_type, p_target_id, p_outcome,
                    p_before, p_after, p_detail, p_request_id, p_key_version, p_prev, p_hash)
            RETURNING seq INTO new_seq;
            RETURN new_seq;
        END $$
        """
    )

    op.execute(f"DROP FUNCTION settings.task_write_keyset({OLD_WRITE_SIGNATURE})")
    op.execute(
        rf"""
        CREATE FUNCTION settings.task_write_keyset(
            p_key text,
            p_expected_version integer,
            p_expected_revision bigint,
            p_section text,
            p_readers text[],
            p_blob text,
            p_updated_by text,
            p_updated_at timestamptz,
            p_sig text,
            p_history_actor text,
            p_manifest_digest text,
            p_manifest_entries jsonb,
            p_manifest_sig text,
            p_action text,
            p_run_id text,
            p_extra jsonb,
            p_audit_id uuid,
            p_audit_at timestamptz,
            p_audit_prev bytea,
            p_audit_hash bytea,
            p_audit_key_version integer,
            p_audit_before jsonb,
            p_audit_after jsonb,
            p_audit_detail jsonb
        ) RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp AS $$
        DECLARE
            allowed constant text[] := ARRAY['MASTER_ENCRYPTION_KEYSET'];
            cur settings.entries%ROWTYPE;
            run record;
            cur_revision bigint;
            cur_entries jsonb;
            new_version integer;
            new_revision bigint;
            audit_seq bigint;
        BEGIN{_reader_check('settings.task_write_keyset')}
            IF p_key IS NULL OR NOT (p_key = ANY (allowed)) THEN
                RAISE EXCEPTION 'settings.task_write_keyset: % is not task-writable', p_key
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            PERFORM admin.take_lock('settings_writer');
            SELECT revision, entries INTO cur_revision, cur_entries
                FROM settings.manifest WHERE id = 1 FOR UPDATE;
            IF cur_revision IS DISTINCT FROM p_expected_revision THEN
                RAISE EXCEPTION 'settings.task_write_keyset: stale revision'
                    USING ERRCODE = 'serialization_failure';
            END IF;
            SELECT * INTO cur FROM settings.entries WHERE key = p_key FOR UPDATE;
            IF NOT FOUND OR cur.cleared OR cur.tier <> 'T4' OR NOT cur.is_secret THEN
                RAISE EXCEPTION 'settings.task_write_keyset: nothing to update'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF cur.version <> p_expected_version THEN
                RAISE EXCEPTION 'settings.task_write_keyset: stale version'
                    USING ERRCODE = 'serialization_failure';
            END IF;
            new_version := cur.version + 1;
            new_revision := cur_revision + 1;
            IF p_section <> 'auth_keys' OR p_section <> cur.section
               OR p_blob IS NULL OR p_blob NOT LIKE 'v2:%' OR octet_length(p_blob) > 16384
               OR p_sig IS NULL OR p_sig !~ '^[0-9a-f]{{64}}$'
               OR p_manifest_digest IS NULL OR p_manifest_digest !~ '^[0-9a-f]{{64}}$'
               OR p_manifest_sig IS NULL OR p_manifest_sig !~ '^[0-9a-f]{{64}}$'
               OR p_updated_by IS NULL OR length(p_updated_by) NOT BETWEEN 1 AND 320
               OR p_history_actor IS NULL OR length(p_history_actor) NOT BETWEEN 1 AND 320
               OR p_action IS NULL OR NOT (p_action = ANY (ARRAY['add_key', 'promote', 'drop_old']))
               OR p_readers IS NULL OR cardinality(p_readers) NOT BETWEEN 1 AND 16
               OR p_readers IS DISTINCT FROM
                  (SELECT array_agg(DISTINCT r ORDER BY r) FROM unnest(cur.readers || 'tasks'::text) r)
               OR p_run_id IS NULL OR p_run_id !~ {UUID}
               OR p_updated_at IS NULL
               OR abs(extract(epoch FROM (clock_timestamp() - p_updated_at))) > 120 THEN
                RAISE EXCEPTION 'settings.task_write_keyset: invalid row'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF jsonb_typeof(p_manifest_entries) IS DISTINCT FROM 'object'
               OR (p_manifest_entries - p_key) IS DISTINCT FROM (cur_entries - p_key)
               OR (p_manifest_entries -> p_key)
                  IS DISTINCT FROM jsonb_build_array(new_version, p_sig, to_jsonb(p_readers)) THEN
                RAISE EXCEPTION 'settings.task_write_keyset: manifest does not match'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;

            -- the write is bound to a running APPLY run of the matching keyset task
            -- whose start the runner's audit function recorded; once per run
            SELECT r.task, r.state, r.dry_run INTO run FROM tasks.runs r WHERE r.id = p_run_id::uuid;
            IF NOT FOUND OR run.state <> 'running' OR run.dry_run
               OR run.task <> 'keyset.' || p_action THEN
                RAISE EXCEPTION 'settings.task_write_keyset: no running apply run for this write'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT EXISTS (SELECT 1 FROM admin.audit_log a
                           WHERE a.request_id = p_run_id AND a.action = 'task.run.started'
                             AND a.actor_kind = 'system' AND a.target_type = 'task_run'
                             AND a.target_id = p_run_id) THEN
                RAISE EXCEPTION 'settings.task_write_keyset: the start of the run was not recorded'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF EXISTS (SELECT 1 FROM admin.audit_log a
                       WHERE a.request_id = p_run_id AND a.action = 'settings.task_set') THEN
                RAISE EXCEPTION 'settings.task_write_keyset: this run already wrote'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            -- the audit row for this write, made here from validated parts
            IF p_audit_id IS NULL OR p_audit_at IS NULL OR p_audit_key_version IS NULL
               OR p_audit_key_version NOT BETWEEN 1 AND 1000
               OR p_audit_prev IS NULL OR p_audit_hash IS NULL
               OR length(p_audit_prev) <> 32 OR length(p_audit_hash) <> 32
               OR abs(extract(epoch FROM (clock_timestamp() - p_audit_at))) > 120
               OR jsonb_typeof(p_audit_before) IS DISTINCT FROM 'object'
               OR jsonb_typeof(p_audit_after) IS DISTINCT FROM 'object'
               OR jsonb_typeof(p_audit_detail) IS DISTINCT FROM 'object'
               OR octet_length(p_audit_before::text) >= 8192
               OR octet_length(p_audit_after::text) >= 8192
               OR octet_length(p_audit_detail::text) >= 8192
               OR EXISTS (SELECT 1 FROM jsonb_object_keys(p_audit_before) k
                          WHERE k <> ALL (ARRAY['setting', 'secret', 'version']))
               OR EXISTS (SELECT 1 FROM jsonb_object_keys(p_audit_after) k
                          WHERE k <> ALL (ARRAY['setting', 'secret', 'version', 'digest']))
               OR p_audit_before ->> 'setting' IS DISTINCT FROM p_key
               OR p_audit_after ->> 'setting' IS DISTINCT FROM p_key
               OR p_audit_before ->> 'version' IS DISTINCT FROM cur.version::text
               OR p_audit_after ->> 'version' IS DISTINCT FROM new_version::text
               OR coalesce(p_audit_after ->> 'digest', '') !~ '^[0-9a-f]{{64}}$'
               OR p_audit_detail ->> 'revision' IS DISTINCT FROM new_revision::text
               OR p_audit_detail ->> 'run_id' IS DISTINCT FROM p_run_id
               OR p_audit_detail ->> 'task' IS DISTINCT FROM run.task
               OR p_audit_detail ->> 'tier' IS DISTINCT FROM 'T4'
               OR EXISTS (SELECT 1 FROM jsonb_each(p_audit_detail) e
                          WHERE jsonb_typeof(e.value) IN ('object', 'array')) THEN
                RAISE EXCEPTION 'settings.task_write_keyset: invalid audit row'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            PERFORM admin.take_lock('audit_chain');
            INSERT INTO admin.audit_log
                (id, at, actor_kind, action, target_type, target_id, outcome,
                 before, after, detail, request_id, key_version, prev_hash, row_hash)
            VALUES (p_audit_id, p_audit_at, 'system', 'settings.task_set', 'setting', p_key,
                    'success', p_audit_before, p_audit_after, p_audit_detail, p_run_id,
                    p_audit_key_version, p_audit_prev, p_audit_hash)
            RETURNING seq INTO audit_seq;

            UPDATE settings.entries SET
                readers = p_readers, blob = p_blob, version = new_version,
                source = 'task', updated_by = p_updated_by, updated_at = p_updated_at,
                sig = p_sig
            WHERE key = p_key;
            INSERT INTO settings.history
                (key, version, section, is_secret, value, blob, cleared, action, source, actor, at)
            VALUES (p_key, new_version, p_section, true, NULL, p_blob, false, 'set', 'task',
                    p_history_actor, p_updated_at);
            UPDATE settings.manifest SET
                revision = new_revision, digest = p_manifest_digest,
                entries = p_manifest_entries, sig = p_manifest_sig
            WHERE id = 1;
            INSERT INTO admin.notifications (kind, payload, audit_seq)
            VALUES ('settings.keyset_changed',
                    jsonb_build_object('setting', p_key, 'tier', 'T4', 'action', p_action,
                                       'version', new_version, 'actor', p_history_actor,
                                       'run_id', p_run_id)
                    || coalesce((SELECT jsonb_object_agg(k, v) FROM jsonb_each(p_extra) e(k, v)
                                 WHERE k = ANY (ARRAY['added_key_id', 'primary_id', 'dropped_count'])
                                   AND jsonb_typeof(v) = 'number'), '{{}}'::jsonb),
                    audit_seq);
            RETURN new_revision;
        END $$
        """
    )
    op.execute(
        rf"""
        CREATE OR REPLACE FUNCTION settings.task_notify_reencrypt(p_run_id text, p_primary_id bigint)
        RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp AS $$
        DECLARE
            started record;
        BEGIN{_reader_check('settings.task_notify_reencrypt')}
            IF p_run_id IS NULL OR p_run_id !~ {UUID}
               OR p_primary_id IS NULL OR p_primary_id NOT BETWEEN 1 AND 4294967295 THEN
                RAISE EXCEPTION 'settings.task_notify_reencrypt: invalid arguments'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            -- only for a running APPLY run of keyset.reencrypt whose start the
            -- runner's audit function recorded, once per run
            IF NOT EXISTS (SELECT 1 FROM tasks.runs r
                           WHERE r.id = p_run_id::uuid AND r.state = 'running'
                             AND r.task = 'keyset.reencrypt' AND NOT r.dry_run) THEN
                RAISE EXCEPTION 'settings.task_notify_reencrypt: no running apply run'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT a.seq, a.detail ->> 'requested_by' AS requested_by INTO started
                FROM admin.audit_log a
                WHERE a.request_id = p_run_id
                  AND a.action = 'task.run.started' AND a.actor_kind = 'system'
                  AND a.target_type = 'task_run' AND a.target_id = p_run_id
                  AND a.detail ->> 'task' = 'keyset.reencrypt'
                  AND a.detail ->> 'dry_run' = 'false'
                ORDER BY a.seq DESC LIMIT 1;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'settings.task_notify_reencrypt: the start of the run was not recorded'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF EXISTS (SELECT 1 FROM admin.notifications
                       WHERE kind = 'settings.keyset_reencrypt' AND payload ->> 'run_id' = p_run_id) THEN
                RETURN;
            END IF;
            INSERT INTO admin.notifications (kind, payload, audit_seq)
            VALUES ('settings.keyset_reencrypt',
                    jsonb_build_object('setting', 'MASTER_ENCRYPTION_KEYSET', 'tier', 'T4',
                                       'action', 'reencrypt', 'run_id', p_run_id,
                                       'primary_id', p_primary_id,
                                       'actor', left(coalesce(started.requested_by, 'task'), 320)),
                    started.seq);
        END $$
        """
    )

    # ---- execute rights: the runner's role only -----------------------------------
    for name, signature in (
        ("tasks.begin_audit", BEGIN_SIGNATURE),
        ("tasks.audit_append", APPEND_SIGNATURE),
        ("settings.task_write_keyset", WRITE_SIGNATURE),
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {name}({signature}) FROM PUBLIC")
        grant(op, f"GRANT EXECUTE ON FUNCTION {name}({signature}) TO {{role}}", "tasks")
    op.execute(f"REVOKE ALL ON FUNCTION settings.task_notify_reencrypt({NOTIFY_SIGNATURE}) FROM PUBLIC")
    grant(
        op,
        f"GRANT EXECUTE ON FUNCTION settings.task_notify_reencrypt({NOTIFY_SIGNATURE}) TO {{role}}",
        "tasks",
    )

    # ---- the definer role: exactly what the functions touch ------------------------
    for statement in (
        "GRANT USAGE ON SCHEMA admin, tasks, settings TO {role}",
        "GRANT EXECUTE ON FUNCTION admin.take_lock(text) TO {role}",
        "GRANT INSERT ON admin.audit_log TO {role}",
        "GRANT SELECT (seq, row_hash, request_id, action, actor_kind, target_type, target_id, detail) "
        "ON admin.audit_log TO {role}",
        "GRANT USAGE ON SEQUENCE admin.audit_log_seq_seq TO {role}",
        "GRANT SELECT ON tasks.runs TO {role}",
        "GRANT SELECT ON settings.entries, settings.manifest, settings.reader_roles TO {role}",
        "GRANT UPDATE (readers, blob, version, source, updated_by, updated_at, sig) "
        "ON settings.entries TO {role}",
        "GRANT UPDATE (revision, digest, entries, sig) ON settings.manifest TO {role}",
        "GRANT SELECT, INSERT ON settings.history TO {role}",
        "GRANT SELECT, INSERT ON admin.notifications TO {role}",
    ):
        grant(op, statement, "tasks_def")
    # the runner loses the log
    grant(op, "REVOKE ALL ON admin.audit_log FROM {role}", "tasks")
    grant(op, "REVOKE ALL ON SEQUENCE admin.audit_log_seq_seq FROM {role}", "tasks")

    hand_functions_to(
        op,
        "tasks_def",
        (
            f"tasks.begin_audit({BEGIN_SIGNATURE})",
            f"tasks.audit_append({APPEND_SIGNATURE})",
            f"settings.task_write_keyset({WRITE_SIGNATURE})",
            f"settings.task_notify_reencrypt({NOTIFY_SIGNATURE})",
        ),
        ("tasks", "settings"),
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
