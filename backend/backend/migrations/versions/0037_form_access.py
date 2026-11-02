"""form-level access: member groups, their members and form grants

Revision ID: 0037
Revises: 0035
Create Date: 2026-11-02

Three new tables (``backend/app/services/form_access``, behind
``FORM_ACCESS_ENABLED``, off by default):

* ``member_groups``: a workspace's teams (names unique per workspace by the
  trimmed, case-folded ``name_key``);
* ``member_group_members``: the members of a manual team (the id is derived
  from the pair, one row per team and user);
* ``form_access_grants``: a role on one form for a subject. ``subject_type``
  is free text on purpose (``user`` and ``group`` today, ``key`` later), unique
  per (workspace, form, subject).

New tables only, so expand-only: nothing reads them while the switch is off,
and a release before this one ignores them. Written by hand in the shape
autogenerate produces for a BaseRow table.

The number is provisional: 0036 is reserved by another item, so
``down_revision`` is 0035, the head of develop when this was written; whichever
revision merges after this one is re-pointed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0037"
down_revision: Union[str, None] = "0035"
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
    _create(
        "member_groups",
        [_spine(n) for n in ("workspace_id", "name_key")],
        sa.UniqueConstraint(
            "workspace_id", "name_key", name=op.f("uq_member_groups_workspace_id_name_key")
        ),
    )
    op.create_index(
        op.f("ix_app_member_groups_workspace_id"),
        "member_groups",
        ["workspace_id"],
        unique=False,
        schema=SCHEMA,
    )

    _create(
        "member_group_members",
        [_spine(n) for n in ("group_id", "workspace_id", "user_id")],
        sa.UniqueConstraint(
            "group_id", "user_id", name=op.f("uq_member_group_members_group_id_user_id")
        ),
    )
    # "which teams is this member in" (every form decision of a member)
    op.create_index(
        op.f("ix_app_member_group_members_workspace_id"),
        "member_group_members",
        ["workspace_id", "user_id"],
        unique=False,
        schema=SCHEMA,
    )

    _create(
        "form_access_grants",
        [_spine(n) for n in ("workspace_id", "form_id", "subject_type", "subject_id")],
        # one grant per subject on a form of a workspace (a form can be linked
        # into two workspaces; grants never reach across them)
        sa.UniqueConstraint(
            "workspace_id",
            "form_id",
            "subject_type",
            "subject_id",
            name="uq_form_access_grants_subject",
        ),
    )
    # "which forms does this subject hold a grant on" (the list filter)
    op.create_index(
        op.f("ix_app_form_access_grants_workspace_id"),
        "form_access_grants",
        ["workspace_id", "subject_type", "subject_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.create_index(
        op.f("ix_app_form_access_grants_form_id"),
        "form_access_grants",
        ["form_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_form_access_grants_form_id"),
        table_name="form_access_grants",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_app_form_access_grants_workspace_id"),
        table_name="form_access_grants",
        schema=SCHEMA,
    )
    op.drop_table("form_access_grants", schema=SCHEMA)
    op.drop_index(
        op.f("ix_app_member_group_members_workspace_id"),
        table_name="member_group_members",
        schema=SCHEMA,
    )
    op.drop_table("member_group_members", schema=SCHEMA)
    op.drop_index(
        op.f("ix_app_member_groups_workspace_id"),
        table_name="member_groups",
        schema=SCHEMA,
    )
    op.drop_table("member_groups", schema=SCHEMA)
