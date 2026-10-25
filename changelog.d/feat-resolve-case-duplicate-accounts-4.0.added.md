- **Admin task `auth.resolve_case_duplicate_accounts`** resolves accounts whose emails differ only
  in case, which 4.1 refuses to start with. Per group: accounts without forms are dropped; if one
  account has forms it stays; if none has, the one created last stays; if two or more have forms,
  those are listed for manual handling. The dry run lists every group (account ids, created time,
  forms count, decision; never an email); the apply deletes each dropped account through the
  product's own account deletion and reports the groups that remain. It needs the same new
  `ADMIN_TASKS_API_KEY` on the `backend` and `task-runner` services (docs/admin-service.md).
