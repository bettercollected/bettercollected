"""form webhooks, the action log and the webhook audit trail

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-31

Three new tables (``backend/app/services/webhooks``): a form's webhooks, one log
row per run of a form action (today the deliveries of a webhook; kept 30 days)
and the audit trail of changes to a form's webhooks. New tables only, so
expand-only. Written by hand in the shape autogenerate produces for a BaseRow
table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024"
down_revision: Union[str, None] = "0023"
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


def _create(table: str, spines: Sequence[str], *constraints) -> None:
    op.create_table(
        table,
        *[_spine(name) for name in spines],
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
    _create("form_webhooks", ("workspace_id", "form_id"))
    _index(
        "ix_app_form_webhooks_workspace_id",
        "form_webhooks",
        ["workspace_id", "form_id"],
    )
    _create(
        "action_logs",
        ("workspace_id", "form_id", "action_id", "response_id", "status"),
        sa.UniqueConstraint(
            "action_id", "response_id", name=op.f("uq_action_logs_action_id_response_id")
        ),
    )
    _index(
        "ix_app_action_logs_workspace_id",
        "action_logs",
        ["workspace_id", "form_id", "created_at"],
    )
    _index("ix_app_action_logs_status", "action_logs", ["status", "created_at"])
    _index("ix_app_action_logs_response_id", "action_logs", ["response_id"])
    _index("ix_app_action_logs_created_at", "action_logs", ["created_at"])
    _create("webhook_audit_entries", ("workspace_id", "form_id", "webhook_id"))
    _index(
        "ix_app_webhook_audit_entries_workspace_id",
        "webhook_audit_entries",
        ["workspace_id", "form_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_app_webhook_audit_entries_workspace_id"),
        table_name="webhook_audit_entries",
        schema=SCHEMA,
    )
    op.drop_table("webhook_audit_entries", schema=SCHEMA)
    for name in (
        "ix_app_action_logs_created_at",
        "ix_app_action_logs_response_id",
        "ix_app_action_logs_status",
        "ix_app_action_logs_workspace_id",
    ):
        op.drop_index(op.f(name), table_name="action_logs", schema=SCHEMA)
    op.drop_table("action_logs", schema=SCHEMA)
    op.drop_index(
        op.f("ix_app_form_webhooks_workspace_id"),
        table_name="form_webhooks",
        schema=SCHEMA,
    )
    op.drop_table("form_webhooks", schema=SCHEMA)
