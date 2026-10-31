- Action runs on the job queue no longer put the response in it. The queued job holds
  ids only (action, form, response, workspace); the executor asks the backend for the
  run's data when it runs, and the backend answers 410, so the run is skipped, when the
  response was deleted or the action was switched off or removed in the meantime. Until
  now the whole response, the responder's address and the action's stored secrets were
  written to the queue's table and kept there. Finished action jobs are now deleted
  after a week (a month for failed ones), including those queued by earlier releases.
- The actions executor's database role sees and changes only the `actions` queue. A
  row-level policy on the queue's table, applied by `python -m backend.jobs.schema`
  (which `deploy.sh` runs), keeps it from reading, queueing or cancelling the other
  queues' jobs, such as an account or response deletion. The executor refuses to start
  where that policy is missing.
- A failed action run is logged and raised with the action and form ids and the kind of
  error only, never the error's message, which can carry an answer. The job's result is
  a single word instead of the action's log.
