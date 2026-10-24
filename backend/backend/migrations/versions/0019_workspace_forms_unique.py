"""one link per workspace and form

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-24

``workspace_forms`` gets a unique index on (workspace_id, form_id) in place of
the plain one, matching Mongo's ``uq_workspace_forms_workspace_form``: a form
is linked to a workspace once, so two imports of the same form racing into one
workspace can't both add a link.

Existing duplicates make it fail **before anything changes**, with counts only
(no ids). They are not merged automatically: each link holds its own settings
(custom URL, privacy, pinned, AI insights consent) and no rule can pick one
without losing what the other holds. List them read-only with::

    SELECT workspace_id, form_id, count(*) AS links, array_agg(id) AS ids
    FROM app.workspace_forms
    WHERE workspace_id IS NOT NULL AND form_id IS NOT NULL
    GROUP BY workspace_id, form_id HAVING count(*) > 1;

keep one link per pair (delete the others in both stores while Mongo is still
written) and migrate again.

A plain ``CREATE UNIQUE INDEX`` inside the migration's transaction, not
``CONCURRENTLY``: ``DB_AUTO_MIGRATE`` runs every revision in one transaction,
where non-transactional DDL can't run, and the table holds one small row per
form link, so the build's short write lock is negligible (``DB_AUTO_MIGRATE``
also bounds its wait for the lock). Dropping the old plain index is safe for
the previous release: it only reads through it, and the unique index serves
the same lookups.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "workspace_forms"
OLD = "ix_workspace_forms_workspace_form"
NEW = "uq_workspace_forms_workspace_form"


def upgrade() -> None:
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT count(*), coalesce(sum(n), 0) FROM (SELECT count(*) AS n "
                f"FROM {SCHEMA}.{TABLE} WHERE workspace_id IS NOT NULL AND form_id "
                "IS NOT NULL GROUP BY workspace_id, form_id HAVING count(*) > 1) d"
            )
        )
        .one()
    )
    pairs, rows = int(duplicates[0]), int(duplicates[1])
    if pairs:
        raise RuntimeError(
            f"{SCHEMA}.{TABLE} has {pairs} (workspace_id, form_id) pairs linked by "
            f"{rows} rows, so the unique index can't be created. Nothing was "
            "changed. List them (read-only) with: SELECT workspace_id, form_id, "
            f"count(*), array_agg(id) FROM {SCHEMA}.{TABLE} GROUP BY workspace_id, "
            "form_id HAVING count(*) > 1; keep one link per pair and migrate again "
            "(see the docstring of revision 0019)."
        )
    op.create_index(NEW, TABLE, ["workspace_id", "form_id"], unique=True, schema=SCHEMA)
    op.drop_index(OLD, table_name=TABLE, schema=SCHEMA)


def downgrade() -> None:
    op.create_index(
        OLD, TABLE, ["workspace_id", "form_id"], unique=False, schema=SCHEMA
    )
    op.drop_index(NEW, table_name=TABLE, schema=SCHEMA)
