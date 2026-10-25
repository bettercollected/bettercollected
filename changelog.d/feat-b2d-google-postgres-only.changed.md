- The backend and the admin task runner treat the Google Forms integration's data as Postgres only,
  as the integration itself does. In `GOOGLE_FORMS_IMPORT=off` the credential purge of a deleted
  account runs in the database whatever `DB_WRITE_MODE` says. The keyset tasks and
  `scripts/rotate_response_keyset.py` take Postgres as the store the integration writes and no
  longer read `DB_WRITE_MODE__GOOGLE`; the task runner's compose entry for it is gone, and
  `keyset.drop_old` with `mongo_retired` needs only `DB_WRITE_MODE` and
  `DB_WRITE_MODE__RESPONSES` on `postgres`.
