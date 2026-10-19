"""notification outbox transitions, and bounds on what a service reports about itself

Revision ID: 0016_outbox_and_state_guards
Revises: 0015_runner_audit_functions
Create Date: 2026-10-19

* ``admin.notifications``: the portal's role holds UPDATE on the delivery columns
  (it runs the sender). A trigger now allows only what the sender does: a
  ``pending`` row may count an attempt (one at a time), record recipients (only
  ever adding), move its next attempt at most a day ahead, and become ``sent``
  (once, with a ``sent_at``, an attempt spent and at least one recipient) or
  ``failed``. A ``sent`` or ``failed`` row is final, and the content columns never
  change, so a credential cannot reset sent notices to replay them or edit them.
  What it cannot tell is a real send from a ``pending -> sent`` UPDATE made by the
  same role: that remains possible for whoever holds the portal's credential.
* ``settings.report_state`` keeps its contract and adds bounds: smaller name lists,
  the reported revision kept as reported (the integrity loop compares it with the
  stored revision to notice a rolled-back database), and rejected names only when they are stored
  settings the caller's service reads. Reports remain self-asserted readiness
  information; the keyset gates cross-check them with their own limits (see
  ``docs/admin-service.md``).
"""

from typing import Sequence, Union

from alembic import op

from backend.admin.migration_support import READER_SERVICES, grant

revision: str = "0016_outbox_and_state_guards"
down_revision: Union[str, None] = "0015_runner_audit_functions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAME = r"^[A-Z][A-Z0-9_]{0,63}$"


def upgrade() -> None:
    op.execute(
        r"""
        CREATE FUNCTION admin.notifications_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            IF OLD.status <> 'pending' THEN
                RAISE EXCEPTION 'admin.notifications: a sent or failed notification is final'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF (NEW.id, NEW.created_at, NEW.kind, NEW.payload, NEW.audit_seq, NEW.dedupe_key)
               IS DISTINCT FROM
               (OLD.id, OLD.created_at, OLD.kind, OLD.payload, OLD.audit_seq, OLD.dedupe_key) THEN
                RAISE EXCEPTION 'admin.notifications: the content of a notification never changes'
                    USING ERRCODE = 'insufficient_privilege';
            END IF;
            IF NEW.attempts < OLD.attempts OR NEW.attempts > OLD.attempts + 1
               OR NOT (OLD.delivered_to <@ NEW.delivered_to)
               OR NEW.next_attempt_at > clock_timestamp() + interval '1 day' THEN
                RAISE EXCEPTION 'admin.notifications: not a delivery step'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            IF NEW.status = 'sent' THEN
                IF NEW.sent_at IS NULL OR NEW.attempts <> OLD.attempts + 1
                   OR cardinality(NEW.delivered_to) < 1
                   OR abs(extract(epoch FROM (clock_timestamp() - NEW.sent_at))) > 3600 THEN
                    RAISE EXCEPTION 'admin.notifications: a sent notice records its delivery'
                        USING ERRCODE = 'integrity_constraint_violation';
                END IF;
            ELSIF NEW.sent_at IS NOT NULL THEN
                RAISE EXCEPTION 'admin.notifications: sent_at belongs to a sent notice'
                    USING ERRCODE = 'integrity_constraint_violation';
            END IF;
            RETURN NEW;
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER notifications_guard BEFORE UPDATE ON admin.notifications "
        "FOR EACH ROW EXECUTE FUNCTION admin.notifications_guard()"
    )

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
            -- a rejection is about a stored setting the caller's service reads (the
            -- reported revision is kept as reported: the integrity loop compares it
            -- with the stored one to notice a restored or replaced database)
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
                 rejected_keys, restart_pending, keyset_fp)
            VALUES (svc, p_instance, now(), p_revision_applied,
                    env_names, rejected, coalesce(p_restart_pending, false), coalesce(p_keyset_fp, ''))
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
    for logical in READER_SERVICES.values():
        grant(
            op,
            "GRANT EXECUTE ON FUNCTION settings.report_state"
            "(text, bigint, text[], text[], boolean, text) TO {role}",
            logical,
        )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
