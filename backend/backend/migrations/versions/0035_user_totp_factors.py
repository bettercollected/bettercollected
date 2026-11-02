"""authenticator-app second factor: the factors and their recovery codes

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-02

Two new tables (``backend/app/services/mfa``): the TOTP factor of an account
(at most one confirmed and one pending per user; the secret is sealed with the
credential key ring, never stored in clear) and its one-time recovery codes
(an unkeyed SHA-256 bound to the user; the code itself is never stored). New
tables only, so expand-only. Written by hand in the shape autogenerate produces
for a BaseRow table.

The number is provisional: ``down_revision`` is 0034, the head of develop when
this was written; whichever revision merges after this one is re-pointed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"


def _spine(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def _create(table: str, spines: Sequence[sa.Column], *constraints) -> None:
    op.create_table(
        table,
        *spines,
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
            name=op.f(f"ck_{table}_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'",
            name=op.f(f"ck_{table}_id_is_object_id"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        *constraints,
        schema=SCHEMA,
    )


def upgrade() -> None:
    _create("user_totp_factors", [_spine(n) for n in ("user_id", "state")])
    # one confirmed and one pending factor per account
    op.create_index(
        "uq_user_totp_factors_confirmed",
        "user_totp_factors",
        ["user_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("state = 'confirmed'"),
    )
    op.create_index(
        "uq_user_totp_factors_pending",
        "user_totp_factors",
        ["user_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("state = 'pending'"),
    )
    op.create_index(
        op.f("ix_app_user_totp_factors_created_at"),
        "user_totp_factors",
        ["created_at"],
        unique=False,
        schema=SCHEMA,
    )
    _create(
        "user_recovery_codes",
        [_spine(n) for n in ("factor_id", "user_id", "code_hash")],
        sa.UniqueConstraint("code_hash", name=op.f("uq_user_recovery_codes_code_hash")),
    )
    op.create_index(
        op.f("ix_app_user_recovery_codes_user_id"),
        "user_recovery_codes",
        ["user_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_user_recovery_codes_factor_id"),
        "user_recovery_codes",
        ["factor_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    for name in (
        "ix_app_user_recovery_codes_factor_id",
        "ix_app_user_recovery_codes_user_id",
    ):
        op.drop_index(op.f(name), table_name="user_recovery_codes", schema=SCHEMA)
    op.drop_table("user_recovery_codes", schema=SCHEMA)
    op.drop_index(
        op.f("ix_app_user_totp_factors_created_at"),
        table_name="user_totp_factors",
        schema=SCHEMA,
    )
    for name in ("uq_user_totp_factors_pending", "uq_user_totp_factors_confirmed"):
        op.drop_index(name, table_name="user_totp_factors", schema=SCHEMA)
    op.drop_table("user_totp_factors", schema=SCHEMA)
