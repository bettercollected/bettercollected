- `deploy.sh` no longer stores the stack's own local MongoDB address in the settings
  store when the operator set a `MONGO_URI` of their own in `.env` or `.env.deployment`
  (an external MongoDB): the operator's value is kept, and a `MONGO_URI` that only the
  root `.env` holds is pointed out instead of being replaced.
