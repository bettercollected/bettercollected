- Admin task `auth.resolve_case_duplicate_accounts`: a refused run now says why. The runner
  refuses with `backend_unreachable` (connection or timeout only), `backend_route_missing`
  (404), `backend_error` (5xx or another status) or `backend_bad_reply` (not the expected
  JSON), and logs the HTTP status. When the API's call to the auth service fails, the internal
  admin-task routes answer 502 with a stable code instead of passing auth's status through, and
  the run refuses with `auth_unreachable`, `auth_key_refused` (the backend's
  `AUTH_INTERNAL_NOTIFY_KEY` does not match auth's) or `auth_error`. The admin service guide has
  a troubleshooting table for these codes.
