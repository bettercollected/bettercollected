- **Migration `verify` agrees with `reconcile`.** In collections Mongo expires by a TTL index,
  `verify` now treats an expired copy in either store as absent, as `reconcile` already did, so
  copies Mongo's TTL monitor dropped are no longer reported as `missing_in_mongo` on every run;
  the report counts them under `expired`. And `reconcile` (Mongo → Postgres) now copies Mongo's
  version over a Postgres row the application wrote later when the services write Mongo first
  (`mongo`/`dual`): before, it left such a row without counting it, so `verify` reported it as
  mismatched forever. Where Postgres is the primary it still keeps the row, now counted as
  `newer_in_postgres`.
