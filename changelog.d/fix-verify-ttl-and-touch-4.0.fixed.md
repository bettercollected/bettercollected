- **Migration `verify` agrees with `reconcile`.** In collections Mongo expires by a TTL index
  (sessions, rate-limit counters, SSO states, …), `verify` now treats an expired copy in either
  store as absent, as `reconcile` already did, so copies Mongo's TTL monitor dropped are no longer
  reported as `missing_in_mongo` on every run; the report counts them under `expired`. Only a date
  expires, as in Mongo: an ISO-string expiry is a live copy. And `reconcile` (Mongo → Postgres) no
  longer skips a Postgres row the application wrote after Mongo's copy without a trace: it keeps
  it and counts it as `newer_in_postgres`. The new `reconcile --mongo-wins` copies Mongo's version
  over such rows instead, only in the groups whose `DB_WRITE_MODE`/`DB_WRITE_MODE__<group>` is
  explicitly `mongo` or `dual`. While the Postgres-side outbox has unresolved entries (writes from
  a time Postgres was primary), no row the application wrote is replaced at all; a `mongo->postgres`
  run no longer resolves those entries (`postgres->mongo` or a clean full `verify` does).
