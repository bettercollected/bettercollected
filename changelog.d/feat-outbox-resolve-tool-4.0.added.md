- `python -m <service>.migrate [--group g] resolve-outbox [--apply]`: after a group rolls back
  from `postgres_primary_dual` to `dual`, it resolves the Postgres-side outbox entries whose
  write Mongo holds (the same or a newer version of every row the entry names and of every
  application-written row of the group), so `reconcile` and `verify` can get clean again. A dry
  run by default, it prints counts only; `--ids-file` writes ids to a new local file. The
  runbook's "stuck case" uses it instead of manual SQL.
