"""indexes of the staff responses list (sort by form version, status lookup)

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-31

Expand only: two new indexes, nothing read or changed in existing rows.

The list pages by keyset on ``(created_at, id)``: the existing
``(workspace_id, form_id, created_at)`` index already serves every page of it
(forward, backward, from a cursor), measured at 300,000 responses in one form,
so the default sort needs no index of its own. Two things did lack one:

* ``ix_form_responses_list_version``: ``(form_id,
  coalesce(form_version, 0), created_at, id)`` over the responses that have
  answers, for the sort by form version (without it every page sorts the whole
  form).
* ``ix_deletion_requests_response``: ``response_id`` of the deletion requests.
  The list looks up the request of each row it shows (its status) and the
  status filter probes by the same column; no index of the table started with
  it.

Revisions run in one transaction, so these are plain ``CREATE INDEX`` and the
build blocks writes to the table meanwhile (seconds at hundreds of thousands of
rows). ``IF NOT EXISTS``: a large deployment may create them first by hand,
without blocking, then run this revision, which finds them there:

    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_form_responses_list_version
      ON app.form_responses (form_id, (coalesce(form_version, 0)), created_at, id)
      WHERE doc ? 'answers';
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_deletion_requests_response
      ON app.responses_deletion_requests (response_id);
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_form_responses_list_version "
        f"ON {SCHEMA}.form_responses "
        f"(form_id, (coalesce(form_version, 0)), created_at, id) "
        f"WHERE doc ? 'answers'"
    )
    op.execute(
        f"CREATE INDEX IF NOT EXISTS ix_deletion_requests_response "
        f"ON {SCHEMA}.responses_deletion_requests (response_id)"
    )


def downgrade() -> None:
    for name in (
        "ix_deletion_requests_response",
        "ix_form_responses_list_version",
    ):
        op.execute(f"DROP INDEX IF EXISTS {SCHEMA}.{name}")
