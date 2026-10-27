- The compose file no longer sets `DB_READ_SOURCE` or `DB_WRITE_MODE` on the backend, the jobs
  worker or the task runner: Postgres is the only store, and the task runner reads no write mode.
  A line for either (or a `__<group>` override) left in `.env.deployment` now reaches the
  services, which refuse any value but `postgres`; `./deploy.sh` refuses such a line before it
  starts or changes any container or data, naming the setting and never its value. Remove the line
  or set it to `postgres`.
