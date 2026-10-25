- **`auth.migrate preflight` names the size of the case-variant email problem.** Besides counting
  them as duplicate keys (preflight fails), it reports `case_variant_keys` (distinct emails held
  by more than one account, ignoring letter case) and `case_variant_documents` (the accounts
  involved), with a warning that backfill stops `users` on the first one. Counts only, never an
  email or an id.
