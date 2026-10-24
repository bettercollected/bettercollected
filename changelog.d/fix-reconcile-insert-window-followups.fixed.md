- `reconcile --direction postgres->mongo` refuses to run unless every group it covers is on
  `DB_WRITE_MODE=postgres_primary_dual` (`--dry-run` excepted): under `dual`, Mongo deletes first and
  records no tombstone for a document that is not there, so a delete racing its Mongo insert would
  not be caught. When reconcile's removal of its own copy finds nothing left to remove, it says so
  in the log.
