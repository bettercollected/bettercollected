"""settings history is immutable; re-wrapping appends; the keyset row is task-only

Revision ID: 0014_history_immutable
Revises: 0013_lock_rows_and_leases
Create Date: 2026-10-19

* ``settings.history``: no role (the runtime role included) can change an existing
  row any more. The runtime role lost ``UPDATE (blob)`` and the guard trigger now
  refuses every UPDATE. A key dropped from the keyset stays readable in the
  history for backups, and that promise no longer depends on the portal's database
  credential. New versions are INSERTed as before.
* master-key rotation (``rewrap``) used to overwrite old history blobs in place.
  It now appends to ``settings.history_wraps``: a new row per re-wrapped blob,
  never replacing the original. A wrap is accepted only when it keeps the sealed
  value (the envelope's own nonce and ciphertext) and the shape of the original
  and changes the wrapped data key alone, so the table cannot hold anything but a
  re-keyed copy. Readers try the newest wrap first and fall back to older ones and
  to the original, so a junk row appended by a stolen credential cannot make a
  version unreadable, and ``verify()`` reports a version with no usable copy
  (``history_unreadable``).
* ``settings.entries``: a same-version update (re-wrap or re-sign) must keep the
  sealed value of the blob, and the portal's runtime role can no longer move the
  keyset (``MASTER_ENCRYPTION_KEYSET``) to a new version: only the task runner's
  function does. Rows are still HMAC-signed with a key the database never sees, so
  a row written by anyone without the master key is refused by every reader and
  reported by ``verify()``; what the guards add is that the keyset row cannot be
  damaged by the portal's credential alone.
"""

from typing import Sequence, Union

from alembic import op

from backend.admin.migration_support import grant, role_name

revision: str = "0014_history_immutable"
down_revision: Union[str, None] = "0013_lock_rows_and_leases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KEYSET = "MASTER_ENCRYPTION_KEYSET"
SAME_ROW = (
    "(NEW.key, NEW.section, NEW.readers, NEW.is_secret, NEW.reload_class, NEW.tier, "
    "NEW.value, NEW.cleared, NEW.version, NEW.updated_at, NEW.updated_by, NEW.source) "
    "IS NOT DISTINCT FROM "
    "(OLD.key, OLD.section, OLD.readers, OLD.is_secret, OLD.reload_class, OLD.tier, "
    "OLD.value, OLD.cleared, OLD.version, OLD.updated_at, OLD.updated_by, OLD.source)"
)


