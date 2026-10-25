"""A test-only routed group.

Every backend group is served from Postgres only since 4.1, so the application
has no routed repository left; the 4.0 -> 4.1 import tooling (backfill, verify,
reconcile, the outbox, the "migration verified" marker, ``--group``) is still
shipped and must stay covered. These tests run it against a Target for which
``responses`` (the last group to leave Mongo) is still a migrating group, whose
routed repositories are the frozen Mongo originals of
``tests/app/db/beanie_originals.py`` over the real Postgres ones.

Nothing here changes what the application does: the real ``build_target`` is
used with its Postgres-only set and flag loader replaced.
"""

from __future__ import annotations

import dataclasses
from typing import Mapping
from unittest import mock

from backend.db import groups
from backend.migrate.__main__ import build_target as real_build_target

#: the group the tests keep routed
ROUTED = "responses"
#: what the Target treats as served from Postgres only
POSTGRES_ONLY = tuple(g for g in groups.POSTGRES_ONLY_GROUPS if g != ROUTED)
#: the routed repositories of the test group (an outbox entry names the
#: repository, not the group)
ROUTED_REPOSITORIES = {
    "WorkspaceRespondersRepository": ROUTED,
    "ResponderGroupsRepository": ROUTED,
    "FormResponseRepository": ROUTED,
}
#: the groups the test Target verifies and the marker rests on
MIGRATING = [g for g in groups.GROUPS if g not in POSTGRES_ONLY]


def load_flags(env: Mapping[str, str]):
    """The backend's flag loader with ``responses`` left to the environment, as
    it was while that group was routed."""
    with mock.patch.object(groups, "POSTGRES_ONLY_GROUPS", POSTGRES_ONLY):
        return groups.load_backend_flags(env)


def build_target(database_url: str):
    """:func:`backend.migrate.__main__.build_target` with ``responses`` still
    migrating."""
    return dataclasses.replace(
        real_build_target(database_url),
        postgres_only_groups=POSTGRES_ONLY,
        load_flags=load_flags,
        repository_groups=lambda: dict(ROUTED_REPOSITORIES),
        retired_repositories={
            repository: group
            for repository, group in groups.RETIRED_REPOSITORIES.items()
            if group != ROUTED
        },
    )
