- Owners choose how long the workspace's activity log keeps its entries: 6, 12, 24 or 60 months
  (12 by default, never less than 6). The Activity page states the workspace's period and lets an
  owner change it; the change is itself recorded in the log, and a shorter period applies at the
  next daily clean-up. The clean-up job is now called `audit_log_purge` (it was `sso_audit_purge`;
  a job still queued under the old name runs as before) and applies each workspace's own period.
