"""workspaces custom_domain index ignores empty strings

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25

A workspace without a domain stores null or "" (35 of 3212 in production);
the partial unique index must exclude both. Written by hand: autogenerate
does not compare a partial index's WHERE clause.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
INDEX = "uq_workspaces_custom_domain"


def upgrade() -> None:
    op.drop_index(INDEX, table_name="workspaces", schema=SCHEMA)
    op.create_index(
        INDEX,
        "workspaces",
        ["custom_domain"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("custom_domain IS NOT NULL AND custom_domain <> ''"),
    )


def downgrade() -> None:
    op.drop_index(INDEX, table_name="workspaces", schema=SCHEMA)
    op.create_index(
        INDEX,
        "workspaces",
        ["custom_domain"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("custom_domain IS NOT NULL"),
    )
