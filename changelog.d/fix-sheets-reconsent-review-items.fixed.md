- Google Sheets action (`GOOGLE_SHEETS_OAUTH=backend`): saving an action that still holds a grant from
  before `drive.file` is refused with 409 `sheets_reconsent_required` instead of refreshing and using
  that grant. The reconnect mail to the billing owner is sent in the background, so submissions no
  longer wait for the auth service; a 422 from auth is final (marked and logged once, never retried),
  transient failures are retried, and long form and workspace titles are cut to auth's limits. The auth
  service no longer builds a reconnect link for the `.` and `..` workspace handles.
