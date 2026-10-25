"""The google group's storage flags: Postgres only, whatever the defaults;
a flag naming another store for this service refuses, naming the setting."""

import pytest

from common.db.flags import FlagError, ReadSource, WriteMode
from googleform.db.flags import load_google_flags


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"},
        {"DB_READ_SOURCE": "", "DB_WRITE_MODE__google": " Postgres "},
        {"DB_WRITE_MODE__GOOGLE": "postgres"},
        # another service's group, and shadow reads: no store of this service
        {"DB_READ_SOURCE__forms": "mongo", "DB_WRITE_MODE__auth": "dual"},
        {"DB_SHADOW_READ_SAMPLE": "0.5"},
    ],
)
def test_the_google_group_is_on_postgres(env):
    flags = load_google_flags(env)
    assert flags.read_source("google") is ReadSource.POSTGRES
    assert flags.write_mode("google") is WriteMode.POSTGRES
    assert not flags.uses_mongo(["google"])
    assert flags.requires_postgres()


@pytest.mark.parametrize(
    "env,named",
    [
        ({"DB_READ_SOURCE": "mongo"}, "DB_READ_SOURCE='mongo'"),
        ({"DB_WRITE_MODE": "dual"}, "DB_WRITE_MODE='dual'"),
        ({"DB_WRITE_MODE": "postgres_primary_dual"}, "DB_WRITE_MODE="),
        ({"DB_READ_SOURCE__google": "mongo"}, "DB_READ_SOURCE__google='mongo'"),
        ({"DB_WRITE_MODE__GOOGLE": "mongo"}, "DB_WRITE_MODE__GOOGLE='mongo'"),
        ({"DB_WRITE_MODE": "nonsense"}, "DB_WRITE_MODE='nonsense'"),
    ],
)
def test_a_stale_flag_refuses_naming_the_setting(env, named):
    with pytest.raises(FlagError) as error:
        load_google_flags(env)
    assert named in str(error.value)
    assert "Postgres only since 4.1" in str(error.value)
