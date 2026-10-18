"""SQLAlchemy Core definitions of the ``admin`` schema.

The migrations in ``backend/admin/migrations`` are written by hand; a test
compares them with these definitions so the two cannot drift.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
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
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, TIMESTAMP, UUID

from common.db.base import NAMING_CONVENTION

SCHEMA = "admin"
metadata = MetaData(schema=SCHEMA, naming_convention=NAMING_CONVENTION)


def _ts(name: str, **kw) -> Column:
    return Column(name, TIMESTAMP(timezone=True), **kw)


def _uuid_pk() -> Column:
    return Column(
        "id",
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )


sessions = Table(
    "sessions",
    metadata,
    _uuid_pk(),
    Column("token_hash", LargeBinary, nullable=False),
    Column("email", Text, nullable=False),
    Column("mfa_state", Text, nullable=False, server_default="email_ok"),
    _ts("stepup_at"),
    _ts("created_at", nullable=False, server_default=text("now()")),
    _ts("last_seen_at", nullable=False, server_default=text("now()")),
    _ts("idle_expires_at", nullable=False),
    _ts("abs_expires_at", nullable=False),
    Column("ip", INET),
    Column("ua_hash", LargeBinary),
    _ts("revoked_at"),
    Column("revoked_reason", Text),
    Column("revoked_by", Text),
    CheckConstraint("mfa_state IN ('email_ok', 'mfa_ok')", name="mfa_state"),
    Index("uq_sessions_token_hash", "token_hash", unique=True),
    Index("ix_sessions_email", "email"),
)

signin_challenges = Table(
    "signin_challenges",
    metadata,
    _uuid_pk(),
    Column("email", Text),
    Column("code_hash", LargeBinary, nullable=False),
    Column("failed_attempts", Integer, nullable=False, server_default="0"),
    Column("ip", INET),
    _ts("created_at", nullable=False, server_default=text("now()")),
    _ts("expires_at", nullable=False),
    _ts("consumed_at"),
    Index("ix_signin_challenges_expires_at", "expires_at"),
)

attempts = Table(
    "attempts",
    metadata,
    Column("key", Text, nullable=False),
    _ts("window_start", nullable=False),
    Column("count", Integer, nullable=False, server_default="0"),
    PrimaryKeyConstraint("key", "window_start", name="pk_attempts"),
)

factors = Table(
    "factors",
    metadata,
    _uuid_pk(),
    Column("email", Text, nullable=False),
    Column("secret_blob", Text, nullable=False),
    Column("key_id", Text, nullable=False),
    _ts("confirmed_at"),
    Column("last_used_step", BigInteger),
    _ts("created_at", nullable=False, server_default=text("now()")),
    Index("ix_factors_email", "email"),
)

recovery_codes = Table(
    "recovery_codes",
    metadata,
    Column("code_hash", LargeBinary, primary_key=True),
    Column(
        "factor_id",
        UUID(as_uuid=True),
        ForeignKey(f"{SCHEMA}.factors.id", ondelete="CASCADE"),
        nullable=False,
    ),
    _ts("used_at"),
    _ts("created_at", nullable=False, server_default=text("now()")),
    Index("ix_recovery_codes_factor_id", "factor_id"),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("seq", BigInteger, Identity(always=True), primary_key=True),
    Column("id", UUID(as_uuid=True), nullable=False),
    _ts("at", nullable=False),
    Column("actor_kind", Text, nullable=False),
    Column("actor_email", Text),
    Column("session_id", UUID(as_uuid=True)),
    Column("ip", INET),
    Column("ua", Text),
    Column("action", Text, nullable=False),
    Column("target_type", Text),
    Column("target_id", Text),
    Column("outcome", Text, nullable=False),
    Column("before", JSONB),
    Column("after", JSONB),
    Column("detail", JSONB),
    Column("request_id", Text),
    Column("key_version", Integer, nullable=False, server_default="1"),
    Column("prev_hash", LargeBinary, nullable=False),
    Column("row_hash", LargeBinary, nullable=False),
    CheckConstraint(
        "actor_kind IN ('admin', 'cli', 'system', 'anonymous')", name="actor_kind"
    ),
    CheckConstraint(
        "length(prev_hash) = 32 AND length(row_hash) = 32", name="hash_lengths"
    ),
    Index("uq_audit_log_id", "id", unique=True),
    Index("uq_audit_log_row_hash", "row_hash", unique=True),
    # one successor per row: a fork (two rows claiming the same head) cannot commit
    Index("uq_audit_log_prev_hash", "prev_hash", unique=True),
    Index("ix_audit_log_at", "at"),
)

notifications = Table(
    "notifications",
    metadata,
    _uuid_pk(),
    _ts("created_at", nullable=False, server_default=text("now()")),
    Column("kind", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("audit_seq", BigInteger),
    Column("status", Text, nullable=False, server_default="pending"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    _ts("sent_at"),
    _ts("next_attempt_at", nullable=False, server_default=text("now()")),
    Column("last_error_code", Text),
    Column("dedupe_key", Text),
    Column(
        "delivered_to", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    ),
    CheckConstraint("kind ~ '^[a-z][a-z0-9_.]{0,63}$'", name="kind"),
    CheckConstraint("status IN ('pending', 'sent', 'failed')", name="status"),
    CheckConstraint("pg_column_size(payload) <= 4096", name="payload"),
    CheckConstraint(
        "last_error_code IS NULL OR last_error_code ~ '^[a-z][a-z0-9_]{0,31}$'",
        name="last_error_code",
    ),
    CheckConstraint(
        "dedupe_key IS NULL OR dedupe_key ~ '^[A-Za-z0-9_.:-]{1,128}$'", name="dedupe_key"
    ),
    CheckConstraint("cardinality(delivered_to) <= 50", name="delivered_to"),
    Index("ix_notifications_status_created_at", "status", "created_at"),
    Index("ix_notifications_status_next_attempt_at", "status", "next_attempt_at"),
    Index("ix_notifications_dedupe_key", "dedupe_key"),
)

setup_tokens = Table(
    "setup_tokens",
    metadata,
    _uuid_pk(),
    Column("token_mac", LargeBinary, nullable=False),
    Column("issued_by", Text, nullable=False),
    _ts("created_at", nullable=False, server_default=text("now()")),
    _ts("expires_at", nullable=False),
    _ts("consumed_at"),
    _ts("revoked_at"),
    _ts("locked_at"),
    Column("failed_attempts", Integer, nullable=False, server_default="0"),
    CheckConstraint("length(token_mac) = 32", name="token_mac"),
    Index(
        "uq_setup_tokens_active",
        text("(true)"),
        unique=True,
        postgresql_where=text(
            "consumed_at IS NULL AND revoked_at IS NULL AND locked_at IS NULL"
        ),
    ),
)
