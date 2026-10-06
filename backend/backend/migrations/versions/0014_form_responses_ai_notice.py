"""form responses: AI notice spine columns

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-06

AI insights analyse only responses whose page showed the AI notice (#752):
``ai_notice_provider_name`` and ``ai_notice_shown_at`` become spine columns
generated from the document, so the insights query filters on them. Expand
only: the previous release never reads them. Both stored generated columns
are added in one ``ALTER TABLE``, so ``form_responses`` is rewritten once
under its table lock (seconds at today's size).
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE app.form_responses"
        " ADD COLUMN ai_notice_provider_name TEXT"
        " GENERATED ALWAYS AS (app.bc_text(doc -> 'ai_notice_provider_name')) STORED,"
        " ADD COLUMN ai_notice_shown_at TIMESTAMP WITH TIME ZONE"
        " GENERATED ALWAYS AS (app.bc_ts(doc -> 'ai_notice_shown_at')) STORED"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE app.form_responses"
        " DROP COLUMN ai_notice_shown_at,"
        " DROP COLUMN ai_notice_provider_name"
    )
