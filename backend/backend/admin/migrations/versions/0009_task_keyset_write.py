"""the task runner's narrow path into the settings store

Revision ID: 0009_task_keyset_write
Revises: 0008_report_state_prune
Create Date: 2026-10-18

The keyset (``MASTER_ENCRYPTION_KEYSET``, tier T4) changes only through tasks,
and the task runner's role has no write privilege on ``settings.*``. Two
narrow additions, nothing broader:

* ``SELECT`` on ``settings.service_state``: the heartbeats the keyset tasks
  check before they promote or re-encrypt (names and revisions only).
* ``settings.task_write_keyset(...)``: ``SECURITY DEFINER``, executable by the
  runner's role alone (and it checks ``session_user`` is the ``tasks`` reader).
  The runner seals and signs the new row itself (it holds the master key); the
  function writes it only when ALL of these hold, in the writer's lock:

  - the key is on the function's allow-list (the keyset, nothing else);
  - the row exists already (the first write is the import) and is tier T4;
  - ``expected_version`` is the stored version, the new one is exactly one
    higher, and ``expected_revision`` is the manifest's revision;
  - the row is a secret in section ``auth_keys`` with a v2 envelope and
    well-formed signature, readers within the known services, ``updated_at``
    close to the database clock;
  - the manifest the runner signed equals the stored one in every other key,
    and carries the new row's version, signature and readers;
  - an audit row for this very write (action ``settings.task_set``, actor kind
    ``system``, the new version and revision) was already inserted in the same
    transaction (no audit row, no write).

  It then updates the entry, the history and the manifest like the portal's
  writer does. It cannot verify HMAC signatures (the keys are not in the
  database): a row signed wrongly is written but refused by every reader, and
  ``settings-verify`` reports it.
"""

from typing import Sequence, Union

from alembic import op

from backend.admin.migration_support import grant

revision: str = "0009_task_keyset_write"
down_revision: Union[str, None] = "0008_report_state_prune"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SIGNATURE = (
    "text, integer, bigint, text, text[], text, text, timestamptz, text, text, "
    "text, jsonb, text"
)


def upgrade() -> None:
    op.execute(
        r"""
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
            p_manifest_sig text
        ) RETURNS bigint
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, settings, admin AS $$
        DECLARE
            allowed constant text[] := ARRAY['MASTER_ENCRYPTION_KEYSET'];
            cur settings.entries%ROWTYPE;
            cur_revision bigint;
            cur_entries jsonb;
            new_version integer;
            new_revision bigint;
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM settings.reader_roles
                           WHERE role = session_user AND service = 'tasks') THEN
                RAISE EXCEPTION 'settings.task_write_keyset: not the task runner'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF p_key IS NULL OR NOT (p_key = ANY (allowed)) THEN
                RAISE EXCEPTION 'settings.task_write_keyset: % is not task-writable', p_key
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            PERFORM pg_advisory_xact_lock(7310952481203619855);
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
               OR p_sig IS NULL OR p_sig !~ '^[0-9a-f]{64}$'
               OR p_manifest_digest IS NULL OR p_manifest_digest !~ '^[0-9a-f]{64}$'
               OR p_manifest_sig IS NULL OR p_manifest_sig !~ '^[0-9a-f]{64}$'
               OR p_updated_by IS NULL OR length(p_updated_by) NOT BETWEEN 1 AND 320
               OR p_history_actor IS NULL OR length(p_history_actor) NOT BETWEEN 1 AND 320
               OR p_readers IS NULL OR cardinality(p_readers) NOT BETWEEN 1 AND 16
               OR NOT (p_readers <@ ARRAY['backend', 'auth', 'google', 'tasks', 'webapp', 'admin'])
               OR p_readers IS DISTINCT FROM (SELECT array_agg(r ORDER BY r) FROM unnest(p_readers) r)
               OR p_updated_at IS NULL
               OR abs(extract(epoch FROM (clock_timestamp() - p_updated_at))) > 120 THEN
                RAISE EXCEPTION 'settings.task_write_keyset: invalid row'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            -- the signed manifest differs from the stored one in this key only
            IF jsonb_typeof(p_manifest_entries) IS DISTINCT FROM 'object'
               OR (p_manifest_entries - p_key) IS DISTINCT FROM (cur_entries - p_key)
               OR (p_manifest_entries -> p_key)
                  IS DISTINCT FROM jsonb_build_array(new_version, p_sig, to_jsonb(p_readers)) THEN
                RAISE EXCEPTION 'settings.task_write_keyset: manifest does not match'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            -- no audit row, no write: the row for this write is already in this transaction
            IF NOT EXISTS (
                SELECT 1 FROM admin.audit_log a
                WHERE a.xmin = pg_current_xact_id()::xid
                  AND a.action = 'settings.task_set'
                  AND a.actor_kind = 'system'
                  AND a.outcome = 'success'
                  AND a.target_type = 'setting' AND a.target_id = p_key
                  AND a.after ->> 'version' = new_version::text
                  AND a.detail ->> 'revision' = new_revision::text
            ) THEN
                RAISE EXCEPTION 'settings.task_write_keyset: no audit row for this write'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;

            UPDATE settings.entries SET
                readers = p_readers, blob = p_blob, version = new_version,
                source = 'task', updated_by = p_updated_by, updated_at = p_updated_at,
                sig = p_sig
            WHERE key = p_key;
            INSERT INTO settings.history
                (key, version, section, is_secret, value, blob, cleared, action, source, actor, at)
            VALUES (p_key, new_version, p_section, true, NULL, p_blob, false, 'set', 'task',
                    p_history_actor, p_updated_at);
            DELETE FROM settings.history
                WHERE key = p_key AND is_secret AND version < new_version - 4;
            UPDATE settings.manifest SET
                revision = new_revision, digest = p_manifest_digest,
                entries = p_manifest_entries, sig = p_manifest_sig
            WHERE id = 1;
            RETURN new_revision;
        END $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION settings.task_write_keyset({SIGNATURE}) FROM PUBLIC")
    grant(op, f"GRANT EXECUTE ON FUNCTION settings.task_write_keyset({SIGNATURE}) TO {{role}}", "tasks")
    grant(op, "GRANT SELECT ON settings.service_state TO {role}", "tasks")


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
