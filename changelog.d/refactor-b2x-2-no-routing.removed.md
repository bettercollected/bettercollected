- The code that ran 4.0 on two stores is gone. The services have no routing between Mongo and
  Postgres, no mirror writes, no shadow reads and no Mongo connection of their own, and Beanie is
  no longer a dependency of the images (it remains a test-only dependency of the import's
  tests). `DB_SHADOW_READ_SAMPLE` and `DB_MIRROR_TIMEOUT_MS` are read by nothing now;
  `DB_READ_SOURCE` and `DB_WRITE_MODE` (and their `__<group>` overrides) are read only to refuse a
  value other than `postgres`, as before. `GET /persistence/status` (admin) no longer reports
  routing counters or an outbox backlog: it shows the jobs backends in effect, whether Postgres
  answers, and that Mongo is not used. The import from 4.0 (`python -m backend.migrate`,
  `auth.migrate`, `googleform.migrate`: backfill, verify, reconcile, status, resolve-outbox,
  jobs-sweep) and the startup check for unimported Mongo data are unchanged.
