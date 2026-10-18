"""SQLAlchemy Core definitions of the ``tasks`` schema (runner and admin side).

The revision (``0004_tasks_schema``) is written by hand; a test compares it with
these definitions so the two cannot drift. Constraints and triggers live in the
revision only.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

from common.db.base import NAMING_CONVENTION

SCHEMA = "tasks"
metadata = MetaData(schema=SCHEMA, naming_convention=NAMING_CONVENTION)


def _ts(name: str, **kw) -> Column:
    return Column(name, TIMESTAMP(timezone=True), **kw)


runs = Table(
    "runs",
    metadata,
    Column("id", UUID(as_uuid=True), nullable=False),
    Column("task", Text, nullable=False),
    Column("version", Integer, nullable=False),
    Column("params", JSONB, nullable=False),
    Column("params_hash", Text, nullable=False),
    Column("dry_run", Boolean, nullable=False),
    Column("requested_by", Text, nullable=False),
    _ts("requested_at", nullable=False),
    Column("nonce", Text, nullable=False),
    Column("resumes_run_id", UUID(as_uuid=True), ForeignKey("tasks.runs.id")),
    Column("request_sig", LargeBinary, nullable=False),
    Column("sig_version", Integer, server_default="1", nullable=False),
    _ts("created_at", nullable=False),
    Column("state", Text, server_default="queued", nullable=False),
    _ts("cancel_requested_at"),
    _ts("started_at"),
    _ts("finished_at"),
    _ts("heartbeat_at"),
    Column("runner_id", Text),
    Column("progress", JSONB),
    Column("result", JSONB),
    Column("refusal_code", Text),
    PrimaryKeyConstraint("id"),
    Index("ix_runs_state_created_at", "state", "created_at"),
    Index("ix_runs_task_params_hash", "task", "params_hash", "finished_at"),
)

run_events = Table(
    "run_events",
    metadata,
    Column("id", BigInteger, Identity(always=True), nullable=False),
    Column("run_id", UUID(as_uuid=True), ForeignKey("tasks.runs.id"), nullable=False),
    Column("seq", Integer, nullable=False),
    _ts("at", nullable=False),
    Column("code", Text, nullable=False),
    Column("counts", JSONB),
    Column("ids", JSONB),
    Column("error_class", Text),
    PrimaryKeyConstraint("id"),
    Index("uq_run_events_run_seq", "run_id", "seq", unique=True),
    Index("ix_run_events_at", "at"),
)

checkpoints = Table(
    "checkpoints",
    metadata,
    Column("id", BigInteger, Identity(always=True), nullable=False),
    Column("run_id", UUID(as_uuid=True), ForeignKey("tasks.runs.id"), nullable=False),
    _ts("at", nullable=False),
    Column("cursor", JSONB, nullable=False),
    PrimaryKeyConstraint("id"),
    Index("ix_checkpoints_run_id_id", "run_id", "id"),
)

locks = Table(
    "locks",
    metadata,
    Column("name", Text, nullable=False),
    Column("run_id", UUID(as_uuid=True), ForeignKey("tasks.runs.id"), nullable=False),
    Column("runner_id", Text, nullable=False),
    _ts("acquired_at", nullable=False),
    PrimaryKeyConstraint("name"),
    Index("ix_locks_run_id", "run_id"),
)
