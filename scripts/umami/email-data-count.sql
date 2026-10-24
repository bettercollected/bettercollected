-- Read-only: how many Umami event-data (and session-data) rows carry an `email`
-- property, from before the web app stopped sending the signed-in user's email
-- as an analytics property. Counts and dates only, never a value.
--
-- Run against the Umami database (its own Postgres), for example:
--   docker exec -i <umami-postgres container> psql -U umami -d umami -X -q < scripts/umami/email-data-count.sql
-- It opens a read-only transaction and changes nothing. Then see
-- email-data-purge.sql.

\set ON_ERROR_STOP on
BEGIN READ ONLY;

\echo 'event_data rows with an email property, per website:'
SELECT website_id,
       count(*) AS rows,
       count(DISTINCT website_event_id) AS events,
       min(created_at)::date AS oldest,
       max(created_at)::date AS newest
FROM event_data
WHERE lower(data_key) = 'email'
GROUP BY website_id
ORDER BY website_id;

\echo 'event_data rows with an email property, total:'
SELECT count(*) AS rows FROM event_data WHERE lower(data_key) = 'email';

\echo 'session_data rows with an email property (only if sessions were identified by email):'
SELECT count(*) AS rows FROM session_data WHERE lower(data_key) = 'email';

\echo 'oldest event kept (Umami keeps events until they are deleted):'
SELECT min(created_at)::date AS oldest_event, count(*) AS events FROM website_event;

ROLLBACK;
