"""The parity harness of the dual run: each step runs on the Mongo repository
and its Postgres twin, and both must return the same (ids, timestamps and
write-result objects aside). Used by the ``test_*_parity.py`` modules of the
groups that still have both stores."""

from typing import Any

import pytest
from pymongo.results import DeleteResult, UpdateResult

from backend.app.container import container
from common.db.routing import normalise_result

VOLATILE = {"id", "_id", "created_at", "updated_at", "revision_id"}


def strip(value: Any) -> Any:
    # Mongo write results carry counts the callers ignore; the twins return the count.
    if isinstance(value, DeleteResult):
        return value.deleted_count
    if isinstance(value, UpdateResult):
        return value.matched_count
    value = normalise_result(value)
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


async def parity(mongo, postgres, steps):
    for name, args in steps:
        m = await getattr(mongo, name)(*args())
        p = await getattr(postgres, name)(*args())
        assert strip(m) == strip(p), f"{type(mongo).__name__}.{name} differs"


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()
