- `python -m <service>.migrate [--group g] resolve-outbox [--apply]`: after a group rolls back
  from `postgres_primary_dual` to `dual`, it resolves the Postgres-side outbox entries whose
  write Mongo provably holds (the same checksum for every row the entry names and every row of
  the group, in both stores), so `reconcile` and `verify` can get clean again. Rows where Mongo
  only has a later-stamped, different version (`superseded`) are kept unless the operator adds
  `--accept-superseded` after confirming Mongo's version should win. A dry run by default, it
  prints counts only; `--ids-file` writes ids to a new local file. The runbook's "stuck case"
  uses it instead of manual SQL.
  Entries left by the repositories of groups served from Postgres only count apart
  (`postgres_only_leftover`) and are cleared only with `--clear-postgres-only-leftovers`.
