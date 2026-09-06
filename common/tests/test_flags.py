import random

import pytest

from common.db import JobsBackend, ReadSource, WriteMode, load_flags
from common.db.flags import FlagError, FlagError


def test_defaults_are_todays_behaviour():
    flags = load_flags({})
    assert flags.read_source("forms") is ReadSource.MONGO
    assert flags.write_mode("forms") is WriteMode.MONGO
    assert flags.primary_store("forms") is ReadSource.MONGO
    assert flags.mirror_store("forms") is None
    assert flags.jobs_backend("delete_user") is JobsBackend.TEMPORAL
    assert flags.shadow_read_sample == 0.0
    assert flags.requires_postgres() is False


def test_dual_write_mirrors_to_postgres():
    flags = load_flags({"DB_WRITE_MODE": "dual"})
    assert flags.primary_store("forms") is ReadSource.MONGO
    assert flags.mirror_store("forms") is ReadSource.POSTGRES
    assert flags.writes_mongo("forms") and flags.writes_postgres("forms")
    assert flags.requires_postgres() is True


def test_per_group_overrides_and_case_insensitivity():
    flags = load_flags(
        {
            "DB_WRITE_MODE": "dual",
            "DB_READ_SOURCE__Responses": "postgres",
            "DB_WRITE_MODE__responses": "postgres_primary_dual",
        }
    )
    assert flags.read_source("responses") is ReadSource.POSTGRES
    assert flags.read_source("RESPONSES") is ReadSource.POSTGRES
    assert flags.read_source("forms") is ReadSource.MONGO
    assert flags.primary_store("responses") is ReadSource.POSTGRES
    assert flags.mirror_store("responses") is ReadSource.MONGO
    assert flags.mirror_store("forms") is ReadSource.POSTGRES


def test_postgres_only_writes_nothing_to_mongo():
    flags = load_flags({"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"})
    assert flags.writes_mongo("forms") is False
    assert flags.mirror_store("forms") is None


@pytest.mark.parametrize(
    "env",
    [
        {"DB_READ_SOURCE": "postgres"},  # reading a store nothing writes to
        {"DB_READ_SOURCE": "mongo", "DB_WRITE_MODE": "postgres"},
        {
            "DB_WRITE_MODE": "dual",
            "DB_READ_SOURCE__forms": "postgres",
            "DB_WRITE_MODE__forms": "mongo",
        },
    ],
)
def test_reading_an_unwritten_store_is_rejected(env):
    with pytest.raises(FlagError, match="nothing writes to"):
        load_flags(env)


@pytest.mark.parametrize(
    "env, message",
    [
        ({"DB_READ_SOURCE": "maria"}, "not one of"),
        ({"DB_WRITE_MODE__forms": "sometimes"}, "not one of"),
        ({"JOBS_BACKEND__delete_user": "celery"}, "not one of"),
        ({"DB_SHADOW_READ_SAMPLE": "1.5"}, "between 0 and 1"),
        ({"DB_SHADOW_READ_SAMPLE": "lots"}, "not a number"),
    ],
)
def test_bad_values_fail_at_startup(env, message):
    with pytest.raises(FlagError, match=message):
        load_flags(env)


def test_empty_values_fall_back_to_defaults():
    flags = load_flags(
        {"DB_READ_SOURCE": "", "DB_WRITE_MODE": "", "DB_READ_SOURCE__forms": ""}
    )
    assert flags.read_source("forms") is ReadSource.MONGO


def test_shadow_read_sampling():
    flags = load_flags({"DB_WRITE_MODE": "dual", "DB_SHADOW_READ_SAMPLE": "0.25"})
    rng = random.Random(42)
    hits = sum(flags.should_shadow_read(rng) for _ in range(10_000))
    assert 2_200 < hits < 2_800
    assert load_flags({}).should_shadow_read(rng) is False


def test_jobs_backend_per_job():
    flags = load_flags({"JOBS_BACKEND__delete_user": "postgres"})
    assert flags.jobs_backend("delete_user") is JobsBackend.POSTGRES
    assert flags.jobs_backend("DELETE_USER") is JobsBackend.POSTGRES
    assert flags.jobs_backend("run_action") is JobsBackend.TEMPORAL
    assert flags.requires_postgres() is True
    assert (
        load_flags({"JOBS_BACKEND": "postgres"}).jobs_backend("anything")
        is JobsBackend.POSTGRES
    )


def test_serves_from_postgres_distinguishes_mirror_only_from_serving():
    assert load_flags({}).serves_from_postgres() is False
    assert (
        load_flags({"DB_WRITE_MODE": "dual"}).serves_from_postgres() is False
    )  # mirror only
    assert (
        load_flags({"DB_WRITE_MODE__refdata": "dual"}).serves_from_postgres() is False
    )
    assert (
        load_flags(
            {"DB_READ_SOURCE__refdata": "postgres", "DB_WRITE_MODE__refdata": "dual"}
        ).serves_from_postgres()
        is True
    )
    assert (
        load_flags({"DB_WRITE_MODE": "postgres_primary_dual"}).serves_from_postgres()
        is True
    )


def test_read_dependencies_enforce_cutover_order():
    deps = {"forms": ["responses"]}
    # responses still on mongo: forms may mirror but not serve
    load_flags({"DB_WRITE_MODE__forms": "dual"}, deps)
    with pytest.raises(FlagError, match="'responses' still read from mongo"):
        load_flags(
            {"DB_READ_SOURCE__forms": "postgres", "DB_WRITE_MODE__forms": "postgres"},
            deps,
        )
    # together, or responses first, is fine
    load_flags(
        {
            "DB_READ_SOURCE__forms": "postgres",
            "DB_WRITE_MODE__forms": "postgres",
            "DB_READ_SOURCE__responses": "postgres",
            "DB_WRITE_MODE__responses": "postgres",
        },
        deps,
    )
    load_flags({"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"}, deps)
