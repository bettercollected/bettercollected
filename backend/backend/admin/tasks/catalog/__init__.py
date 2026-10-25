"""The task catalog: metadata only, safe for the admin web process to import.

Test-only tasks (``internal``) are listed only when ``ADMIN_TASKS_SELFTEST=1``.
"""

from __future__ import annotations

import os
from typing import Mapping

from backend.admin.tasks.spec import TaskMeta

SELFTEST_FLAG = "ADMIN_TASKS_SELFTEST"


def selftest_enabled(env: Mapping[str, str] = os.environ) -> bool:
    return env.get(SELFTEST_FLAG) == "1"


def all_meta(env: Mapping[str, str] = os.environ) -> list[TaskMeta]:
    """Every task the build offers, in a stable order."""
    from backend.admin.tasks.catalog import (
        case_duplicates,
        google_purge,
        keyset,
        responses_backfill,
        responses_check,
    )

    metas: list[TaskMeta] = [
        responses_check.META,
        responses_backfill.META,
        *keyset.ALL,
        google_purge.META,
        case_duplicates.META,
    ]
    if selftest_enabled(env):
        from backend.admin.tasks.catalog import selftest, selftest_slow

        metas += [selftest.META, selftest_slow.META, selftest_slow.GUARDED_META]
    return metas
