"""purge_user_credentials: erase one user's stored Google credentials

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25

Account deletion must erase the user's stored Google credentials even when the
Google Forms service is switched off (GOOGLE_FORMS_IMPORT=off) and never called.
The backend's role has no privileges on this schema, and gets none: it may only
execute ``google.purge_user_credentials(user_id, email)``, a SECURITY DEFINER
function owned by this schema's owner (bc_google) that

* deletes only the rows matching BOTH the user id and the email (never one of
  the two alone, never another user's rows),
* records a deletion tombstone per deleted row (as every delete here does,
  common/db/tombstones.py), and
* returns the number of rows deleted, nothing else.

Its search_path is pinned (pg_catalog, pg_temp; every table is schema
qualified), EXECUTE is revoked from PUBLIC and granted only to the owner of
schema ``app`` (the backend's role, bc_app), when that schema exists, together
with USAGE on this schema (needed to call a function in it; it grants no access
to any table). A new function only, so expand-only; the downgrade drops it and
revokes that USAGE.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FUNCTION = "google.purge_user_credentials(text, text)"
# the Mongo collection name the credentials table mirrors
# (googleform/db/models.py OAuthCredentialRow.__mongo_collection__): the
# tombstone's ``collection``
COLLECTION = "Oauth2CredentialDocument"


def upgrade() -> None:
    op.execute(
        f"""
CREATE FUNCTION google.purge_user_credentials(p_user_id text, p_email text)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $fn$
DECLARE
    deleted integer;
BEGIN
    IF coalesce(p_user_id, '') = '' OR coalesce(p_email, '') = '' THEN
        RETURN 0;
    END IF;
    WITH gone AS (
        DELETE FROM google.oauth_credentials c
         WHERE c.user_id = p_user_id AND c.email = p_email
        RETURNING c.id
    ), stones AS (
        INSERT INTO google.deletion_tombstones AS t (collection, row_id, deleted_at)
        SELECT '{COLLECTION}', gone.id, date_trunc('milliseconds', clock_timestamp())
          FROM gone
        ON CONFLICT (collection, row_id) DO UPDATE SET deleted_at = excluded.deleted_at
        RETURNING 1
    )
    SELECT count(*) INTO deleted FROM gone;
    RETURN deleted;
END
$fn$;
"""
    )
    op.execute(
        f"""
DO $own$
DECLARE
    schema_owner name;
    app_owner name;
BEGIN
    SELECT nspowner::regrole::name INTO schema_owner
      FROM pg_namespace WHERE nspname = 'google';
    EXECUTE format('ALTER FUNCTION {FUNCTION} OWNER TO %I', schema_owner);
    EXECUTE 'REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC';
    SELECT nspowner::regrole::name INTO app_owner
      FROM pg_namespace WHERE nspname = 'app';
    IF app_owner IS NOT NULL AND app_owner <> schema_owner THEN
        -- USAGE is needed to call a function in the schema; it grants no
        -- access to any table here
        EXECUTE format('GRANT USAGE ON SCHEMA google TO %I', app_owner);
        EXECUTE format('GRANT EXECUTE ON FUNCTION {FUNCTION} TO %I', app_owner);
    END IF;
END
$own$;
"""
    )


def downgrade() -> None:
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}")
    op.execute(
        """
DO $own$
DECLARE
    schema_owner name;
    app_owner name;
BEGIN
    SELECT nspowner::regrole::name INTO schema_owner
      FROM pg_namespace WHERE nspname = 'google';
    SELECT nspowner::regrole::name INTO app_owner
      FROM pg_namespace WHERE nspname = 'app';
    IF app_owner IS NOT NULL AND app_owner <> schema_owner THEN
        EXECUTE format('REVOKE USAGE ON SCHEMA google FROM %I', app_owner);
    END IF;
END
$own$;
"""
    )
