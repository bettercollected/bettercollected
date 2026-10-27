"""registration services, form registrations and deliveries

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-27

Three new tables for registering submissions in a workspace's case system
(``backend/app/services/registration``): the destinations a workspace's admins
configure, a form's registration settings, and one delivery record per
response. New tables only, so expand-only. Written by hand in the shape
autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023"
down_revision: Union[str, None] = "0022"
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


def _create(table: str, spines: Sequence[str], *constraints) -> None:
    op.create_table(
        table,
        *[_spine(name) for name in spines],
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
    _create(
        "registration_services",
        ("workspace_id", "name", "kind"),
        sa.UniqueConstraint(
            "workspace_id",
            "name",
            name=op.f("uq_registration_services_workspace_id_name"),
        ),
    )
    _create(
        "form_registrations",
        ("workspace_id", "form_id", "service_id"),
        sa.UniqueConstraint(
            "workspace_id",
            "form_id",
            name=op.f("uq_form_registrations_workspace_id_form_id"),
        ),
    )
    op.create_index(
        op.f("ix_app_form_registrations_service_id"),
        "form_registrations",
        ["service_id"],
        unique=False,
        schema=SCHEMA,
    )
    _create(
        "registration_deliveries",
        ("workspace_id", "form_id", "response_id", "registration_id", "status"),
        sa.UniqueConstraint(
            "registration_id",
            "response_id",
            name=op.f("uq_registration_deliveries_registration_id_response_id"),
        ),
    )
    op.create_index(
        op.f("ix_app_registration_deliveries_workspace_id"),
        "registration_deliveries",
        ["workspace_id", "form_id", "status"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_registration_deliveries_response_id"),
        "registration_deliveries",
        ["response_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_registration_deliveries_status"),
        "registration_deliveries",
        ["status", "created_at"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    for name in (
        "ix_app_registration_deliveries_status",
        "ix_app_registration_deliveries_response_id",
        "ix_app_registration_deliveries_workspace_id",
    ):
        op.drop_index(op.f(name), table_name="registration_deliveries", schema=SCHEMA)
    op.drop_table("registration_deliveries", schema=SCHEMA)
    op.drop_index(
        op.f("ix_app_form_registrations_service_id"),
        table_name="form_registrations",
        schema=SCHEMA,
    )
    op.drop_table("form_registrations", schema=SCHEMA)
    op.drop_table("registration_services", schema=SCHEMA)
