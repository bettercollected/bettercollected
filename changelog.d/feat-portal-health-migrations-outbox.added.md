- The admin portal's Health page now shows the `app`, `auth` and `google` schemas'
  migration state against the head the deployed code expects, next to `admin`, and a
  "Mirror outbox" table with the unresolved and total mirror-write failures of each
  service in PostgreSQL (red while any is unresolved). Both are read through narrow
  definer functions created by `postgres/ensure-admin-roles.sh`; run it once after
  upgrading (`deploy.sh` does). MongoDB outboxes are not shown.
