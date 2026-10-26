"""Which data stores this process writes, as the settings heartbeat reports
them (``settings.service_state.write_stores``, admin revision 0018).

Since 4.1 every service writes Postgres alone: nothing in the application
connects to Mongo any more, whatever ``DB_WRITE_MODE`` (a setting left from the
cutover, which a service only refuses or ignores) says or leaves unset. So the
report is constant. The admin keyset task ``drop_old`` still reads it from every
live instance to catch a 4.0 instance that has not been replaced yet: those
report ``mongo`` or ``mongo,postgres`` themselves."""

from __future__ import annotations

import os
from typing import Mapping


def write_stores_report(env: Mapping[str, str] = os.environ) -> str:
    """``postgres``: the only store a 4.1 process writes (``env`` is accepted
    for the callers that pass one, and never read)."""
    return "postgres"
