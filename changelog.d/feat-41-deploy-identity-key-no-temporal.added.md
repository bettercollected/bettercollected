- `deploy.sh` now gives a compose stack that upgrades from 4.0 its respondent identity key. The 4.1
  backend refuses to start without `RESPONDENT_IDENTITY_KEY`, and `bootstrap-keys` only runs on a new
  stack, so `deploy.sh` generates it once before any service starts, into the settings store and into
  `.env` (like the other keys of an upgrade, so `SETTINGS_STORE=off` still has it). It never overwrites a
  key, uses one set in the shell or `.env` as it is (one only in `.env.deployment` is copied into `.env`,
  because compose does not pass it to the backend from there), never prints it, and stops before any
  service starts when the database was already used with a key and none is configured, when `.env` and
  the store hold keys that cannot be shown to be the same (`BC_IDENTITY_KEY_SOURCE=env` says the `.env` one
  is intended), or when `SETTINGS_STORE=off` and the key is only in the store. After the new backend is up it runs
  the one-time conversion of the stored identities (`python -m backend.identity_rekey`) and prints the
  key's 8-digit fingerprint (write it down with the key backup); a missing or wrong key fails the deploy.
