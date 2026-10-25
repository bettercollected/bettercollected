- **`auth.migrate preflight` counts accounts whose emails differ only in letter case**
  (`case_variant_keys`: distinct emails held by more than one account; `case_variant_documents`:
  the accounts involved), as a warning with counts only. A later release makes an email unique
  ignoring case, so these accounts have to be merged before upgrading; on 4.0 they keep working
  and preflight still passes.
