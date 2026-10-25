"""the portal's role deletes a heartbeat only when the whole service is stale

Revision ID: 0019_service_state_delete_guard
Revises: 0018_report_write_stores
Create Date: 2026-10-25

``settings.service_state`` holds what each service instance reports about itself
(revision applied, rejected keys, keyset fingerprint, write stores). The portal's
role needs DELETE on it for one thing, the retention loop, and a table grant
cannot say "only old rows". Without a guard a stolen portal credential could
delete live heartbeats: a service would then look as if it never reported, and
the checks that read the reports (the keyset gates, the integrity monitor) would
see nothing to refuse.

A ``BEFORE DELETE`` trigger now refuses the delete of any row that is not exactly
what the retention loop removes: older than 7 days AND of a service that has no
newer row. It does not apply to the table's owner (``settings.report_state``
runs as its owner and prunes the stale rows of the reporting service itself) or
to a superuser (host commands). A role that can drop or disable the trigger is
the owner anyway; the guard narrows the portal's credential, not the owner's.
The threshold is the retention loop's (``SERVICE_STATE_DAYS``) and
``report_state``'s: a row younger than that is never removed by anyone but the
owner.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0019_service_state_delete_guard"
down_revision: Union[str, None] = "0018_report_write_stores"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION settings.service_state_delete_guard() RETURNS trigger
        LANGUAGE plpgsql SET search_path = pg_catalog AS $$
        BEGIN
            IF (SELECT r.rolsuper FROM pg_roles r WHERE r.rolname = current_user)
               OR current_user::text = (SELECT pg_get_userbyid(c.relowner)::text
                                        FROM pg_class c WHERE c.oid = TG_RELID) THEN
                RETURN OLD;
            END IF;
            IF OLD.reported_at < now() - interval '7 days'
               AND NOT EXISTS (SELECT 1 FROM settings.service_state f
                               WHERE f.service = OLD.service
                                 AND f.reported_at >= now() - interval '7 days') THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'settings.service_state: only the stale rows of a service that stopped reporting can be deleted'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER service_state_delete_guard BEFORE DELETE ON settings.service_state "
        "FOR EACH ROW EXECUTE FUNCTION settings.service_state_delete_guard()"
    )


def downgrade() -> None:
    raise NotImplementedError("migrations are expand-only; restore from a backup")
