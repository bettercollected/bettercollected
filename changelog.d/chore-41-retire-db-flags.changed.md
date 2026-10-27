- `python -m backend.migrate jobs-sweep` (and the same command of `auth.migrate` and
  `googleform.migrate`) no longer needs a `MONGO_URI`: the migration tooling opens MongoDB only
  for the commands that read it (`preflight`, `backfill`, `verify`, `reconcile`, `status`,
  `resolve-outbox`), and those say so and exit 2 when none is set. `deploy.sh` no longer gives the
  sweep it runs after the 4.1 roll a placeholder `MONGO_URI`.
