- Action runs on the job queue no longer put the response in it. The queued job holds
  ids only (action, form, response, workspace) and a run token; the executor asks the
  backend for the run's data when it runs, and the backend answers 410, so the run is
  skipped, when the response was deleted, the action was switched off or removed, or
  the run is more than a day old. Until now the whole response, the responder's address
  and the action's stored secrets were written to the queue's table and kept there.
  `python -m backend.jobs.schema`, which `deploy.sh` runs, now also removes that data
  from rows queued by earlier releases, in any status: finished ones are deleted,
  waiting ones are rewritten to ids only. Finished action jobs are deleted after a week
  (a month for failed ones).
- The route that serves a run's data needs the job key, the run's own token (signed by
  the backend, expiring after a day) and the run's job in the queue, `doing`, with the
  same ids and token. The shared job key alone no longer reads any response, and a token
  read from the queue opens nothing once its run is over. The route returns only that
  action's settings, not those of the form's other actions.
- The actions executor's database role is narrowed, with these limits still open (see
  below). It sees and writes only `run_action` jobs of the `actions` queue, with locks
  that start with `action_`, so it can no longer read, queue or cancel the other queues'
  jobs, or take the lock name of a response or account deletion. It cannot write the
  events or periodic-defers tables. A row-level policy, applied by `python -m
  backend.jobs.schema`, does this, and the executor refuses to start without it.
- Job arguments no longer reach the logs: the call string procrastinate prints at start,
  at the end and when a job fails for good is cut to the task name and the job id.
  A failed action run is raised with the action and form ids and the kind of error only,
  and the job's result is a single word instead of the action's log.
- This narrows what a compromised executor can reach. It does not make form actions safe
  to enable. The executor still runs creator code in a restricted `exec` that is not a
  boundary, and it holds the job key and the stack's AES key. Together those two let code
  in it forge the header that deletes an account, so the executor must never hold both:
  taking one of them out is part of the executor isolation work. Keep form actions off
  until that is done.
