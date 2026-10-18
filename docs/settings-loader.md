# Reading the settings store (the loader)

Backend, auth and the Google integration read settings through
`common.settings.loader` (`SETTINGS_STORE=off|auto|required`, default `auto`: on
only when `DATABASE_URL` and `SETTINGS_MASTER_KEY` are both set). Order: a
non-empty environment value, then the verified store row, then the default.

- Production should run with `SETTINGS_STORE=required`: a stored secret that is
  rejected or cannot be opened is otherwise refused (logged once by key name) and
  the field keeps its code default, which is empty for a secret. In `auto` mode
  start-up logs one warning listing the secret and T3 keys that have neither an
  environment value nor a verified store row.
- `SETTINGS_SNAPSHOT_DIR` holds the signed snapshot used when the database is
  down and remembers the highest revision seen (the rollback floor). The
  deployment compose file mounts a named volume at `/var/lib/bc-settings` for
  each of backend, auth and integrations-googleform; mount a volume or tmpfs
  there too if you make the containers read-only. The directory is closed to mode
  700 and the file is mode 600. Secret values in it are sealed, non-secret values
  are plain JSON. After restoring the database from a backup, remove it.
- Hot (class H) keys are read through `live().ai.X` / `live().api.X` at every
  call. `common.settings.loader.proven.LIVE_PROVEN` lists the keys whose consumers
  are proven to do so (tests in `backend/tests/app/services/test_live_settings_reads.py`
  run each against the settings object and against the loader's snapshot); a
  changed H key outside it reports `restart_pending`.

The list of settings, with their reload classes, is generated: see `docs/settings-inventory.md`.
