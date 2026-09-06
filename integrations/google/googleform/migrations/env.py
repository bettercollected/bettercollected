from alembic import context

import googleform.db.models  # noqa: F401  registers every table on Base.metadata
from common.db.alembic_support import run_migrations
from googleform.db.base import SCHEMA, Base

run_migrations(context, Base.metadata, SCHEMA)
