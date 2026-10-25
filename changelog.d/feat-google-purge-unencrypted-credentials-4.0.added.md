- Admin portal: a task, `google.purge_unencrypted_credentials`, replaces the manual runbook step
  "Google credentials without a user id". It deletes the stored Google credentials that have no user
  id or hold readable tokens, with exactly the runbook's filters: a dry run first (counts per store),
  then the apply with the usual confirmation code, Mongo first and then Postgres, with the counts in
  the audit log. Counts only, never ids, emails or tokens; a second run deletes nothing. An apply
  must cover every store the services still write (`stores_incomplete` otherwise). The task
  runner's Google data role still has no DELETE: it calls a narrow definer function,
  `google.purge_unencrypted_credentials`, owned by a new login-less role `bc_tasks_purge_google`.
  Both are created by `postgres/ensure-admin-roles.sh`: run it once after upgrading (`deploy.sh`
  does; without `deploy.sh`, as described for 4.0.8). Until then the task refuses with
  `purge_function_missing`. Mongo: the runner's Mongo user needs `readWrite` on
  `Oauth2CredentialDocument`.
