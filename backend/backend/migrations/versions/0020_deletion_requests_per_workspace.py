"""deletion requests: one per response, provider and workspace

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-24

A provider response imported into two workspaces is stored once in each
(0015, #768), and each workspace files and completes its own deletion request
for its copy. The unique ``(form_id, response_id, provider)`` let a request
filed in one workspace refuse the other's; it becomes
``(form_id, response_id, provider, workspace_id)``, nulls not distinct (as
0015 did for ``form_responses``): requests stored before ``workspace_id``
existed count as one more "workspace", so two unstamped requests for the same
response still collide.

The new key is wider than the old one, so existing rows always satisfy it: no
duplicate check is needed. The index is built in the migration's transaction
(``DB_AUTO_MIGRATE`` runs every revision in one transaction, so not
``CONCURRENTLY``); the table holds one small row per deletion request.
Dropping the old constraint is safe for the previous release: it never relied
on it for a write (requests are upserted on ``id``) and it already looks
requests up per workspace. The downgrade restores it and fails while two
workspaces hold a request for the same response.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD = "uq_responses_deletion_requests_form_id_response_id_provider"
NEW = "uq_deletion_requests_form_response_provider_workspace"


def upgrade() -> None:
    op.execute(
        f"CREATE UNIQUE INDEX {NEW} ON app.responses_deletion_requests"
        " (form_id, response_id, provider, workspace_id) NULLS NOT DISTINCT"
    )
    op.execute(f"ALTER TABLE app.responses_deletion_requests DROP CONSTRAINT {OLD}")


def downgrade() -> None:
    op.execute(
        f"ALTER TABLE app.responses_deletion_requests ADD CONSTRAINT {OLD}"
        " UNIQUE NULLS NOT DISTINCT (form_id, response_id, provider)"
    )
    op.execute(f"DROP INDEX app.{NEW}")
