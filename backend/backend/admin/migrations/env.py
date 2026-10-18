from alembic import context

from backend.admin.repositories.tables import SCHEMA, metadata
from common.db.alembic_support import run_migrations

run_migrations(context, metadata, SCHEMA)
