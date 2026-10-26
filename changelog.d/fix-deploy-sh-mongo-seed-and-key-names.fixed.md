- `deploy.sh` no longer stores the stack's own local MongoDB address in the settings
  store when the operator set a `MONGO_URI` of their own in `.env` or `.env.deployment`
  (an external MongoDB). A `MONGO_URI` that only the root `.env` holds, which no
  service reads, now stops the upgrade before any service is stopped, with the line to
  move to `.env.deployment`.
