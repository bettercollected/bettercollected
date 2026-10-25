- The compose stack runs without MongoDB. A new install never starts it and stores no
  `MONGO_URI`; the backend and the jobs worker default to Postgres for every group.
  MongoDB starts only under the new `legacy-mongo` compose profile.
- `./deploy.sh` upgrades a 4.0 stack whose data is still in MongoDB by importing it first.
  It stops the services, runs preflight, backfill and verify for auth, the Google
  integration and the backend, and stops before any service starts if a check fails,
  printing the counts. On success it clears `MONGO_URI`, records
  `BC_LEGACY_MONGO_IMPORTED` in `.env`, and stops MongoDB. The Mongo volume is kept.
  Stacks that were already imported skip this step.
