- auth allows one account per email address ignoring case (database revision `0005`). An
  instance that already holds accounts whose emails differ only in case refuses the migration,
  naming only the counts, and nothing is merged automatically: check and resolve them before
  upgrading (docs/postgres-cutover-runbook.md, "Accounts whose emails differ only in case").
  `python -m auth.migrate preflight` counts them too.
