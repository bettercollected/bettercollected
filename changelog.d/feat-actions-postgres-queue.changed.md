- Action runs are retried up to three times in total, five and then twenty-five seconds
  apart, and stopped after ninety seconds. A run that is already queued is not queued
  twice, and a run that cannot be queued no longer fails the submission or keeps the
  form's other actions from running (it is logged with ids). `deploy.sh` now also
  creates or repairs the executor's database role (`postgres/ensure-jobs-exec-role.sh`),
  so a database that predates it gets it.
