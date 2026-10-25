"""The actions executor takes its jobs from the Postgres queue unless told to
use Temporal, as the backend does (JOBS_BACKEND, default postgres)."""

import pytest

from main import jobs_backend


@pytest.mark.parametrize("value", [None, "", "postgres", "POSTGRES"])
def test_postgres_is_the_default(value):
    env = {} if value is None else {"JOBS_BACKEND": value}
    assert jobs_backend(env) == "postgres"


@pytest.mark.parametrize("value", ["temporal", " Temporal "])
def test_temporal_is_kept_on_request(value):
    assert jobs_backend({"JOBS_BACKEND": value}) == "temporal"


def test_another_value_refuses_to_start():
    with pytest.raises(SystemExit):
        jobs_backend({"JOBS_BACKEND": "redis"})
