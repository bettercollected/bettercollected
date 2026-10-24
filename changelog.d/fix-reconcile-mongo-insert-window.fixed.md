- `reconcile --direction postgres->mongo` checks a copy it inserted into Mongo again once it has
  landed, and removes it when the record was deleted meanwhile (its tombstone, or the Postgres row
  gone), so a delete racing that insert can no longer bring the record back in Mongo.
