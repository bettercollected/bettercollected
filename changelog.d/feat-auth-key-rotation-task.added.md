- The admin portal can rotate the auth keys without losing data: the tasks `authkeys.add_key`,
  `authkeys.promote`, `authkeys.reencrypt`, `authkeys.verify` and `authkeys.drop_old` (each
  mutating step after a dry run) replace `AUTH_JWT_SECRET` or `AUTH_AES_HEX_KEY`, move every
  stored secret to the new encryption key and drop the old key only when nothing still needs it,
  with counts and ids only in results, events and the audit trail. Signing the session tokens
  with a new secret signs nobody out until the old secret is dropped, and the dry run counts
  who that would affect. The new host command `settings-grant-runner` lets the task runner read
  keys stored before this release. See `docs/auth-key-rotation.md`.
