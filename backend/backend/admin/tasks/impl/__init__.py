"""Task implementations. Imported by the runner only, never by the admin web
process (an AST test enforces it)."""

from __future__ import annotations

import os
from typing import Mapping

from backend.admin.tasks.catalog import selftest_enabled
from backend.admin.tasks.registry import Registry


def load(registry: Registry, env: Mapping[str, str] = os.environ) -> Registry:
    """Register every implementation this build offers."""
    from backend.admin.tasks.impl.responses_backfill_task import BackfillWorkspaces
    from backend.admin.tasks.impl.keyset_tasks import TASKS as KEYSET_TASKS
    from backend.admin.tasks.impl.responses_check import CheckUndecryptable
    from backend.admin.tasks.impl.responses_purge_task import PurgeOrphanedForms

    for cls in (CheckUndecryptable, BackfillWorkspaces, PurgeOrphanedForms, *KEYSET_TASKS):
        registry.register(cls.META, cls())
    if selftest_enabled(env):
        from backend.admin.tasks.impl.selftest import SelfTest
        from backend.admin.tasks.impl.selftest_slow import SelfTestGuarded, SelfTestSlow

        for cls in (SelfTest, SelfTestSlow, SelfTestGuarded):
            registry.register(cls.META, cls())
    return registry


def build_registry(env: Mapping[str, str] = os.environ) -> Registry:
    return load(Registry(), env)
