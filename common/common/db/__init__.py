"""Postgres foundation shared by every Python service.

Introduced by the Postgres consolidation (plans/postgres-consolidation.md).
Services build their engine and sessions with :func:`make_engine` /
:func:`make_sessionmaker`, declare rows on a :func:`make_base` base with the
:class:`BaseRow` mixin, read the switching flags with :func:`load_flags`, and
record mirror-write failures with the outbox models. Nothing in here talks to
Mongo except the Mongo-side outbox document.
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
from common.db.flags import DbFlags, JobsBackend, ReadSource, WriteMode, load_flags
from common.db.spine import SpineColumns
from common.db.outbox import (
    MIRROR_OPS,
    MirrorWriteFailureDocument,
    MirrorWriteFailureMixin,
)

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
    "JobsBackend",
    "ReadSource",
    "WriteMode",
    "load_flags",
    "MIRROR_OPS",
    "MirrorWriteFailureDocument",
    "MirrorWriteFailureMixin",
]
