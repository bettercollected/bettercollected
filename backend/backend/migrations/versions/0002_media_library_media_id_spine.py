"""media library media_id spine

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-06 15:48:27.898269
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "media_libraries",
        sa.Column(
            "media_id",
            sa.Text(),
            sa.Computed("app.bc_text(doc -> 'media_id')", persisted=True),
            nullable=True,
        ),
        schema="app",
    )
    op.create_index(
        "ix_media_libraries_workspace_media",
        "media_libraries",
        ["workspace_id", "media_id"],
        unique=False,
        schema="app",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_media_libraries_workspace_media", table_name="media_libraries", schema="app"
    )
    op.drop_column("media_libraries", "media_id", schema="app")
