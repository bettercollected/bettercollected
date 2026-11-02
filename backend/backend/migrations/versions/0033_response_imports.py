"""response imports: the audit entry and job state of each CSV import and the uploaded file

Revision ID: 0033
Revises: 0031
Create Date: 2026-11-01

Two new tables (``backend/app/services/response_import``): one row per import of
submissions from a CSV file (who, when, how many rows, the mapping as positions
and keys, the state of its job, the problems as row/column/code: no answer, no
header, no file name) and the encrypted upload, deleted when the job ends and at
the latest an hour after it was uploaded. New tables only, so expand-only.
Written by hand in the shape autogenerate produces for a BaseRow table. The
marker on an imported response (``csv_import_id``) is a field of the response
document: no column and no change to ``form_responses``.

The number is provisional: ``down_revision`` is 0031, the head of develop when
this was written; whichever revision merges after this one is re-pointed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SCHEMA = "app"


def _spine(name: str) -> sa.Column:
    return sa.Column(
        name,
        sa.Text(),
        sa.Computed(f"{SCHEMA}.bc_text(doc -> '{name}')", persisted=True),
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
        "response_imports",
        [_spine(n) for n in ("workspace_id", "form_id", "actor_id", "status")],
    )
    _index(
        "ix_app_response_imports_workspace_id",
        "response_imports",
        ["workspace_id", "form_id", "created_at"],
    )
    _index("ix_app_response_imports_status", "response_imports", ["status", "created_at"])
    _index("ix_app_response_imports_form_id", "response_imports", ["form_id"])
    # one import being checked, queued or run per form
    op.create_index(
        "uq_response_imports_one_busy",
        "response_imports",
        ["workspace_id", "form_id"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status IN ('checking', 'queued', 'running')"),
    )
    _create(
        "response_import_files",
        [_spine(n) for n in ("import_id", "workspace_id", "form_id")],
        sa.UniqueConstraint("import_id", name=op.f("uq_response_import_files_import_id")),
    )
    _index(
        "ix_app_response_import_files_workspace_id",
        "response_import_files",
        ["workspace_id", "form_id"],
    )
    _index("ix_app_response_import_files_form_id", "response_import_files", ["form_id"])


def downgrade() -> None:
    for name in (
        "ix_app_response_import_files_form_id",
        "ix_app_response_import_files_workspace_id",
    ):
        op.drop_index(op.f(name), table_name="response_import_files", schema=SCHEMA)
    op.drop_table("response_import_files", schema=SCHEMA)
    op.drop_index("uq_response_imports_one_busy", table_name="response_imports", schema=SCHEMA)
    for name in (
        "ix_app_response_imports_form_id",
        "ix_app_response_imports_status",
        "ix_app_response_imports_workspace_id",
    ):
        op.drop_index(op.f(name), table_name="response_imports", schema=SCHEMA)
    op.drop_table("response_imports", schema=SCHEMA)
