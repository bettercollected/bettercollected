"""The google group is served from Postgres only (since 4.1).

The service has no Mongo store any more: its one repository is the Postgres
one, and Mongo is read only by the import from 4.0 (``python -m
googleform.migrate``). The storage flags therefore have one valid value. A
flag left from the cutover that names another store for this service refuses
the start, naming the setting: the store it asks for is no longer there.
"""

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
    load_flags,
)

GROUP = "google"


def _applies(key: str) -> bool:
    """The service-wide flag, or the google group's override."""
    for base in (READ_KEY, WRITE_KEY):
        if key == base:
            return True
        if key.startswith(base + OVERRIDE_SEP):
            return key[len(base + OVERRIDE_SEP) :].lower() == GROUP
    return False


def load_google_flags(env: Mapping[str, str] = os.environ) -> DbFlags:
    """Flags with the google group on Postgres; a stale store flag
    (``DB_READ_SOURCE=mongo``, ``DB_WRITE_MODE__google=dual`` ...) raises
    :class:`FlagError`. Overrides for other services' groups and
    ``DB_SHADOW_READ_SAMPLE`` mean nothing here (no routing) and are ignored."""
    stale = sorted(
        f"{key}={value!r}"
        for key, value in env.items()
        if _applies(key) and value.strip().lower() not in ("", "postgres")
    )
    if stale:
        raise FlagError(
            f"{', '.join(stale)}: the Google Forms integration stores its data "
            "in Postgres only since 4.1 and has no Mongo store any more. Remove "
            "these settings (or set them to postgres) and restart."
        )
    return load_flags(
        {READ_KEY: ReadSource.POSTGRES.value, WRITE_KEY: WriteMode.POSTGRES.value}
    )
