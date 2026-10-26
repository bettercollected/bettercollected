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

from common.db.flags import DbFlags, refuse_stale_store_flags

GROUP = "auth"

#: The flags auth runs with (it has no jobs).
POSTGRES_ONLY = DbFlags()


def load_auth_flags(env: Mapping[str, str] = os.environ) -> DbFlags:
    """:data:`POSTGRES_ONLY`, or :class:`FlagError` naming each stale flag."""
    refuse_stale_store_flags(
        env,
        (GROUP,),
        what="the auth service stores its data in Postgres only since 4.1 and "
        "has no Mongo store any more.",
    )
    return POSTGRES_ONLY
