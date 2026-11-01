"""the auth key rings may be written by the authkeys.* tasks

Revision ID: 0020_authkeys_task_write
Revises: 0019_service_state_delete_guard
Create Date: 2026-11-01

``settings.task_write_keyset`` (revision 0015) writes the response keyset only,
and only for a running APPLY run of the ``keyset.<action>`` task. The two auth
key rings (``AUTH_JWT_SECRET``, ``AUTH_AES_HEX_KEY``, docs/auth-key-rotation.md)
are rotated the same way, by the ``authkeys.<action>`` tasks, so the function is
replaced (same signature, so the owner, the grants and the roles script's loop
over it are untouched) with exactly two changes:

* the allow-list holds the two ring keys beside the keyset;
* the run binding ties each key to its own task family: the keyset to
  ``keyset.<action>``, a ring key to ``authkeys.<action>``. A ``keyset.*`` run
  can therefore never write a ring and an ``authkeys.*`` run can never write
  the keyset. Which of the two rings an ``authkeys.*`` run writes is recorded
  in the audit row (the setting name), not in the database's check.

Everything else is unchanged: reader check, version and revision compare-and-swap,
signed manifest, an audit row built from validated parts, the run must be
``running`` with its start recorded, once per run, and the notice for all admins.
Expand-only; downgrade is not supported, like the other revisions.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0020_authkeys_task_write"
down_revision: Union[str, None] = "0019_service_state_delete_guard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'"


def _reader_check(name: str) -> str:
    """The first statement of every runner function: only the runner's role."""
    return f"""
            IF NOT EXISTS (SELECT 1 FROM settings.reader_roles
                           WHERE role = session_user AND service = 'tasks') THEN
                RAISE EXCEPTION '{name}: not the task runner'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;"""


def upgrade() -> None:
    op.execute(
        rf"""
        CREATE OR REPLACE FUNCTION settings.task_write_keyset(
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
            allowed constant text[] := ARRAY['MASTER_ENCRYPTION_KEYSET', 'AUTH_JWT_SECRET', 'AUTH_AES_HEX_KEY'];
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
               OR NOT ((p_key = 'MASTER_ENCRYPTION_KEYSET' AND run.task = 'keyset.' || p_action)
                       OR (p_key = ANY (ARRAY['AUTH_JWT_SECRET', 'AUTH_AES_HEX_KEY'])
                           AND run.task = 'authkeys.' || p_action)) THEN
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


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
