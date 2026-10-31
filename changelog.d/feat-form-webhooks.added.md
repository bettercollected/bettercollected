- Self-service webhooks per form (off by default, `WEBHOOKS_ENABLED`). Owners and admins send the answers of chosen
  questions to an https address of their own, signed with a per-webhook secret that is shown once, with retries and
  a "Deliveries" log (ids, status and timings only, kept 30 days). The respondent's privacy panel names the
  destination host. Addresses are checked when saved and again at every call.
  Upgrade note: the jobs worker now serves the `default` and `webhooks` queues; if you set `JOBS_QUEUES`,
  include `webhooks`.
