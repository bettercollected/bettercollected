"""The google group is served from Postgres only (since 4.1).

The service has no Mongo store any more: its one repository is the Postgres
one, and Mongo is read only by the import from 4.0 (``python -m
googleform.migrate``). The storage flags therefore have one valid value. A
flag left from the cutover that names another store for this service refuses
the start, naming the setting: the store it asks for is no longer there.
"""

import os
from typing import Mapping

from common.db.flags import DbFlags, load_flags, refuse_stale_store_flags

GROUP = "google"


def load_google_flags(env: Mapping[str, str] = os.environ) -> DbFlags:
    """The service's flags (it has no jobs); a stale store flag
    (``DB_READ_SOURCE=mongo``, ``DB_WRITE_MODE__google=dual`` ...) raises
    :class:`FlagError`. Overrides for other services' groups and
    ``DB_SHADOW_READ_SAMPLE`` mean nothing here (no routing) and are ignored."""
    refuse_stale_store_flags(
        env,
        (GROUP,),
        what="the Google Forms integration stores its data in Postgres only "
        "since 4.1 and has no Mongo store any more.",
    )
    return load_flags({})
