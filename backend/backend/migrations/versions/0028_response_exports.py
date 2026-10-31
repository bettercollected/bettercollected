"""response exports: the audit entry of each export and the chunks of a job's file

Revision ID: 0028
Revises: 0025
Create Date: 2026-10-31

Two new tables (``backend/app/services/response_export``): one row per export of
a form's responses (who, when, how many rows, which columns and filters, the
state of its background job: no answer content) and the encrypted chunks of a
job's file, deleted 24 hours after it was built, when its requester deletes it, or
when responses of the form are deleted. New
tables only, so expand-only. Written by hand in the shape autogenerate produces
for a BaseRow table.

``down_revision`` is 0025, the head of develop when this was merged (0026 and 0027
belong to other branches that also revise 0025; whichever merges later is re-pointed).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0028"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"


def _spine(name: str, function: str = "bc_text", source: str = None, column: str = None, type_=None) -> sa.Column:
    return sa.Column(
        column or name,
        type_ or sa.Text(),
        sa.Computed(f"{SCHEMA}.{function}(doc -> '{source or name}')", persisted=True),
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


def _index(name: str, table: str, columns: Sequence[str]) -> None:
    op.create_index(op.f(name), table, list(columns), unique=False, schema=SCHEMA)


def upgrade() -> None:
    _create(
        "response_exports",
        [_spine(n) for n in ("workspace_id", "form_id", "actor_id", "status")],
    )
    _index(
        "ix_app_response_exports_workspace_id",
        "response_exports",
        ["workspace_id", "form_id", "created_at"],
    )
    _index(
        "ix_app_response_exports_actor_id",
        "response_exports",
        ["actor_id", "form_id", "created_at"],
    )
    _index("ix_app_response_exports_status", "response_exports", ["status", "created_at"])
    _index("ix_app_response_exports_form_id", "response_exports", ["form_id"])
    # one export in flight or waiting to be fetched per requester and form
    op.create_index(
        "uq_response_exports_one_open",
        "response_exports",
        ["workspace_id", "form_id", "actor_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status IN ('queued', 'running', 'ready')"),
    )
    _create(
        "response_export_chunks",
        [
            *(_spine(n) for n in ("export_id", "workspace_id", "form_id")),
            _spine(
                "chunk_index",
                function="bc_int",
                source="index",
                type_=sa.BigInteger(),
            ),
        ],
        sa.UniqueConstraint(
            "export_id",
            "chunk_index",
            name=op.f("uq_response_export_chunks_export_id_chunk_index"),
        ),
    )
    _index(
        "ix_app_response_export_chunks_workspace_id",
        "response_export_chunks",
        ["workspace_id", "form_id"],
    )
    _index("ix_app_response_export_chunks_form_id", "response_export_chunks", ["form_id"])


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_response_export_chunks_form_id"),
        table_name="response_export_chunks",
        schema=SCHEMA,
    )
    op.drop_index(
        op.f("ix_app_response_export_chunks_workspace_id"),
        table_name="response_export_chunks",
        schema=SCHEMA,
    )
    op.drop_table("response_export_chunks", schema=SCHEMA)
    op.drop_index("uq_response_exports_one_open", table_name="response_exports", schema=SCHEMA)
    for name in (
        "ix_app_response_exports_form_id",
        "ix_app_response_exports_status",
        "ix_app_response_exports_actor_id",
        "ix_app_response_exports_workspace_id",
    ):
        op.drop_index(op.f(name), table_name="response_exports", schema=SCHEMA)
    op.drop_table("response_exports", schema=SCHEMA)
