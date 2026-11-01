- Response exports are bounded better. Exports that stream to the browser (and the
  bulk JSON read) now count as running: at most 2 per person and 6 per workspace at once,
  counted in the database so the limit holds across several backend replicas (429
  `export_busy` or `workspace_busy`). A large export that no worker takes within 2 hours
  now fails as `queue_timeout` (shown as a failed export) instead of waiting for ever and
  holding the workspace's export slots. A running export job now records its own
  heartbeat, also while it reads rows, so a stuck job is told apart without losing when
  it started.
