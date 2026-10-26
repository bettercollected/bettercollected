import pytest

from common.db import JobsBackend, load_flags, refuse_stale_store_flags
from common.db.flags import FlagError, stale_store_flags


def test_defaults_put_every_job_on_the_postgres_queue():
    flags = load_flags({})
    assert flags.jobs_backend("delete_user") is JobsBackend.POSTGRES
    assert flags.jobs_default is JobsBackend.POSTGRES


def test_jobs_backend_per_job():
    flags = load_flags({"JOBS_BACKEND__run_action": "temporal"})
    assert flags.jobs_backend("delete_user") is JobsBackend.POSTGRES
    assert flags.jobs_backend("run_action") is JobsBackend.TEMPORAL
    assert flags.jobs_backend("RUN_ACTION") is JobsBackend.TEMPORAL
    assert (
        load_flags({"JOBS_BACKEND": "temporal"}).jobs_backend("anything")
        is JobsBackend.TEMPORAL
    )
    # an empty override falls back to the default
    assert (
        load_flags({"JOBS_BACKEND__run_action": ""}).jobs_backend("run_action")
        is JobsBackend.POSTGRES
    )


@pytest.mark.parametrize(
    "env",
    [{"JOBS_BACKEND": "celery"}, {"JOBS_BACKEND__delete_user": "celery"}],
)
def test_a_bad_jobs_value_fails_at_startup(env):
    with pytest.raises(FlagError, match="not one of"):
        load_flags(env)


def test_the_store_flags_of_the_cutover_mean_nothing_to_the_parser():
    """The jobs flags are all it reads: the store settings of the cutover are
    only ever *refused* (below), never interpreted."""
    flags = load_flags(
        {
            "DB_READ_SOURCE": "mongo",
            "DB_WRITE_MODE": "dual",
            "DB_SHADOW_READ_SAMPLE": "lots",
            "JOBS_BACKEND__delete_user": "temporal",
        }
    )
    assert flags.jobs_backend("delete_user") is JobsBackend.TEMPORAL


def test_describe_names_the_store_and_the_jobs():
    described = load_flags({"JOBS_BACKEND__run_action": "temporal"}).describe(
        ["delete_user"]
    )
    assert described == {
        "store": "postgres",
        "jobs_backend_default": "postgres",
        "jobs": {"delete_user": "postgres", "run_action": "temporal"},
    }


# -- stale store flags ------------------------------------------------------------
@pytest.mark.parametrize(
    "env",
    [
        {},
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"},
        {"DB_READ_SOURCE": " Postgres ", "DB_WRITE_MODE__forms": ""},
        {"DB_WRITE_MODE__other": "dual"},  # another group's override: not ours
        {"DB_SHADOW_READ_SAMPLE": "0.5"},  # read by nothing any more
    ],
)
def test_postgres_or_nothing_is_fine(env):
    assert stale_store_flags(env, ["forms"]) == []
    refuse_stale_store_flags(env, ["forms"], what="the forms group is Postgres.")


@pytest.mark.parametrize(
    "key, value",
    [
        ("DB_READ_SOURCE", "mongo"),
        ("DB_WRITE_MODE", "dual"),
        ("DB_WRITE_MODE", "postgres_primary_dual"),
        ("DB_WRITE_MODE", "nonsense"),
        ("DB_READ_SOURCE__forms", "mongo"),
        ("DB_WRITE_MODE__FORMS", "dual"),
    ],
)
def test_a_flag_asking_for_another_store_is_refused_naming_it(key, value):
    with pytest.raises(FlagError) as refused:
        refuse_stale_store_flags({key: value}, ["forms"], what="Postgres only.")
    message = str(refused.value)
    assert f"{key}={value!r}" in message and "Postgres only." in message
    assert "Remove these settings" in message


def test_the_service_wide_flags_can_be_left_out():
    """The backend ignores ``DB_READ_SOURCE`` / ``DB_WRITE_MODE`` (they mean
    nothing to it) and refuses only a group's own override."""
    env = {"DB_READ_SOURCE": "mongo", "DB_WRITE_MODE": "dual"}
    assert stale_store_flags(env, ["forms"], service_wide=False) == []
    env = {**env, "DB_WRITE_MODE__forms": "dual"}
    assert stale_store_flags(env, ["forms"], service_wide=False) == [
        "DB_WRITE_MODE__forms='dual'"
    ]


def test_every_stale_flag_is_listed_once_sorted():
    env = {"DB_WRITE_MODE": "dual", "DB_READ_SOURCE": "mongo"}
    assert stale_store_flags(env, []) == [
        "DB_READ_SOURCE='mongo'",
        "DB_WRITE_MODE='dual'",
    ]
