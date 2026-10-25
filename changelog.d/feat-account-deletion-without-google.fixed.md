- Account deletion no longer fails, or leaves the user's stored Google credentials behind, when the Google
  Forms service is off, unreachable, slow or failing. The account, its sessions and its workspace data are
  erased first. Then the service deletes the stored credentials, and in `GOOGLE_FORMS_IMPORT=on` and
  `readonly` it revokes the grant at Google first. When that fails, or in `off`, a retryable
  `purge_provider_credentials` job is queued (procrastinate, `JOBS_BACKEND__purge_provider_credentials=postgres`;
  hourly for two days, the email encrypted in its arguments). In `off` the job erases the rows through
  `google.purge_user_credentials(user_id, email)` (google revision 0005): a `SECURITY DEFINER` function owned by
  the Google schema's role, which deletes only the rows matching both the user id and the email, records
  tombstones and returns a count. EXECUTE is granted to the backend's role only. Mongo and dual stacks rely on
  the service. A purge that is still pending a day after it was queued, or failed (or a deletion job in that
  state), is shown by the admin portal's integrity monitor and mailed to the admins once
  (`CREDENTIAL_PURGE` / `overdue`, through `admin.credential_purges_overdue()` from
  `postgres/ensure-admin-roles.sh`). If the purge can't be queued at all, the deletion job fails after the
  erasure and is retried: on procrastinate the integrity monitor reports it, on Temporal (the default) it
  shows in the Temporal UI and the backend's error log only. A disabled Google provider is purged too. The
  Google Forms service's erase is now `POST /google/oauth/credentials/erase` with the user id and email in the
  JSON body (the `DELETE /google/oauth/credentials` query-string form is removed), so no URL or access log
  carries the email. The auth service's account delete uses a 30 s timeout
  instead of 20000 s.
