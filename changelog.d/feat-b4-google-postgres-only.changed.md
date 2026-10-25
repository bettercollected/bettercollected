- The Google Forms integration stores its data in Postgres only: the Mongo credential store and the
  routing between the two stores are gone, and the service never connects to Mongo (`MONGO_URI` and
  `MONGO_DB` are read only by `python -m googleform.migrate`, which imports the 4.0 data). It needs
  `DATABASE_URL`, and refuses to start while `DB_READ_SOURCE`, `DB_WRITE_MODE` or their `__google`
  overrides name anything but `postgres`; remove them or set them to `postgres`. The Google Forms
  routes now read the signed-in user's credential through the same Postgres store as the rest of
  the service.
