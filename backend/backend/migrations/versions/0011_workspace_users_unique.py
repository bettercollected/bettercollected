"""one membership per workspace and user

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-05

``workspace_users`` gets a unique index on (workspace_id, user_id) in place
of the plain one, so two writers racing to add the same member (SSO, SCIM,
an invitation) can't both succeed. Existing duplicates make it fail **before
anything changes**, with a message naming them: run
``python -m backend.membership_duplicates`` and resolve them by hand (see
docs/sso.md, "Duplicate memberships"). Nothing is deleted automatically.
Dropping the old plain index is safe for the previous release (it only
reads through it, and the unique index serves the same lookups).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "workspace_users"
OLD = "ix_workspace_users_workspace_user"
NEW = "uq_workspace_users_workspace_user"


def upgrade() -> None:
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                f"SELECT count(*) FROM (SELECT 1 FROM {SCHEMA}.{TABLE} "
                "GROUP BY workspace_id, user_id HAVING count(*) > 1) d"
            )
        )
        .scalar()
    )
    if duplicates:
        raise RuntimeError(
            f"{SCHEMA}.{TABLE} has {duplicates} (workspace_id, user_id) pairs with "
            "more than one membership, so the unique index can't be created. "
            "Nothing was changed. Run `python -m backend.membership_duplicates` "
            "to list them, resolve them by hand (docs/sso.md, 'Duplicate "
            "memberships') and migrate again."
        )
    op.create_index(NEW, TABLE, ["workspace_id", "user_id"], unique=True, schema=SCHEMA)
    op.drop_index(OLD, table_name=TABLE, schema=SCHEMA)


def downgrade() -> None:
    op.create_index(
        OLD, TABLE, ["workspace_id", "user_id"], unique=False, schema=SCHEMA
    )
    op.drop_index(NEW, table_name=TABLE, schema=SCHEMA)
