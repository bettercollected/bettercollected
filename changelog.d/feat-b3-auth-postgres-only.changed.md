- The auth service keeps accounts in Postgres only and no longer connects to MongoDB; it needs
  `DATABASE_URL` and refuses to start without it. A `DB_READ_SOURCE`, `DB_WRITE_MODE`,
  `DB_READ_SOURCE__auth` or `DB_WRITE_MODE__auth` setting other than `postgres` now stops it from
  starting and names the setting: remove it. `MONGO_URI` and `MONGO_DB` are read only by the
  import from 4.0 (`python -m auth.migrate`).
