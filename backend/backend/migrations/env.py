from alembic import context

import backend.db.models  # noqa: F401  registers every table on Base.metadata
from backend.db.base import SCHEMA, Base
from common.db.alembic_support import run_migrations

run_migrations(context, Base.metadata, SCHEMA)
