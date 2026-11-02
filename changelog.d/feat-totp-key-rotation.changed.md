- The `authkeys.*` tasks that rotate `AUTH_AES_HEX_KEY` also cover the secrets of authenticator
  apps (second-factor setup): `reencrypt` moves them to the new key, `verify` and `drop_old`
  count them, and the task runner's data role gets read and write access to their `doc` and
  checksum only. Merge this before turning `TOTP_ENABLED` on.
