"""Which data stores this process writes, as the settings heartbeat reports
them (``settings.service_state.write_stores``, admin revision 0018). Read from
the same variables as ``common.db.flags`` (kept free of it: ``common.settings``
imports no database code), never echoing a value."""

from __future__ import annotations

import os
from typing import Mapping

WRITE_KEY = "DB_WRITE_MODE"
_STORES = {
    "mongo": {"mongo"},
    "dual": {"mongo", "postgres"},
    "postgres_primary_dual": {"mongo", "postgres"},
    "postgres": {"postgres"},
}


def write_stores_report(env: Mapping[str, str] = os.environ) -> str:
    """``mongo``, ``postgres`` or ``mongo,postgres``: every store written for
    any group (``DB_WRITE_MODE``, default ``mongo``, and each
    ``DB_WRITE_MODE__<group>``); ``""`` when a value is not a write mode."""
    values = [env.get(WRITE_KEY) or "mongo"]
    values += [
        v for k, v in env.items() if k.startswith(WRITE_KEY + "__") and v != ""
    ]
    stores: set = set()
    for value in values:
        found = _STORES.get(value.strip().lower())
        if found is None:
            return ""
        stores |= found
    return ",".join(sorted(stores))
