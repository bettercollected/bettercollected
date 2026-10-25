- **The backend refuses to start while Mongo holds data of a Postgres-only group that was never
  imported** (`refdata`, `analytics`, `ai`, `actions`): the API, the job worker and
  `python -m backend.scim` check every collection of those groups, and a collection with documents
  in Mongo, no row in Postgres and no finished backfill stops the start, naming the group, the
  collection, its count and the command (`python -m backend.migrate --group <g> backfill`). The
  check is an existence probe per table; Mongo is asked only about empty, never imported tables, and
  not at all without `MONGO_URI`. A `MONGO_URI` that is set but cannot be read refuses the start too.
  `python -m backend.seed_refdata` runs the same check before seeding. Override, for data known to be
  worthless: `DB_DISCARD_UNIMPORTED_MONGO_DATA=all` (or a list of groups), logged as a warning on
  every start. See "Upgrading to 4.1" in `docs/postgres-cutover-runbook.md`.
