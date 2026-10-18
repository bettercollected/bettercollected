"""settings store: schema, tables, guards and the writer's privileges

Revision ID: 0004_settings_tables
Revises: 0003_audit_log
Create Date: 2026-10-18

Schema ``settings`` (created by the roles script, owned by the migration role):

* ``entries``: one signed row per setting. A cleared setting stays as a signed
  tombstone (``cleared``) so versions only ever go up.
* ``history``: every version written; the encrypted ones are pruned to five
  per setting (or purged) by the writer, and nothing else may change.
* ``manifest`` (single row): the signed ``key -> [version, sig, readers]``
  map of every row, which lets a reader notice a deleted or rolled-back row.
* ``service_state``: what each service reports about itself, written only by
  ``settings.report_state`` (revision 0005).

Guards bind the owner too: no DELETE or TRUNCATE on ``entries`` and
``manifest``; versions and the manifest revision only go up by one;
``history`` changes only by pruning encrypted rows that are not current and by
re-wrapping a blob.
"""

from typing import Sequence, Union

from alembic import op

from backend.admin.migration_support import grant

revision: str = "0004_settings_tables"
down_revision: Union[str, None] = "0003_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PAYLOAD = (
    "(cleared AND value IS NULL AND blob IS NULL) "
    "OR (NOT cleared AND is_secret AND blob IS NOT NULL AND value IS NULL) "
    "OR (NOT cleared AND NOT is_secret AND value IS NOT NULL AND blob IS NULL)"
)
SAME_ROW = (
    "(NEW.key, NEW.section, NEW.readers, NEW.is_secret, NEW.reload_class, NEW.tier, "
    "NEW.value, NEW.cleared, NEW.version, NEW.updated_at, NEW.updated_by, NEW.source) "
    "IS NOT DISTINCT FROM "
    "(OLD.key, OLD.section, OLD.readers, OLD.is_secret, OLD.reload_class, OLD.tier, "
    "OLD.value, OLD.cleared, OLD.version, OLD.updated_at, OLD.updated_by, OLD.source)"
)


