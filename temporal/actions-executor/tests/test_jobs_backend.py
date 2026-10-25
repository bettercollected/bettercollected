"""The actions executor takes its jobs from the Postgres queue unless told to
use Temporal, as the backend does (JOBS_BACKEND, default postgres)."""

import pytest

from main import jobs_backend, require_database_url


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


@pytest.mark.parametrize("env", [{}, {"DATABASE_URL": ""}, {"DATABASE_URL": "  "}])
def test_the_postgres_queue_refuses_to_start_without_a_database_url(env):
    """No restart loop on an empty connection string: the message names the
    setting and the way back to Temporal."""
    with pytest.raises(SystemExit) as stopped:
        require_database_url(env)
    message = str(stopped.value)
    assert "DATABASE_URL" in message and "JOBS_BACKEND=temporal" in message


def test_a_database_url_is_enough_and_is_never_echoed():
    secret = "postgresql://bc_jobs_exec:pw-never-shown@db/app"
    require_database_url({"DATABASE_URL": secret})
    with pytest.raises(SystemExit) as stopped:
        require_database_url({"DATABASE_URL": ""})
    assert "pw-never-shown" not in str(stopped.value)
