"""Postgres rows for the backend (schema ``app``) — plans/postgres-consolidation.md.

Nothing in the application reads or writes these yet; the repository layer
lands in the following PRs. Alembic (``backend/alembic.ini``) owns the schema.

This package deliberately lives beside ``app``, not inside it: importing anything
under ``app`` runs ``app/__init__`` and boots the whole application (settings, APM,
database clients), which Alembic and the tests must never do.
"""
