"""scim directory sync

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-04

SCIM directory sync (docs/sso.md): a workspace's directory in Ory Polis, its
users and groups as last seen, group memberships and accepted webhook events
(expired rows are deleted on each claim). New tables only, so expand-only.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scim_directories",
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "polis_directory_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'polis_directory_id')", persisted=True),
            nullable=True,
        ),
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
            name=op.f("ck_scim_directories_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_scim_directories_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scim_directories")),
        sa.UniqueConstraint(
            "polis_directory_id", name=op.f("uq_scim_directories_polis_directory_id")
        ),
        sa.UniqueConstraint(
            "workspace_id", name=op.f("uq_scim_directories_workspace_id")
        ),
        schema="app",
    )
    op.create_table(
        "scim_events",
        sa.Column(
            "event_key",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'event_key')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            postgresql.TIMESTAMP(timezone=True),
            sa.Computed("app.bc_ts(doc -> 'expires_at')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_scim_events_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_scim_events_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scim_events")),
        sa.UniqueConstraint("event_key", name=op.f("uq_scim_events_event_key")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_scim_events_expires_at"),
        "scim_events",
        ["expires_at"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "scim_group_members",
        sa.Column(
            "directory_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'directory_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "group_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'group_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "scim_user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'scim_user_id')", persisted=True),
            nullable=True,
        ),
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
            name=op.f("ck_scim_group_members_id_matches_doc"),
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_scim_group_members_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scim_group_members")),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_scim_group_members_directory_id"),
        "scim_group_members",
        ["directory_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_scim_group_members_group_id"),
        "scim_group_members",
        ["group_id"],
        unique=False,
        schema="app",
    )
    op.create_index(
        op.f("ix_app_scim_group_members_scim_user_id"),
        "scim_group_members",
        ["scim_user_id"],
        unique=False,
        schema="app",
    )
    op.create_table(
        "scim_groups",
        sa.Column(
            "directory_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'directory_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "polis_group_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'polis_group_id')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_scim_groups_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_scim_groups_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scim_groups")),
        sa.UniqueConstraint(
            "directory_id",
            "polis_group_id",
            name=op.f("uq_scim_groups_directory_id_polis_group_id"),
        ),
        schema="app",
    )
    op.create_table(
        "scim_users",
        sa.Column(
            "directory_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'directory_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "workspace_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'workspace_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "polis_user_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'polis_user_id')", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "email",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'email')", persisted=True),
            nullable=True,
        ),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("doc", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "_bc_source", sa.Text(), server_default=sa.text("'app'"), nullable=False
        ),
        sa.Column("_bc_checksum", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id = (doc -> '_id' ->> '$oid')", name=op.f("ck_scim_users_id_matches_doc")
        ),
        sa.CheckConstraint(
            "id ~ '^[0-9a-f]{24}$'", name=op.f("ck_scim_users_id_is_object_id")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scim_users")),
        sa.UniqueConstraint(
            "directory_id",
            "polis_user_id",
            name=op.f("uq_scim_users_directory_id_polis_user_id"),
        ),
        schema="app",
    )
    op.create_index(
        op.f("ix_app_scim_users_workspace_id"),
        "scim_users",
        ["workspace_id", "email"],
        unique=False,
        schema="app",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_scim_users_workspace_id"), table_name="scim_users", schema="app"
    )
    op.drop_table("scim_users", schema="app")
    op.drop_table("scim_groups", schema="app")
    op.drop_index(
        op.f("ix_app_scim_group_members_scim_user_id"),
        table_name="scim_group_members",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_scim_group_members_group_id"),
        table_name="scim_group_members",
        schema="app",
    )
    op.drop_index(
        op.f("ix_app_scim_group_members_directory_id"),
        table_name="scim_group_members",
        schema="app",
    )
    op.drop_table("scim_group_members", schema="app")
    op.drop_index(
        op.f("ix_app_scim_events_expires_at"), table_name="scim_events", schema="app"
    )
    op.drop_table("scim_events", schema="app")
    op.drop_table("scim_directories", schema="app")
