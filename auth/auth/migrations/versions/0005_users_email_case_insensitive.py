"""one account per email, ignoring case

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-25

Email addresses are case-insensitive in practice, but ``uq_users_email`` was
not: a code sign-in as ``Jane@Example.com`` created a second account next to
``jane@example.com``. Every lookup now compares ``lower(email)``, and this
revision replaces the exact unique constraint with a unique index on
``lower(email)``, which also serves those lookups.

Existing accounts whose emails differ only in case make it fail **before
anything changes**, with counts only (no ids, no addresses). They are never
merged automatically: each account holds its own workspaces, forms, sessions
and billing, and no rule can pick one without taking from the other. Resolve
them by hand (docs/postgres-cutover-runbook.md, "Accounts whose emails differ
only in case") and migrate again. Stored addresses keep the case they were
written with.

A plain ``CREATE UNIQUE INDEX`` inside the migration's transaction, not
``CONCURRENTLY``: ``DB_AUTO_MIGRATE`` runs every revision in one transaction,
and ``auth.users`` holds one small row per account.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "auth"
TABLE = "users"
OLD = "uq_users_email"
NEW = "uq_users_email_lower"
FIND_QUERY = (
    f"SELECT lower(email), count(*), array_agg(id ORDER BY id) FROM {SCHEMA}.{TABLE} "
    "WHERE email IS NOT NULL GROUP BY lower(email) HAVING count(*) > 1"
)


def upgrade() -> None:
    groups, accounts = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*), coalesce(sum(n), 0) FROM (SELECT count(*) AS n "
                f"FROM {SCHEMA}.{TABLE} WHERE email IS NOT NULL "
                "GROUP BY lower(email) HAVING count(*) > 1) d"
            )
        )
        .one()
    )
    if groups:
        raise RuntimeError(
            f"{SCHEMA}.{TABLE} has {int(groups)} email addresses held by "
            f"{int(accounts)} accounts that differ only in case, so emails "
            "can't be made unique ignoring case. Nothing was changed and no "
            "account was merged. Find them (read-only) with: "
            f"{FIND_QUERY}; resolve them by hand "
            "(docs/postgres-cutover-runbook.md, 'Accounts whose emails differ "
            "only in case') and migrate again."
        )
    op.create_index(NEW, TABLE, [sa.text("lower(email)")], unique=True, schema=SCHEMA)
    op.drop_constraint(OLD, TABLE, schema=SCHEMA, type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(OLD, TABLE, ["email"], schema=SCHEMA)
    op.drop_index(NEW, table_name=TABLE, schema=SCHEMA)
