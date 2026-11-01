"""revision log of response edits

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-02

One new table (``backend/app/services/response_revisions``): one entry per edit
of a response, by staff or by the respondent: who (kind, user id, role), when,
which questions changed (ids), and the previous values sealed with the
response keyset. ``response_pk`` references the response row with
``ON DELETE CASCADE``: whatever deletes a response (a person, a deletion
request, a form, a workspace, expiry) deletes its history in the same
statement. New table only, so expand-only. Written by hand in the shape
autogenerate produces for a BaseRow table.

Numbering: follows 0031 (workspace option lists), the head of develop when this was written.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "response_revisions"


def _text(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def _int(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.BigInteger(),
        sa.Computed(f"{SCHEMA}.bc_int(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        _text("response_pk"),
        _text("form_id"),
        _text("workspace_id"),
        _text("actor_id"),
        _int("seq"),
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
        sa.ForeignKeyConstraint(
            ["response_pk"],
            [f"{SCHEMA}.form_responses.id"],
            name=op.f(f"fk_{TABLE}_response_pk_form_responses"),
            ondelete="CASCADE",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        f"uq_{TABLE}_response_seq",
        TABLE,
        ["response_pk", "seq"],
        unique=True,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_app_{TABLE}_actor_id"),
        TABLE,
        ["actor_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f(f"ix_app_{TABLE}_form_id"),
        TABLE,
        ["form_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(op.f(f"ix_app_{TABLE}_form_id"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(op.f(f"ix_app_{TABLE}_actor_id"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(f"uq_{TABLE}_response_seq", table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