def upgrade() -> None:
    # the roles script creates it; creating it here needs CREATE on the database,
    # which the migration role does not have, so only a missing schema is attempted
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'settings') "
        "THEN CREATE SCHEMA settings; END IF; END $$"
    )
    op.execute(
        f"""
        CREATE TABLE settings.entries (
            key text NOT NULL,
            section text NOT NULL,
            readers text[] NOT NULL,
            is_secret boolean NOT NULL,
            reload_class text NOT NULL,
            tier text NOT NULL,
            value jsonb,
            blob text,
            cleared boolean NOT NULL DEFAULT false,
            version integer NOT NULL,
            source text NOT NULL,
            updated_by text NOT NULL,
            updated_at timestamptz NOT NULL,
            sig text NOT NULL,
            CONSTRAINT pk_entries PRIMARY KEY (key),
            CONSTRAINT ck_entries_key CHECK (key ~ '^[A-Z][A-Z0-9_]{{0,63}}$'),
            CONSTRAINT ck_entries_section CHECK (section ~ '^[a-z][a-z0-9_]{{0,31}}$'),
            CONSTRAINT ck_entries_readers CHECK (
                cardinality(readers) BETWEEN 1 AND 16
                AND array_to_string(readers, ',')
                    ~ '^[a-z][a-z0-9_]{{0,31}}(,[a-z][a-z0-9_]{{0,31}})*$'),
            CONSTRAINT ck_entries_reload_class CHECK (reload_class IN ('B', 'H', 'R')),
            CONSTRAINT ck_entries_tier CHECK (tier IN ('T1', 'T2', 'T3', 'T4')),
            CONSTRAINT ck_entries_secret_tier CHECK (NOT is_secret OR tier <> 'T1'),
            CONSTRAINT ck_entries_key_material CHECK (tier <> 'T4' OR is_secret),
            CONSTRAINT ck_entries_payload CHECK ({PAYLOAD}),
            CONSTRAINT ck_entries_blob CHECK (
                blob IS NULL OR (blob LIKE 'v2:%' AND octet_length(blob) <= 16384)),
            CONSTRAINT ck_entries_value_size CHECK (
                value IS NULL OR pg_column_size(value) <= 70000),
            CONSTRAINT ck_entries_version CHECK (version >= 1),
            CONSTRAINT ck_entries_source CHECK (
                source IN ('portal', 'import', 'cli', 'task')),
            CONSTRAINT ck_entries_updated_by CHECK (
                length(updated_by) BETWEEN 1 AND 320),
            CONSTRAINT ck_entries_sig CHECK (sig ~ '^[0-9a-f]{{64}}$')
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE settings.history (
            key text NOT NULL,
            version integer NOT NULL,
            section text NOT NULL,
            is_secret boolean NOT NULL,
            value jsonb,
            blob text,
            cleared boolean NOT NULL DEFAULT false,
            action text NOT NULL,
            source text NOT NULL,
            actor text NOT NULL,
            at timestamptz NOT NULL,
            CONSTRAINT pk_history PRIMARY KEY (key, version),
            CONSTRAINT fk_history_key_entries FOREIGN KEY (key)
                REFERENCES settings.entries (key) ON DELETE RESTRICT,
            CONSTRAINT ck_history_payload CHECK ({PAYLOAD}),
            CONSTRAINT ck_history_blob CHECK (
                blob IS NULL OR (blob LIKE 'v2:%' AND octet_length(blob) <= 16384)),
            CONSTRAINT ck_history_version CHECK (version >= 1),
            CONSTRAINT ck_history_action CHECK (
                action IN ('set', 'clear', 'restore', 'import')),
            CONSTRAINT ck_history_source CHECK (
                source IN ('portal', 'import', 'cli', 'task')),
            CONSTRAINT ck_history_actor CHECK (length(actor) BETWEEN 1 AND 320)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE settings.manifest (
            id smallint NOT NULL DEFAULT 1,
            revision bigint NOT NULL,
            digest text NOT NULL,
            entries jsonb NOT NULL DEFAULT '{}',
            sig text NOT NULL,
            CONSTRAINT pk_manifest PRIMARY KEY (id),
            CONSTRAINT ck_manifest_entries CHECK (jsonb_typeof(entries) = 'object'),
            CONSTRAINT ck_manifest_single CHECK (id = 1),
            CONSTRAINT ck_manifest_revision CHECK (revision >= 0),
            CONSTRAINT ck_manifest_digest CHECK (digest ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_manifest_sig CHECK (sig = '' OR sig ~ '^[0-9a-f]{64}$')
        )
        """
    )
    # revision 0 = nothing written yet (placeholder digest, no signature)
    op.execute(
        "INSERT INTO settings.manifest (id, revision, digest, sig) "
        "VALUES (1, 0, repeat('0', 64), '')"
    )
    op.execute(
        """
        CREATE TABLE settings.service_state (
            service text NOT NULL,
            instance text NOT NULL,
            reported_at timestamptz NOT NULL DEFAULT now(),
            revision_applied bigint NOT NULL,
            env_overrides text[] NOT NULL DEFAULT '{}',
            rejected_keys text[] NOT NULL DEFAULT '{}',
            restart_pending boolean NOT NULL DEFAULT false,
            keyset_fp text NOT NULL DEFAULT '',
            CONSTRAINT pk_service_state PRIMARY KEY (service, instance),
            CONSTRAINT ck_service_state_service CHECK (service ~ '^[a-z][a-z0-9_]{0,31}$'),
            CONSTRAINT ck_service_state_instance CHECK (instance ~ '^[A-Za-z0-9_.:-]{1,64}$'),
            CONSTRAINT ck_service_state_revision CHECK (revision_applied >= 0),
            CONSTRAINT ck_service_state_keyset_fp CHECK (keyset_fp ~ '^[A-Za-z0-9_.:-]{0,64}$')
        )
        """
    )

    # ---- guards (they bind the owner as well as the writer)
    op.execute(
        """
        CREATE FUNCTION settings.refuse_change() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            RAISE EXCEPTION 'settings.% does not allow % (append-only or tombstoned)',
                TG_TABLE_NAME, TG_OP USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    for table in ("entries", "manifest"):
        op.execute(
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON settings.{table} "
            "FOR EACH ROW EXECUTE FUNCTION settings.refuse_change()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_no_truncate BEFORE TRUNCATE ON settings.{table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION settings.refuse_change()"
        )
    op.execute(
        "CREATE TRIGGER history_no_truncate BEFORE TRUNCATE ON settings.history "
        "FOR EACH STATEMENT EXECUTE FUNCTION settings.refuse_change()"
    )
    op.execute(
        f"""
        CREATE FUNCTION settings.entries_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, settings AS $$
        BEGIN
            IF NEW.key <> OLD.key THEN
                RAISE EXCEPTION 'settings.entries: the key cannot change'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF NEW.version = OLD.version THEN
                -- a re-wrap or a re-signature: nothing but blob and sig may differ
                IF NOT ({SAME_ROW}) THEN
                    RAISE EXCEPTION 'settings.entries: a same-version update may only change blob and sig'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
            ELSIF NEW.version <> OLD.version + 1 THEN
                RAISE EXCEPTION 'settings.entries: the version must go up by one'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER entries_guard BEFORE UPDATE ON settings.entries "
        "FOR EACH ROW EXECUTE FUNCTION settings.entries_guard()"
    )
    op.execute(
        """
        CREATE FUNCTION settings.history_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog, settings AS $$
        DECLARE
            current_version integer;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NOT OLD.is_secret
                   OR (NEW.key, NEW.version, NEW.section, NEW.is_secret, NEW.value,
                       NEW.cleared, NEW.action, NEW.source, NEW.actor, NEW.at)
                      IS DISTINCT FROM
                      (OLD.key, OLD.version, OLD.section, OLD.is_secret, OLD.value,
                       OLD.cleared, OLD.action, OLD.source, OLD.actor, OLD.at) THEN
                    RAISE EXCEPTION 'settings.history: only an encrypted blob may be re-wrapped'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                RETURN NEW;
            END IF;
            SELECT version INTO current_version FROM settings.entries WHERE key = OLD.key;
            IF NOT OLD.is_secret OR current_version IS NULL OR OLD.version >= current_version THEN
                RAISE EXCEPTION 'settings.history: only older encrypted versions can be pruned'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            RETURN OLD;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER history_guard BEFORE UPDATE OR DELETE ON settings.history "
        "FOR EACH ROW EXECUTE FUNCTION settings.history_guard()"
    )
    op.execute(
        """
        CREATE FUNCTION settings.manifest_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            IF NEW.revision <> OLD.revision + 1 THEN
                RAISE EXCEPTION 'settings.manifest: the revision must go up by one'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER manifest_guard BEFORE UPDATE ON settings.manifest "
        "FOR EACH ROW EXECUTE FUNCTION settings.manifest_guard()"
    )

    # ---- the writer: explicit, per table (there are no default privileges)
    grant(op, "GRANT USAGE ON SCHEMA settings TO {role}")
    grant(op, "GRANT SELECT, INSERT, UPDATE ON settings.entries TO {role}")
    grant(op, "GRANT SELECT, INSERT, DELETE ON settings.history TO {role}")
    grant(op, "GRANT UPDATE (blob) ON settings.history TO {role}")
    grant(op, "GRANT SELECT, INSERT, UPDATE ON settings.manifest TO {role}")
    grant(op, "GRANT SELECT ON settings.service_state TO {role}")


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
