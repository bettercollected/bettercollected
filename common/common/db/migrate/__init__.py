"""The Mongo → Postgres migration engine (plans/postgres-consolidation.md §5).

``preflight`` · ``backfill`` · ``verify`` · ``reconcile`` · ``status`` (and a
service-provided ``jobs-sweep``). Runs as a one-off process per service —
``python -m backend.migrate``, ``python -m auth.migrate``,
``python -m googleform.migrate`` — each with its own rows, schema, Mongo
database and least-privilege role. Raw pymongo and SQLAlchemy Core only: no
Beanie, nothing is ever decrypted, every batch is a fresh short query and one
short transaction, every run is idempotent and resumable.
"""

from common.db.migrate.engine import Runner, Target
from common.db.migrate.progress import MigrationProgressMixin

__all__ = ["Runner", "Target", "MigrationProgressMixin"]
