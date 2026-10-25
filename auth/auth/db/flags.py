"""auth's persistence flags: Postgres only since 4.1.

The service has one repository group, ``auth``, and it no longer has a Mongo
store: its data lives in the ``auth`` schema, and the 4.0 Mongo database is
read only by the import (``python -m auth.migrate``).

* The global ``DB_READ_SOURCE`` / ``DB_WRITE_MODE`` / ``DB_SHADOW_READ_SAMPLE``
  are ignored here: deployments share one env file between the backend and
  auth, and the backend's groups that are still moving read them.
* A per-group flag left from the cutover that names another store
  (``DB_READ_SOURCE__auth=mongo``, ``DB_WRITE_MODE__auth=dual`` ...) refuses
  the start, naming the setting: the store it asks for is not there any more.
"""

from __future__ import annotations

import os
from typing import Mapping

from common.db.flags import (
    OVERRIDE_SEP,
    READ_KEY,
    WRITE_KEY,
    DbFlags,
    FlagError,
    ReadSource,
    WriteMode,
)

GROUP = "auth"

#: The flags auth runs with, whatever the environment says.
POSTGRES_ONLY = DbFlags(
    default_read=ReadSource.POSTGRES, default_write=WriteMode.POSTGRES
)


def load_auth_flags(env: Mapping[str, str] = os.environ) -> DbFlags:
    """:data:`POSTGRES_ONLY`, or :class:`FlagError` for a stale per-group flag."""
    stale = sorted(
        f"{key}={value!r}"
        for key, value in env.items()
        if any(
            key.startswith(base + OVERRIDE_SEP)
            and key.split(OVERRIDE_SEP, 1)[1].lower() == GROUP
            for base in (READ_KEY, WRITE_KEY)
        )
        and value.strip().lower() not in ("", "postgres")
    )
    if stale:
        raise FlagError(
            f"{', '.join(stale)}: the auth service is served from Postgres only "
            "since 4.1 and has no Mongo store any more. Remove these settings "
            "(or set them to postgres) and restart."
        )
    return POSTGRES_ONLY
