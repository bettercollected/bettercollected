- The admin portal's Health page shows the background job queue: jobs waiting, scheduled for later,
  running and failed, and how long the longest-waiting job has waited, as counts only. The line turns
  amber when a job has waited more than 15 minutes or any job has failed. It needs the roles script
  (`postgres/ensure-admin-roles.sh`, run by `deploy.sh`) to have run once after the upgrade; until then
  the page says it is not available.
