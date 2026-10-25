- Background jobs run on the Postgres job queue by default (`JOBS_BACKEND` is now `postgres`): account
  deletion, scheduled response deletion, action runs, form imports, and the credential purge and Google
  grant revocation that exist on the queue only. The actions executor follows the same default. Set
  `JOBS_BACKEND=temporal` (or `JOBS_BACKEND__<job>=temporal`) to keep a job kind on the Temporal workflows,
  which are still needed for jobs queued there before the switch.
- The admin tasks and the break-glass scripts (`responses.check_undecryptable`, `responses.backfill_workspaces`,
  `google.purge_unencrypted_credentials`, the `keyset.*` tasks, `scripts/rotate_response_keyset.py`,
  `scripts/check_undecryptable_values.py`, `scripts/backfill_response_workspaces.py`) cover Postgres alone and
  never connect to Mongo. `stores: postgres` is the default (`auto` means the same); `mongo` and `both`
  are refused with `store_retired`. No write mode is read any more. `keyset.drop_old` and
  `rotate_response_keyset.py drop-old` need the signed `mongo_retired` statement (`--mongo-retired`)
  and refuse with `store_retired` without it. `google.purge_unencrypted_credentials` refuses an apply
  while the runner still has a `MONGO_URI` configured, since the import from 4.0 would copy the rows
  held there back; the task runner no longer reads `MONGO_URI`, `MONGO_DB` or `GOOGLE_MONGO_DB`.
- `python -m backend.scim` and `python -m scripts.seed_flow_templates` connect no Mongo; the Google Forms
  integration keeps its credentials as plain records and no longer sets up Beanie at startup.
