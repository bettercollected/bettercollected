- The backend keeps its responses data in Postgres only: form responses and their deletion
  requests, responders and tags, and responder groups. Every backend group is now served from
  Postgres, so the backend and its job worker no longer use Mongo. A
  `DB_READ_SOURCE__responses` or `DB_WRITE_MODE__responses` setting other than `postgres` now stops
  the backend from starting and names the setting: remove it (`DB_WRITE_MODE__RESPONSES` left empty
  is fine). A 4.0 database's responses are imported with
  `python -m backend.migrate --group responses backfill`, and the backend refuses to start while a
  responses collection in Mongo has documents that were never imported. Answers stay encrypted as
  stored; nothing about them is decrypted, logged or queried by the repository.
