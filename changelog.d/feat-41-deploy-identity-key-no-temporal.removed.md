- Temporal is no longer part of the compose stack: `docker-compose.deployment.yml` has no `temporal`,
  Temporal database (`postgresql`) or Temporal `worker` service, `deploy.sh` no longer starts them,
  generates `BC_TEMPORAL_DB_PASSWORD`, writes the worker's `API_KEY` / `AES_HEX_KEY` copies to `.env` or
  creates `.env.worker`, and `.env.deployment.example` no longer lists the worker's settings. Background
  work runs on the Postgres job queue (`jobs-worker`). On a stack from before 4.1, `deploy.sh` retires
  Temporal after the new release is up: it puts every scheduled response deletion on the job queue
  (`backend.migrate jobs-sweep`), waits up to `BC_TEMPORAL_DRAIN_SECONDS` (default 300) until Temporal runs
  no workflow, then removes the three containers and keeps the `temporal-postgres-data` volume (a rollback
  to 4.0 uses it; remove it with `docker volume rm` once 4.1 has run well). With workflows still running,
  or Temporal unreachable, the deploy stops with the stack on 4.1 and the old containers untouched; run it
  again later, or `BC_TEMPORAL_DRAIN=skip ./deploy.sh` to remove Temporal without waiting. A
  `JOBS_BACKEND` or `JOBS_BACKEND__<job>` set to `temporal` in `.env.deployment` is refused before anything
  changes. A leftover `.env.worker` is no longer read and is kept.
