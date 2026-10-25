"""auth's persistence flags: Postgres only since 4.1.

The service has one repository group, ``auth``, and it no longer has a Mongo
store: its data lives in the ``auth`` schema, and the 4.0 Mongo database is
read only by the import (``python -m auth.migrate``). The storage flags
therefore have one valid value. A flag left from the cutover that names
another store for this service (``DB_READ_SOURCE=mongo``,
``DB_WRITE_MODE__auth=dual`` ...) refuses the start, naming the setting: the
store it asks for is no longer there. Unset is fine. Overrides for other
services' groups and ``DB_SHADOW_READ_SAMPLE`` mean nothing here (no routing)
and are ignored. The Google integration applies the same rule
(``googleform/db/flags.py``).
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

#: The flags auth runs with.
POSTGRES_ONLY = DbFlags(
    default_read=ReadSource.POSTGRES, default_write=WriteMode.POSTGRES
)


def _applies(key: str) -> bool:
    """The service-wide flag, or the auth group's override."""
    for base in (READ_KEY, WRITE_KEY):
        if key == base:
            return True
        if key.startswith(base + OVERRIDE_SEP):
            return key[len(base + OVERRIDE_SEP) :].lower() == GROUP
    return False


def load_auth_flags(env: Mapping[str, str] = os.environ) -> DbFlags:
    """:data:`POSTGRES_ONLY`, or :class:`FlagError` naming each stale flag."""
    stale = sorted(
        f"{key}={value!r}"
        for key, value in env.items()
        if _applies(key) and value.strip().lower() not in ("", "postgres")
    )
    if stale:
        raise FlagError(
            f"{', '.join(stale)}: the auth service stores its data in Postgres "
            "only since 4.1 and has no Mongo store any more. Remove these "
            "settings (or set them to postgres) and restart."
        )
    return POSTGRES_ONLY
