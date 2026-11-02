- The backend can run the Google Sheets action itself, in its jobs worker on a new `integrations` queue,
  instead of the actions executor: the same header row, answer row and group tabs, the same permanent
  and retried failures (a missing sheet or withdrawn access ends the run, a Google error is retried after
  5 and 25 seconds), visible in the action log, with the access token refreshed and stored by the
  backend. Nothing runs there until a built-in action is moved (a later 4.4 step); the worker serves
  `integrations` by default, so a `JOBS_QUEUES` you set must name it (`default,webhooks,emails,exports,imports,integrations`).
