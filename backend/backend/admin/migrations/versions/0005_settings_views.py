"""settings store: per-service views, reader roles and ``report_state``

Revision ID: 0005_settings_views
Revises: 0004_settings_tables
Create Date: 2026-10-18

A reading service never touches a base table. It gets SELECT on two
security-barrier views of its own, and EXECUTE on ``settings.report_state``:

* ``settings.v_<service>``: the signed rows whose ``readers`` include the
  service (cleared settings are not shown);
* ``settings.v_<service>_manifest``: the whole signed manifest (revision,
  ``key -> [version, row signature, readers]`` for every row, signature). It
  is deliberately not filtered: the loader checks the signed ``readers`` of
  each entry to know which keys its service must receive, so a row withheld
  from it shows up as a missing key.

``settings.reader_roles`` maps a database role to its service (the names come
from ``migration_support.READER_SERVICES``); ``report_state`` trusts
``session_user`` (the login role; ``current_user`` is the definer inside a
SECURITY DEFINER function) and can write only that service's own rows.
"""

from typing import Sequence, Union

from alembic import op

from backend.admin.migration_support import READER_SERVICES, grant, role_name

revision: str = "0005_settings_views"
down_revision: Union[str, None] = "0004_settings_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAME = r"^[A-Z][A-Z0-9_]{0,63}$"


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE settings.reader_roles (
            role text NOT NULL,
            service text NOT NULL,
            CONSTRAINT pk_reader_roles PRIMARY KEY (role),
            CONSTRAINT uq_reader_roles_service UNIQUE (service),
            CONSTRAINT ck_reader_roles_service CHECK (service ~ '^[a-z][a-z0-9_]{0,31}$')
        )
        """
    )
    for service, logical in READER_SERVICES.items():
        role = role_name(logical)
        op.execute(
            f"INSERT INTO settings.reader_roles (role, service) VALUES ('{role}', '{service}')"
        )
        op.execute(
            f"""
            CREATE VIEW settings.v_{service} WITH (security_barrier = true) AS
            SELECT key, section, readers, is_secret, reload_class, value, blob,
                   version, updated_at, sig
            FROM settings.entries
            WHERE NOT cleared AND readers @> ARRAY['{service}']::text[]
            """
        )
        op.execute(
            f"""
            CREATE VIEW settings.v_{service}_manifest WITH (security_barrier = true) AS
            SELECT revision, entries, sig
            FROM settings.manifest
            """
        )

    op.execute(
        rf"""
        CREATE FUNCTION settings.report_state(
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
        grant(op, "GRANT USAGE ON SCHEMA settings TO {role}", logical)
        grant(
            op,
            f"GRANT SELECT ON settings.v_{service}, settings.v_{service}_manifest TO {{role}}",
            logical,
        )
        grant(
            op,
            "GRANT EXECUTE ON FUNCTION settings.report_state"
            "(text, bigint, text[], text[], boolean, text) TO {role}",
            logical,
        )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
