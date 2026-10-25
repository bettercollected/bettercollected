- The backend keeps its identity data in Postgres only: workspaces, members, invitations, API keys,
  email domains, single sign-on connections, SCIM directory sync, sessions and user tags. A
  `DB_READ_SOURCE__identity` or `DB_WRITE_MODE__identity` setting other than `postgres` now stops
  the backend from starting and names the setting: remove it. The backend no longer creates the
  Mongo index on `workspace_users`, and `python -m backend.membership_duplicates` checks Postgres
  only (`python -m backend.migrate preflight` reports duplicates in a 4.0 database).
