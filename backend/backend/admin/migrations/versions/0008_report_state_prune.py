"""settings.report_state prunes the caller's stale instance rows

Revision ID: 0008_report_state_prune
Revises: 0007_tasks_schema
Create Date: 2026-10-18

Instances come and go with containers (each recreation is a new instance id), so
rows nobody refreshes would eventually fill the 100-instance cap and make reports
fail. ``report_state`` now deletes the calling service's rows not reported for 7
days (never another service's, never the caller's own instance, at most 100 per
call) before it checks the cap. Replaces the function from 0005 with the same
signature, ``SECURITY DEFINER`` and pinned ``search_path``; the execute grants are
re-applied exactly as in 0005.
"""

from typing import Sequence, Union

from alembic import op

from backend.admin.migration_support import READER_SERVICES, grant

revision: str = "0008_report_state_prune"
down_revision: Union[str, None] = "0007_tasks_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAME = r"^[A-Z][A-Z0-9_]{0,63}$"


def upgrade() -> None:
    op.execute(
        rf"""
        CREATE OR REPLACE FUNCTION settings.report_state(
            p_instance text,
            p_revision_applied bigint,
            p_env_overrides text[],
            p_rejected_keys text[],
            p_restart_pending boolean,
            p_keyset_fp text
        ) RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, settings, pg_temp AS $$
        DECLARE
            svc text;
            env_names text[] := coalesce(p_env_overrides, '{{}}');
            rejected text[] := coalesce(p_rejected_keys, '{{}}');
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
            IF cardinality(env_names) > 500 OR cardinality(rejected) > 500
               OR EXISTS (SELECT 1 FROM unnest(env_names || rejected) n
                          WHERE n IS NULL OR n !~ '{NAME}') THEN
                RAISE EXCEPTION 'settings.report_state: invalid setting names'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            IF coalesce(p_keyset_fp, '') !~ '^[A-Za-z0-9_.:-]{{0,64}}$' THEN
                RAISE EXCEPTION 'settings.report_state: invalid fingerprint'
                    USING ERRCODE = 'invalid_parameter_value';
            END IF;
            -- instances come and go with containers: drop this service's rows not
            -- reported for 7 days (never another service's, never a recent row;
            -- at most 100 per call) before the cap is checked
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
                 rejected_keys, restart_pending, keyset_fp)
            VALUES (svc, p_instance, now(), p_revision_applied, env_names, rejected,
                    coalesce(p_restart_pending, false), coalesce(p_keyset_fp, ''))
            ON CONFLICT (service, instance) DO UPDATE SET
                reported_at = excluded.reported_at,
                revision_applied = excluded.revision_applied,
                env_overrides = excluded.env_overrides,
                rejected_keys = excluded.rejected_keys,
                restart_pending = excluded.restart_pending,
                keyset_fp = excluded.keyset_fp;
        END $$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION settings.report_state"
        "(text, bigint, text[], text[], boolean, text) FROM PUBLIC"
    )

    for service, logical in READER_SERVICES.items():
        grant(
            op,
            "GRANT EXECUTE ON FUNCTION settings.report_state"
            "(text, bigint, text[], text[], boolean, text) TO {role}",
            logical,
        )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
