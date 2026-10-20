"""services report which data stores they write

Revision ID: 0018_report_write_stores
Revises: 0017_audit_verify_state
Create Date: 2026-10-20

``settings.service_state.write_stores``: the data stores a service instance
writes, from its own ``DB_WRITE_MODE`` and ``DB_WRITE_MODE__<group>`` (``mongo``,
``postgres`` or ``mongo,postgres``; empty when it did not say). ``keyset.drop_old``
with ``mongo_retired`` refuses while a live keyset consumer reports Mongo, or
does not report at all.

Expand-only, rolling-deploy safe: a new seven-argument
``settings.report_state(..., p_write_stores)`` takes the value; the
six-argument function keeps its signature and grants and now stores an empty
value (unknown), so services that predate this revision keep reporting. The new
function has the same checks as 0016, ``SECURITY DEFINER`` and a pinned
``search_path``, and is executable by the store readers only.
"""

from typing import Sequence, Union

from alembic import op

from backend.admin.migration_support import READER_SERVICES, grant

revision: str = "0018_report_write_stores"
down_revision: Union[str, None] = "0017_audit_verify_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAME = r"^[A-Z][A-Z0-9_]{0,63}$"
OLD = "(text, bigint, text[], text[], boolean, text)"
NEW = "(text, bigint, text[], text[], boolean, text, text)"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE settings.service_state "
        "ADD COLUMN write_stores text NOT NULL DEFAULT '' "
        "CHECK (write_stores IN ('', 'mongo', 'postgres', 'mongo,postgres'))"
    )
    op.execute(
        rf"""
        CREATE FUNCTION settings.report_state(
            p_instance text,
            p_revision_applied bigint,
            p_env_overrides text[],
            p_rejected_keys text[],
            p_restart_pending boolean,
            p_keyset_fp text,
            p_write_stores text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, settings, pg_temp AS $$
        DECLARE
            svc text;
            env_names text[] := coalesce(p_env_overrides, '{{}}');
            rejected text[] := coalesce(p_rejected_keys, '{{}}');
            stores text := coalesce(p_write_stores, '');
        BEGIN
            SELECT service INTO svc FROM settings.reader_roles
            WHERE role = session_user::text;
            IF svc IS NULL THEN
                RAISE EXCEPTION 'settings.report_state: not a settings reader'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF p_instance IS NULL OR p_instance !~ '^[A-Za-z0-9_.:-]{{1,64}}$' THEN
                RAISE EXCEPTION 'settings.report_state: invalid instance'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF p_revision_applied IS NULL OR p_revision_applied < 0 THEN
                RAISE EXCEPTION 'settings.report_state: invalid revision'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF cardinality(env_names) > 300 OR cardinality(rejected) > 100
               OR EXISTS (SELECT 1 FROM unnest(env_names || rejected) n
                          WHERE n IS NULL OR n !~ '{NAME}') THEN
                RAISE EXCEPTION 'settings.report_state: invalid setting names'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF coalesce(p_keyset_fp, '') !~ '^[A-Za-z0-9_.:-]{{0,64}}$' THEN
                RAISE EXCEPTION 'settings.report_state: invalid fingerprint'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF stores NOT IN ('', 'mongo', 'postgres', 'mongo,postgres') THEN
                RAISE EXCEPTION 'settings.report_state: invalid write stores'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            rejected := coalesce((
                SELECT array_agg(DISTINCT n ORDER BY n) FROM unnest(rejected) n
                WHERE EXISTS (SELECT 1 FROM settings.entries e
                              WHERE e.key = n AND svc = ANY (e.readers))), '{{}}');
            DELETE FROM settings.service_state d
            WHERE d.ctid IN (
                SELECT s.ctid FROM settings.service_state s
                WHERE s.service = svc AND s.instance <> p_instance
                  AND s.reported_at < now() - interval '7 days'
                ORDER BY s.reported_at LIMIT 100);
            IF NOT EXISTS (SELECT 1 FROM settings.service_state
                           WHERE service = svc AND instance = p_instance)
               AND (SELECT count(*) FROM settings.service_state WHERE service = svc) >= 100 THEN
                RAISE EXCEPTION 'settings.report_state: too many instances'
                    USING ERRCODE = 'program_limit_exceeded';
            END IF;
            INSERT INTO settings.service_state AS s
                (service, instance, reported_at, revision_applied, env_overrides,
                 rejected_keys, restart_pending, keyset_fp, write_stores)
            VALUES (svc, p_instance, now(), p_revision_applied,
                    env_names, rejected, coalesce(p_restart_pending, false),
                    coalesce(p_keyset_fp, ''), stores)
            ON CONFLICT (service, instance) DO UPDATE SET
                reported_at = excluded.reported_at,
                revision_applied = excluded.revision_applied,
                env_overrides = excluded.env_overrides,
                rejected_keys = excluded.rejected_keys,
                restart_pending = excluded.restart_pending,
                keyset_fp = excluded.keyset_fp,
                write_stores = excluded.write_stores;
        END $$
        """
    )
    # the old signature: same checks and row, write stores unknown
    op.execute(
        """
        CREATE OR REPLACE FUNCTION settings.report_state(
            p_instance text,
            p_revision_applied bigint,
            p_env_overrides text[],
            p_rejected_keys text[],
            p_restart_pending boolean,
            p_keyset_fp text
        ) RETURNS void
        LANGUAGE sql SECURITY DEFINER
        SET search_path = pg_catalog, settings, pg_temp AS $$
            SELECT settings.report_state(p_instance, p_revision_applied, p_env_overrides,
                                         p_rejected_keys, p_restart_pending, p_keyset_fp, '');
        $$
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION settings.report_state{NEW} FROM PUBLIC")
    for logical in READER_SERVICES.values():
        grant(
            op,
            f"GRANT EXECUTE ON FUNCTION settings.report_state{NEW} TO {{role}}",
            logical,
        )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
