"""indexes of the staff responses list (sort by form version, status lookup)

Revision ID: 0025
Revises: 0024
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
build blocks writes to the table meanwhile: about 2 seconds per million rows on
a warm disk, more on a cold one. The runtime ``lock_timeout`` is 5 seconds, so
submissions can fail while a long build runs: on a large table build the
indexes first by hand, without blocking, then run this revision, which finds
them there (``IF NOT EXISTS``):

    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_form_responses_list_version
      ON app.form_responses (form_id, (coalesce(form_version, 0)), created_at, id)
      WHERE doc ? 'answers';
    CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_deletion_requests_response
      ON app.responses_deletion_requests (response_id);

A failed or cancelled ``CREATE INDEX CONCURRENTLY`` leaves an INVALID index of
that name, which ``IF NOT EXISTS`` would skip silently. This revision therefore
drops an invalid one before creating it. To check by hand:

    SELECT indisvalid FROM pg_index
     WHERE indexrelid = 'app.ix_form_responses_list_version'::regclass;

and, when it is false, ``DROP INDEX app.ix_form_responses_list_version`` and
build it again.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"


def _drop_if_invalid(name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = '{SCHEMA}' AND c.relname = '{name}'
                  AND NOT i.indisvalid
            ) THEN
                DROP INDEX {SCHEMA}.{name};
            END IF;
        END
        $$
        """
    )


def upgrade() -> None:
    _drop_if_invalid("ix_form_responses_list_version")
    _drop_if_invalid("ix_deletion_requests_response")
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
