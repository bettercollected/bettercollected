-- Delete the `email` property from Umami's event data (and, with
-- include_sessions, its session data): the signed-in user's email address that
-- the web app used to send as an analytics property. Only those rows go; the
-- events themselves (page views, event names) stay. Counts only, never a value.
--
-- A DRY RUN unless `apply` is set: the deletion runs inside a transaction that
-- is rolled back, so it reports what it would delete and changes nothing.
--
--   docker exec -i <umami-postgres container> psql -U umami -d umami -X -q < scripts/umami/email-data-purge.sql
--   docker exec -i <umami-postgres container> psql -U umami -d umami -X -q -v apply=1 < scripts/umami/email-data-purge.sql
--   ... -v apply=1 -v include_sessions=1 ...   (also session_data rows keyed `email`)
--
-- Take a backup of the Umami database first. Run email-data-count.sql
-- afterwards: it should report 0.

\set ON_ERROR_STOP on
\if :{?apply}
\else
\set apply 0
\endif
\if :{?include_sessions}
\else
\set include_sessions 0
\endif

BEGIN;

\echo 'event_data rows deleted:'
WITH deleted AS (
    DELETE FROM event_data WHERE lower(data_key) = 'email' RETURNING 1
)
SELECT count(*) AS rows FROM deleted;

\if :include_sessions
\echo 'session_data rows deleted:'
WITH deleted AS (
    DELETE FROM session_data WHERE lower(data_key) = 'email' RETURNING 1
)
SELECT count(*) AS rows FROM deleted;
\endif

\if :apply
COMMIT;
\echo 'Applied.'
\else
ROLLBACK;
\echo 'Dry run: nothing was deleted. Run again with -v apply=1 to delete.'
\endif
