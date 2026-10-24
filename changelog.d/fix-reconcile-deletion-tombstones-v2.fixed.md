- `reconcile` could bring back a record deleted in one store whose delete had failed in the other
  (a response, a deletion request, an account). Every delete now records a tombstone (collection,
  id and time only) in the store that deletes, in every write mode. `reconcile` never copies a
  deleted record and deletes its surviving copy instead, in both directions, and `verify` reports
  deleted records that are still present (`tombstoned`). Tombstones are kept 400 days. New table
  `deletion_tombstones` in the `app`, `auth` and `google` schemas (app revision `0021`, auth and
  google `0004`).
