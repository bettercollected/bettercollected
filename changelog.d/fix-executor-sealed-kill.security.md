- **The actions executor can no longer hold the encryption key unnoticed, and an administrator's
  secret goes only where the administrator said.** A secret the instance's administrators stored on an
  action now goes only to the exact address they set (scheme, host, port, path and query), not to any
  address on the same host, and custom code does not see the reply of such a call. New setting
  `ACTION_SECRETS_SEALED_ALLOWED` on the backend (default `true`; set `false` once the executor is 4.3):
  the sealed run context and the key-only credential write-back are then refused with 426 and a log
  line. New setting `ACTION_EXECUTOR_KEY_ALLOWED` on the executor (default `true`; set `false` after
  removing `AES_HEX_KEY`): the executor then refuses to start while the key is set. The key-only
  write-back only replaces the `Credentials` secret, a run context asked with opened secrets answers
  503 when the backend has no key (never an empty or sealed answer), and the run context and the
  run-scoped write-back are sent with `Cache-Control: no-store`.
