- `deploy.sh` now gives a compose stack that upgrades from 4.0 its respondent identity key. The 4.1
  backend refuses to start without `RESPONDENT_IDENTITY_KEY`, and `bootstrap-keys` only runs on a new
  stack, so `deploy.sh` generates it once before any service starts, into the settings store and into
  `.env` (like the other keys of an upgrade, so `SETTINGS_STORE=off` still has it). It never overwrites a
  key, uses one set in the shell, `.env` or `.env.deployment` as it is, never prints it, and refuses to
  make a new one for a database that was already used with a key and has none configured. After the new backend is up it runs
  the one-time conversion of the stored identities (`python -m backend.identity_rekey`) and prints the
  key's 8-digit fingerprint (write it down with the key backup); a missing or wrong key fails the deploy.
