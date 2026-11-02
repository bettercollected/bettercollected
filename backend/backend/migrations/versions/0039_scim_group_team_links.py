"""directory groups feeding teams: the link table and the index behind the read

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-02

Expand only (behind ``FORM_ACCESS_ENABLED``; nothing reads either while it is
off, and a release before this one ignores them):

* ``scim_group_team_links``: the team a directory group feeds. One row per group
  (unique ``group_id``), any number per team. It is a table of its own, not a
  field of ``scim_groups.doc``, because the directory sync, the role mapping and
  a rotation each save the whole group document: a link inside it could be
  restored by a save that read the document before an unlink. The row is removed
  by code in the transaction that deletes the team (no foreign keys anywhere in
  this schema) and when the group or the directory goes. New table, not imported
  from Mongo (``common/common/db/migrate/import_guard.py``).
* ``scim_users.user_id``: a generated column over ``doc`` (the account a
  directory user maps to) and the index ``(workspace_id, user_id)``. "Which
  teams is this person in through a directory group" is asked on every access
  check, and ``user_id`` was only inside ``doc``. Existing rows get the column
  filled by the table rewrite (a directory has a few thousand users at most).

Written by hand in the shape autogenerate produces for a BaseRow table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "scim_group_team_links"


def _spine(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
        nullable=True,
    )


def upgrade() -> None:
    op.create_table(
        TABLE,
        *[_spine(n) for n in ("group_id", "team_id", "workspace_id")],
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
        sa.UniqueConstraint("group_id", name=op.f(f"uq_{TABLE}_group_id")),
        schema=SCHEMA,
    )
    # the teams of a person, and a team's links (deleting a team clears them)
    op.create_index(
        op.f(f"ix_app_{TABLE}_team_id"), TABLE, ["team_id"], unique=False, schema=SCHEMA
    )
    op.create_index(
        op.f(f"ix_app_{TABLE}_workspace_id"),
        TABLE,
        ["workspace_id"],
        unique=False,
        schema=SCHEMA,
    )
    op.add_column("scim_users", _spine("user_id"), schema=SCHEMA)
    op.create_index(
        "ix_scim_users_workspace_user",
        "scim_users",
        ["workspace_id", "user_id"],
        unique=False,
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_scim_users_workspace_user", table_name="scim_users", schema=SCHEMA)
    op.drop_column("scim_users", "user_id", schema=SCHEMA)
    op.drop_index(op.f(f"ix_app_{TABLE}_workspace_id"), table_name=TABLE, schema=SCHEMA)
    op.drop_index(op.f(f"ix_app_{TABLE}_team_id"), table_name=TABLE, schema=SCHEMA)
    op.drop_table(TABLE, schema=SCHEMA)
