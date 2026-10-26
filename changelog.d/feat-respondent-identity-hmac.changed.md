- **Upgrade note:** the backend refuses to start without `RESPONDENT_IDENTITY_KEY`, a new secret of at
  least 32 random bytes (`openssl rand -hex 32`; hex or base64). A new compose stack gets one from
  `bootstrap-keys`; a stack that upgrades sets it once and keeps it, because a different key makes every
  stored anonymous identity unmatchable. See `docs/respondent-identity.md`.
