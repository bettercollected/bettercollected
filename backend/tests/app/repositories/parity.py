"""Helpers of the repository tests: a result shaped for comparison (``strip``)
and the Postgres sessions fixture. (The parity harness of the dual run, which
ran each step on the Mongo repository and its Postgres twin, went with the
Mongo repositories.)"""

from typing import Any

import pytest
from pydantic import BaseModel
from pymongo.results import DeleteResult, UpdateResult

from backend.app.container import container

VOLATILE = {"id", "_id", "created_at", "updated_at", "revision_id"}


def normalise_result(value: Any) -> Any:
    """Shape a repository result for comparison: models to plain JSON data."""
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): normalise_result(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalise_result(v) for v in value]
    return value


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


@pytest.fixture
def sessions(clean_postgres):
    return container.pg_sessionmaker()
