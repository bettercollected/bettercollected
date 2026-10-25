"""Shared metadata of the responses data tasks."""

import enum


class StoreChoice(str, enum.Enum):
    """Which data store a task covers. Postgres is the only store since 4.1:
    ``postgres`` (the default) and ``auto`` (kept so that parameters saved
    before 4.1 still validate) name it; ``mongo`` and ``both`` are refused with
    ``store_retired`` before anything connects. The 4.0 data in Mongo is only
    read by the import (``python -m backend.migrate``)."""

    auto = "auto"
    mongo = "mongo"
    postgres = "postgres"
    both = "both"


class Refusals(str, enum.Enum):
    store_not_configured = "store_not_configured"
    # the task was asked for Mongo (``mongo`` or ``both``): no task reads or
    # writes Mongo any more
    store_retired = "store_retired"
    store_unreachable = "store_unreachable"
    store_empty = "store_empty"
    keyset_missing = "keyset_missing"
    keyset_unreadable = "keyset_unreadable"
