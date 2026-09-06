"""Postgres rows for the auth service (schema ``auth``) — plans/postgres-consolidation.md.

This package deliberately lives beside ``app``, not inside it: importing anything
under ``app`` runs ``app/__init__`` and boots the whole application (settings, APM,
database clients), which Alembic and the tests must never do.
"""
