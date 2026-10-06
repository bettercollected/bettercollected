"""form responses and deletion requests: workspace_id spine column

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-06

A response belongs to the workspace it was collected in or imported into
(#768): a provider form linked to several workspaces has the same form_id in
each, so workspace reads filter on ``(workspace_id, form_id)``.
``workspace_id`` becomes a spine column generated from the document on
``form_responses`` (indexed with form_id and created_at, the listing order)
and on ``responses_deletion_requests``. Expand only: the previous release
never reads them. Each table is rewritten once under its lock (seconds at
today's size); the indexes are built in the same transaction.

``response_id`` was unique on its own; a provider response is now stored once
per workspace, so uniqueness moves to ``(response_id, workspace_id)`` (nulls
not distinct: rows stored before this count as one more "workspace"). The
previous release never relied on the old constraint for a write (upserts
conflict on ``id``), so a rollback still works. The downgrade restores it and
fails while two workspaces hold a copy of the same response.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.form_responses"
        " ADD COLUMN workspace_id TEXT"
        " GENERATED ALWAYS AS (app.bc_text(doc -> 'workspace_id')) STORED"
    )
    op.execute(
        "CREATE INDEX ix_form_responses_workspace_form_created"
        " ON app.form_responses (workspace_id, form_id, created_at)"
    )
    op.execute(
        "ALTER TABLE app.responses_deletion_requests"
        " ADD COLUMN workspace_id TEXT"
        " GENERATED ALWAYS AS (app.bc_text(doc -> 'workspace_id')) STORED"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_form_responses_response_workspace"
        " ON app.form_responses (response_id, workspace_id) NULLS NOT DISTINCT"
        " WHERE response_id IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE app.form_responses"
        " DROP CONSTRAINT uq_form_responses_response_id"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE app.form_responses"
        " ADD CONSTRAINT uq_form_responses_response_id UNIQUE (response_id)"
    )
    op.execute("DROP INDEX app.uq_form_responses_response_workspace")
    op.execute("ALTER TABLE app.responses_deletion_requests DROP COLUMN workspace_id")
    op.execute("DROP INDEX app.ix_form_responses_workspace_form_created")
    op.execute("ALTER TABLE app.form_responses DROP COLUMN workspace_id")
