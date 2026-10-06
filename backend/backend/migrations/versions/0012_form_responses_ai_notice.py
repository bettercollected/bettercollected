"""form responses: AI notice spine columns

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-06

AI insights analyse only responses whose page showed the AI notice (#752):
``ai_notice_provider_name`` and ``ai_notice_shown_at`` become spine columns
generated from the document, so the insights query filters on them. Expand
only: the previous release never reads them. Adding stored generated columns
rewrites ``form_responses`` once under its table lock (seconds at today's
size).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"
TABLE = "form_responses"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "ai_notice_provider_name",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'ai_notice_provider_name')", persisted=True),
            nullable=True,
        ),
        schema=SCHEMA,
    )
    op.add_column(
        TABLE,
        sa.Column(
            "ai_notice_shown_at",
            postgresql.TIMESTAMP(timezone=True),
            sa.Computed("app.bc_ts(doc -> 'ai_notice_shown_at')", persisted=True),
            nullable=True,
        ),
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_column(TABLE, "ai_notice_shown_at", schema=SCHEMA)
    op.drop_column(TABLE, "ai_notice_provider_name", schema=SCHEMA)
