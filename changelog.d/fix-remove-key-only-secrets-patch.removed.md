- The key-only route `PATCH /temporal/forms/{form}/actions/{action}/secrets`, which actions executors
  older than 4.3 used to write a refreshed Google credential back with their own copy of the encryption
  key, is removed (it answers 404). **Run an actions executor of version 4.3 or later before upgrading
  the backend to 4.4**: the 4.3 executor writes back on the run-scoped route and holds no key. Nothing
  changes for an executor that is already 4.3.
