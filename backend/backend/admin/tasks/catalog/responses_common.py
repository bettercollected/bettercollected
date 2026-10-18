"""Shared metadata of the responses data tasks."""

import enum


class StoreChoice(str, enum.Enum):
    """Which data stores a responses task covers. ``auto`` = every store the
    runner is configured for; ``both`` requires both."""

    auto = "auto"
    mongo = "mongo"
    postgres = "postgres"
    both = "both"


class Refusals(str, enum.Enum):
    store_not_configured = "store_not_configured"
    store_unreachable = "store_unreachable"
    store_empty = "store_empty"
    keyset_missing = "keyset_missing"
    keyset_unreadable = "keyset_unreadable"
