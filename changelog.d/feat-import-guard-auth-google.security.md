- **Auth and the Google Forms integration refuse to start while Mongo holds data that was never
  imported into Postgres.** The backend already did; an upgraded stack whose import had not finished
  would have started auth on an empty or partial `auth.users` and created new accounts for emails
  that already have one, and the Google integration on empty credential and form tables. Each
  service now checks its own collections at startup, after the schema check: a collection with
  documents in Mongo, no row in Postgres and no finished backfill stops the start, naming the
  collection, its count and the command (`python -m auth.migrate --group auth backfill`,
  `python -m googleform.migrate --group google backfill`), never a value. Mongo is not contacted
  without `MONGO_URI`; a `MONGO_URI` that is set but cannot be read refuses the start. The shared
  escape `DB_DISCARD_UNIMPORTED_MONGO_DATA` (`all`, or the service's group) starts anyway, logged as a
  warning on every start. The Google integration's `MONGO_URI` is now also read from the settings
  store, as the other services'. See "Upgrading to 4.1" in `docs/postgres-cutover-runbook.md`.
