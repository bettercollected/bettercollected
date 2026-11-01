- The run's context route (`POST /temporal/.../runs/{r}/context`) takes an optional `{"secrets": "plain"}`
  request: the action's, the workspace's and the form's secrets for that action then come back already opened, so
  the actions executor needs no encryption key. A new run-scoped route
  (`PATCH /temporal/.../runs/{r}/secrets`: the run's token and job, as the context route) takes a refreshed Google
  credential back in plain (only the `Credentials` secret) and seals it with the backend's key. Each hand-out of
  opened secrets is logged with the run's ids and a count. Nothing changes for an executor that asks for neither.
