- Background jobs run on the Postgres job queue by default (`JOBS_BACKEND` is now `postgres`): account
  deletion, scheduled response deletion, action runs, form imports, and the credential purge and Google
  grant revocation that exist on the queue only. Set `JOBS_BACKEND=temporal` (or
  `JOBS_BACKEND__<job>=temporal`) to keep a job kind on the Temporal workflows. Upgrading: a stack that
  never set `JOBS_BACKEND` (the deployment compose file does not) switches to the queue at once, so the
  `jobs-worker` service must be running; run `python -m backend.migrate jobs-sweep --backend postgres` at
  the upgrade so that every scheduled response deletion is on the queue, and keep the Temporal worker until
  the Temporal schedules and workflows already in flight have run.
- The actions executor follows the same default: without `JOBS_BACKEND` it consumes the Postgres queue and
  needs `DATABASE_URL` (the jobs role's URL); it now exits at start naming that setting when it is empty,
  instead of failing on the first connection. Before updating its image, set its `DATABASE_URL` or
  `JOBS_BACKEND=temporal`. A response whose deletion cannot be queued is logged and left to
  `jobs-sweep`, no longer a failed submission.
- The admin tasks and the break-glass scripts (`responses.check_undecryptable`, `responses.backfill_workspaces`,
  `google.purge_unencrypted_credentials`, the `keyset.*` tasks, `scripts/rotate_response_keyset.py`,
  `scripts/check_undecryptable_values.py`, `scripts/backfill_response_workspaces.py`) cover Postgres alone and
  never connect to Mongo. `stores: postgres` is the default (`auto` means the same); `mongo` and `both`
  are refused with `store_retired`. No write mode is read any more. `keyset.drop_old` and
  `rotate_response_keyset.py drop-old` need the signed `mongo_retired` statement (`--mongo-retired`)
  and refuse with `store_retired` without it; they also refuse with `import_incomplete` until the import
  from 4.0 is over (no `MONGO_URI` on the runner, no unfinished backfill in `migration_progress`), so a
  later backfill cannot bring in a value on a key that was dropped. `google.purge_unencrypted_credentials`
  applies the same rule: it refuses an apply until the import is over, since running it again would copy
  the rows still held in Mongo back (a role that cannot read `google.migration_progress` leaves the
  decision to the runner's `MONGO_URI`). The task runner connects to Mongo never; it reads `MONGO_URI`
  only to refuse in these cases.
- `python -m backend.scim` and `python -m scripts.seed_flow_templates` connect no Mongo; the Google Forms
  integration keeps its credentials as plain records and no longer sets up Beanie at startup.
