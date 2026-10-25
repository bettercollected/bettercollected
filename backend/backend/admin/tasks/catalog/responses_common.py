"""Shared metadata of the responses data tasks."""

import enum


class StoreChoice(str, enum.Enum):
    """Which data stores a task covers. ``auto`` = every store the services
    still write (the runner's ``DB_WRITE_MODE`` / ``DB_WRITE_MODE__<group>``;
    unset, the services' default; Postgres for the groups served from Postgres
    only; ``write_mode_unknown`` for a value that is not a write mode), plus
    any other store the runner is configured for; ``both`` requires both."""

    auto = "auto"
    mongo = "mongo"
    postgres = "postgres"
    both = "both"


class Refusals(str, enum.Enum):
    store_not_configured = "store_not_configured"
    write_mode_unknown = "write_mode_unknown"
    store_unreachable = "store_unreachable"
    store_empty = "store_empty"
    keyset_missing = "keyset_missing"
    keyset_unreadable = "keyset_unreadable"
