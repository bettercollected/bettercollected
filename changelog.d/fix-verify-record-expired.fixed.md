- **Migration `verify` records groups that hold expired TTL copies.** A clean `verify` refused to
  record a group (and so the service marker) when a collection Mongo expires by a TTL index held
  expired copies in only one store, because it still compared the raw counts. It now compares the
  live counts, without the expired copies, and the report counts those per store
  (`expired_mongo`, `expired_postgres`; `expired` stays the total). The recorded counts are the
  live ones, with the expired copies beside them. `verify` still deletes nothing.
