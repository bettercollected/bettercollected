"""workspace security events (owner break-glass audit)

Revision ID: 0030
Revises: 0028
Create Date: 2026-11-01

One new table (``backend/app/services/sso/policy.py``): who got into a workspace
that requires single sign-on through the owners' break-glass, one entry per
request (session, user, method and route template; ids only). New
table only, so expand-only. Written by hand in the shape autogenerate produces
for a BaseRow table.

Revision 0029 is the option-sources branch's: whichever of 0029 and 0030 merges
second re-points its ``down_revision`` at the other (this one at 0029 if 0029
lands first).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "workspace_audit_events"


def _text(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        _text("workspace_id"),
        _text("session_id"),
        _text("event"),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')",
            name=op.f(f"ck_{TABLE}_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f(f"ck_{TABLE}_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TABLE}")),
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_app_{TABLE}_workspace_id"),
        TABLE,
        ["workspace_id", "created_at"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_app_{TABLE}_created_at"),
        TABLE,
        ["created_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(op.f(f"ix_app_{TABLE}_created_at"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(
        op.f(f"ix_app_{TABLE}_workspace_id"), table_name=TABLE, schema=SCHEMA
    )
    op.drop_table(TABLE, schema=SCHEMA)
