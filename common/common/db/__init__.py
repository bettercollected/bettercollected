"""Postgres foundation shared by every Python service.

Services build their engine and sessions with :func:`make_engine` /
:func:`make_sessionmaker`, declare rows on a :func:`make_base` base with the
:class:`BaseRow` mixin, and read the jobs backend flags with :func:`load_flags`.
Postgres is the only store since 4.1; Mongo is read only by the import from
4.0 (:mod:`common.db.migrate`), which uses its own client.
"""

from common.db.base import BaseRow, NAMING_CONVENTION, OBJECT_ID_PATTERN, make_base
from common.db.ddl import (
    HELPER_FUNCTIONS,
    drop_helper_function_ddl,
    helper_function_ddl,
)
from common.db.canonical import (
    canonical_document,
    canonical_json,
    checksum,
    document_checksum,
    from_canonical_document,
)
from common.db.engine import DatabaseSettings, make_engine, make_sessionmaker, ping
from common.db.flags import (
    DbFlags,
    FlagError,
    JobsBackend,
    load_flags,
    refuse_stale_store_flags,
)
from common.db.runtime import (
    LazyRepository,
    build_engine,
    build_sessionmaker,
    check_postgres_at_startup,
    dispose_engine,
)
from common.db.schema_guard import (
    AUTO_MIGRATE_KEY,
    AuxiliarySchema,
    MigrationTarget,
    SchemaNotReady,
    auto_migrate_enabled,
    ensure_schema_ready,
)
from common.db.spine import SpineColumns
from common.db.groups import SERVICE_GROUPS, SERVICE_SCHEMAS
from common.db.marker import MarkerInfo, StoreMigrationMixin, migration_verified
from common.db.tombstones import DeletionTombstoneMixin
from common.db.outbox import MIRROR_OPS, MirrorWriteFailureMixin

__all__ = [
    "BaseRow",
    "NAMING_CONVENTION",
    "OBJECT_ID_PATTERN",
    "make_base",
    "canonical_document",
    "canonical_json",
    "checksum",
    "document_checksum",
    "from_canonical_document",
    "DatabaseSettings",
    "make_engine",
    "make_sessionmaker",
    "ping",
    "DbFlags",
    "FlagError",
    "JobsBackend",
    "load_flags",
    "refuse_stale_store_flags",
    "LazyRepository",
    "build_engine",
    "build_sessionmaker",
    "check_postgres_at_startup",
    "dispose_engine",
    "AUTO_MIGRATE_KEY",
    "AuxiliarySchema",
    "MigrationTarget",
    "SchemaNotReady",
    "auto_migrate_enabled",
    "ensure_schema_ready",
    "MIRROR_OPS",
    "MirrorWriteFailureMixin",
    "DeletionTombstoneMixin",
    "SERVICE_GROUPS",
    "SERVICE_SCHEMAS",
    "MarkerInfo",
    "StoreMigrationMixin",
    "migration_verified",
]
