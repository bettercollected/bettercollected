- **`verify` and `reconcile` leave the Postgres-only groups alone**: without `--group` they skip
  `refdata`, `analytics`, `ai` and `actions` and say so; `--group` (or `--collections`) naming one
  exits with code 2 and names it. The verified marker covers the other groups. `reconcile
  --direction postgres->mongo` checks each group's effective write mode (the backend's own flags,
  where a Postgres-only group is always `postgres`) instead of the global `DB_WRITE_MODE`.