def upgrade() -> None:
    runtime = role_name("runtime")
    # v2:<kek_id>:<dek_nonce>:<wrapped_dek>:<nonce>:<ciphertext>; a re-wrap changes
    # the first four after "v2" and nothing else (the same shape and lengths)
    op.execute(
        r"""
        CREATE FUNCTION settings.same_sealed_value(p_old text, p_new text) RETURNS boolean
        LANGUAGE sql IMMUTABLE SET search_path = pg_catalog AS $$
            SELECT p_old IS NOT NULL AND p_new IS NOT NULL
               AND cardinality(string_to_array(p_old, ':')) = 6
               AND cardinality(string_to_array(p_new, ':')) = 6
               AND split_part(p_old, ':', 1) = 'v2' AND split_part(p_new, ':', 1) = 'v2'
               AND split_part(p_old, ':', 5) = split_part(p_new, ':', 5)
               AND split_part(p_old, ':', 6) = split_part(p_new, ':', 6)
               AND length(split_part(p_old, ':', 3)) = length(split_part(p_new, ':', 3))
               AND length(split_part(p_old, ':', 4)) = length(split_part(p_new, ':', 4))
        $$
        """
    )
    op.execute(
        r"""
        CREATE OR REPLACE FUNCTION settings.history_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, settings AS $$
        DECLARE
            current_version integer;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT version INTO current_version FROM settings.entries WHERE key = NEW.key;
                IF current_version IS NULL OR NEW.version <> current_version THEN
                    RAISE EXCEPTION 'settings.history: a row must match the entry''s current version'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                RAISE EXCEPTION 'settings.history: a version is never changed (re-wraps are appended to history_wraps)'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            SELECT version INTO current_version FROM settings.entries WHERE key = OLD.key;
            -- a key dropped from the keyset must stay readable in the history for backups
            IF EXISTS (SELECT 1 FROM settings.entries WHERE key = OLD.key AND tier = 'T4') THEN
                RAISE EXCEPTION 'settings.history: the history of a task-managed key is never pruned'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NOT OLD.is_secret OR current_version IS NULL OR OLD.version >= current_version THEN
                RAISE EXCEPTION 'settings.history: only older encrypted versions can be pruned'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN OLD;
        END $$
        """
    )
    op.execute("REVOKE UPDATE (blob) ON settings.history FROM PUBLIC")
    grant(op, "REVOKE UPDATE (blob) ON settings.history FROM {role}")

    op.execute(
        """
        CREATE TABLE settings.history_wraps (
            id bigint GENERATED ALWAYS AS IDENTITY,
            key text NOT NULL,
            version integer NOT NULL,
            blob text NOT NULL,
            at timestamptz NOT NULL DEFAULT clock_timestamp(),
            CONSTRAINT pk_history_wraps PRIMARY KEY (id),
            CONSTRAINT fk_history_wraps_history FOREIGN KEY (key, version)
                REFERENCES settings.history (key, version) ON DELETE CASCADE,
            CONSTRAINT ck_history_wraps_blob CHECK (
                blob LIKE 'v2:%' AND octet_length(blob) <= 16384)
        )
        """
    )
    op.execute(
        "CREATE INDEX ix_history_wraps_key_version ON settings.history_wraps (key, version, id)"
    )
    op.execute(
        r"""
        CREATE FUNCTION settings.history_wraps_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, settings AS $$
        DECLARE
            original text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                SELECT h.blob INTO original FROM settings.history h
                    WHERE h.key = NEW.key AND h.version = NEW.version AND h.is_secret;
                IF original IS NULL OR NOT settings.same_sealed_value(original, NEW.blob) THEN
                    RAISE EXCEPTION 'settings.history_wraps: a wrap keeps the sealed value of its version'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
                RETURN NEW;
            END IF;
            -- only the cascade of a pruned (older, non-task) history row may remove a wrap
            IF TG_OP = 'DELETE' AND NOT EXISTS (
                SELECT 1 FROM settings.history h WHERE h.key = OLD.key AND h.version = OLD.version) THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'settings.history_wraps is append-only (% refused)', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER history_wraps_guard BEFORE INSERT OR UPDATE OR DELETE ON settings.history_wraps "
        "FOR EACH ROW EXECUTE FUNCTION settings.history_wraps_guard()"
    )
    op.execute(
        "CREATE TRIGGER history_wraps_no_truncate BEFORE TRUNCATE ON settings.history_wraps "
        "FOR EACH STATEMENT EXECUTE FUNCTION settings.refuse_change()"
    )
    grant(op, "GRANT SELECT, INSERT ON settings.history_wraps TO {role}")
    grant(op, "GRANT USAGE ON SEQUENCE settings.history_wraps_id_seq TO {role}")

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION settings.entries_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, settings AS $$
        BEGIN
            IF NEW.key <> OLD.key THEN
                RAISE EXCEPTION 'settings.entries: the key cannot change'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF NEW.version = OLD.version THEN
                -- a re-wrap or a re-signature: nothing but blob and sig may differ,
                -- and a changed blob keeps its sealed value
                IF NOT ({SAME_ROW}) THEN
                    RAISE EXCEPTION 'settings.entries: a same-version update may only change blob and sig'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
                IF NEW.blob IS DISTINCT FROM OLD.blob
                   AND NOT settings.same_sealed_value(OLD.blob, NEW.blob) THEN
                    RAISE EXCEPTION 'settings.entries: a re-wrap keeps the sealed value'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
            ELSIF NEW.version <> OLD.version + 1 THEN
                RAISE EXCEPTION 'settings.entries: the version must go up by one'
                    USING ERRCODE = 'integrity_constraint_violation';
            ELSIF NEW.key = '{KEYSET}' AND current_user = '{runtime}' THEN
                -- the response keyset changes through tasks only (settings.task_write_keyset)
                RAISE EXCEPTION 'settings.entries: the keyset is changed by tasks only'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN NEW;
        END $$
        """
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
