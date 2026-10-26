"""respondent identity key check, and an index of the identities still to convert

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-26

Expand only: a new one-row table and two partial indexes; nothing is read or
changed in existing rows, and no secret is needed to apply it.

* ``respondent_identity_key_check``: HMAC-SHA256(RESPONDENT_IDENTITY_KEY, a
  fixed label), written by ``backend.identity_rekey`` before its first
  conversion. It tells a later start whether the configured key is the one that
  converted the stored identities (a mistyped or drifted key is refused). It is
  not the key and cannot be used to compute or match an identity.
* ``ix_form_responses_legacy_identity`` / ``ix_deletion_requests_legacy_identity``:
  the rows whose ``anonymous_identity`` is not ``v2:`` yet. The conversion pass
  and its counts read only these, so a start with nothing left to convert does
  not walk the tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
WHERE = "anonymous_identity IS NOT NULL AND anonymous_identity NOT LIKE 'v2:%'"
INDEXES = {
    "ix_form_responses_legacy_identity": "form_responses",
    "ix_deletion_requests_legacy_identity": "responses_deletion_requests",
}


def upgrade() -> None:
    op.create_table(
        "respondent_identity_key_check",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("check_value", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_respondent_identity_key_check_one_row"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_respondent_identity_key_check")),
        schema=SCHEMA,
    )
    for name, table in INDEXES.items():
        op.create_index(
            name,
            table,
            ["id"],
            unique=False,
            schema=SCHEMA,
            postgresql_where=sa.text(WHERE),
        )


def downgrade() -> None:
    for name, table in INDEXES.items():
        op.drop_index(name, table_name=table, schema=SCHEMA)
    op.drop_table("respondent_identity_key_check", schema=SCHEMA)
