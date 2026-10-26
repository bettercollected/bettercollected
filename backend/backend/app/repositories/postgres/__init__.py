"""The backend's repositories: Postgres only, one module per repository group.

Each class is built on :class:`common.records.repository.RecordRepository` and
keeps the public methods (and quirks) of the 4.0 Mongo repository it replaced.
The Mongo collections they replace are read only by the import from 4.0
(``python -m backend.migrate``).
"""
