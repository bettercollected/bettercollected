"""one AI preference memory per workspace and user

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-20

``ai_preference_memories`` gets a unique index on (workspace_id, user_id) in
place of the plain one, matching Mongo's ``workspace_user_unique``, so two
writers racing to create the same user's memory can't both succeed once
Postgres is the primary store.

Existing duplicates make it fail **before anything changes**, with a count
only (no ids, no content). They are not merged automatically: two rows hold
separate learned entries and consent timestamps, and no rule can pick one
without losing what the other holds. Resolve them by hand (see
docs/postgres-cutover-runbook.md, "Duplicate AI preference memories") and
migrate again.

A plain ``CREATE UNIQUE INDEX`` inside the migration's transaction, not
``CONCURRENTLY``: ``DB_AUTO_MIGRATE`` runs every revision in one transaction,
where non-transactional DDL can't run, and the table holds at most one small
row per workspace member who used the AI assistant, so the build's short
write lock is negligible (``DB_AUTO_MIGRATE`` also bounds its wait for the
lock).
Dropping the old plain index is safe for the previous release: it only reads
through it, and the unique index serves the same lookups.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "ai_preference_memories"
OLD = "ix_ai_preference_memories_workspace_user"
NEW = "uq_ai_preference_memories_workspace_user"


def upgrade() -> None:
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT count(*), coalesce(sum(n), 0) FROM (SELECT count(*) AS n "
                f"FROM {SCHEMA}.{TABLE} WHERE workspace_id IS NOT NULL AND user_id "
                "IS NOT NULL GROUP BY workspace_id, user_id HAVING count(*) > 1) d"
            )
        )
        .one()
    )
    pairs, rows = int(duplicates[0]), int(duplicates[1])
    if pairs:
        raise RuntimeError(
            f"{SCHEMA}.{TABLE} has {pairs} (workspace_id, user_id) pairs held by "
            f"{rows} rows, so the unique index can't be created. Nothing was "
            "changed. Resolve them by hand (docs/postgres-cutover-runbook.md, "
            "'Duplicate AI preference memories') and migrate again."
        )
    op.create_index(NEW, TABLE, ["workspace_id", "user_id"], unique=True, schema=SCHEMA)
    op.drop_index(OLD, table_name=TABLE, schema=SCHEMA)


def downgrade() -> None:
    op.create_index(
        OLD, TABLE, ["workspace_id", "user_id"], unique=False, schema=SCHEMA
    )
    op.drop_index(NEW, table_name=TABLE, schema=SCHEMA)
