"""Repository groups per service: the unit the migration CLI acts on.

A group names the repositories (and so the tables) that moved from Mongo to
Postgres together during the 4.0 cutover (``DB_READ_SOURCE__<group>``,
``DB_WRITE_MODE__<group>``, which a 4.1 service only refuses to see set to
another store). The migration CLIs accept ``--group <g>`` to backfill, verify
or reconcile only the collections of those groups; each service declares which
group every one of its collections belongs to.
"""

from __future__ import annotations

from typing import Iterable, Mapping

BACKEND_GROUPS = (
    "refdata",
    "identity",
    "forms",
    "responses",
    "actions",
    "ai",
    "analytics",
)

#: service -> the repository groups it has (the names the flags and ``--group`` use)
SERVICE_GROUPS: Mapping[str, tuple[str, ...]] = {
    "backend": BACKEND_GROUPS,
    "auth": ("auth",),
    "google": ("google",),
}

#: service -> the Postgres schema holding its tables (and its verified marker)
SERVICE_SCHEMAS: Mapping[str, str] = {
    "backend": "app",
    "auth": "auth",
    "google": "google",
}


class UnknownGroup(ValueError):
    """A ``--group`` value the service does not have."""


def parse_groups(values: Iterable[str] | None) -> list[str]:
    """``--group a,b --group c`` -> ``["a", "b", "c"]`` (order kept, duplicates dropped)."""
    out: list[str] = []
    for value in values or ():
        for name in value.split(","):
            name = name.strip().lower()
            if name and name not in out:
                out.append(name)
    return out


def validate_groups(groups: Iterable[str], valid: Iterable[str]) -> list[str]:
    groups, valid = list(groups), list(valid)
    unknown = [g for g in groups if g not in valid]
    if unknown:
        raise UnknownGroup(
            f"unknown group(s): {', '.join(unknown)}; valid groups: {', '.join(valid)}"
        )
    return groups


def collections_of(
    collection_groups: Mapping[str, str], groups: Iterable[str]
) -> list[str]:
    """The collections belonging to ``groups``, in the map's order."""
    wanted = set(groups)
    return [c for c, g in collection_groups.items() if g in wanted]
