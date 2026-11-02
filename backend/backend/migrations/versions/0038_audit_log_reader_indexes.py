"""audit log reader: who / form columns and the indexes behind its filters

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-02

The audit log page (``backend/app/services/audit_log``) reads
``workspace_audit_events`` newest first with filters on the form and on the
person (the actor or the one it was done to). The three ids live inside ``doc``,
not in columns, so each filter would scan the workspace's rows. Expand only:

* generated columns ``form_id``, ``user_id`` (the actor) and ``target_user_id``,
  computed from ``doc`` the way ``workspace_id`` and ``event`` are (existing rows
  get them filled by the table rewrite; the table holds a few thousand rows per
  workspace at most);
* ``(workspace_id, created_at, id)``: the keyset pair of the page, so a page is
  an index range scan with no sort;
* ``(workspace_id, form_id, created_at)`` where ``form_id`` is set: a form's
  activity;
* ``(workspace_id, user_id, created_at)``: what a person did;
* ``(workspace_id, target_user_id, created_at)`` where ``target_user_id`` is
  set: what was done to a person.

The two indexes of revision 0030 stay (the purge reads ``created_at``). The
table is Postgres only and is not imported from Mongo
(``common/common/db/migrate/import_guard.py``).

Revisions run in one transaction, so these are plain ``CREATE INDEX``; the table
is small and a write waits for them for a moment.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "workspace_audit_events"
COLUMNS = ("form_id", "user_id", "target_user_id")

# name -> (columns, partial predicate)
INDEXES = {
    "ix_workspace_audit_events_keyset": (
        ("workspace_id", "created_at", "id"),
        None,
    ),
    "ix_workspace_audit_events_form": (
        ("workspace_id", "form_id", "created_at"),
        "form_id IS NOT NULL",
    ),
    "ix_workspace_audit_events_actor": (
        ("workspace_id", "user_id", "created_at"),
        None,
    ),
    "ix_workspace_audit_events_target": (
        ("workspace_id", "target_user_id", "created_at"),
        "target_user_id IS NOT NULL",
    ),
}


def upgrade() -> None:
    for name in COLUMNS:
        op.add_column(
            TABLE,
            sa.Column(
                name,
                sa.Text(),
                sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
                nullable=True,
            ),
            schema=SCHEMA,
        )
    for name, (columns, where) in INDEXES.items():
        op.create_index(
            name,
            TABLE,
            list(columns),
            unique=False,
            schema=SCHEMA,
            postgresql_where=sa.text(where) if where else None,
        )


def downgrade() -> None:
    for name in INDEXES:
        op.drop_index(name, table_name=TABLE, schema=SCHEMA)
    for name in COLUMNS:
        op.drop_column(TABLE, name, schema=SCHEMA)
