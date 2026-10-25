"""refdata, analytics, ai, actions and identity are served from Postgres only (4.1): the backend's
flags pin them there, a stale per-group flag refuses the start, and a fresh
store gets its reference data from ``python -m backend.seed_refdata``."""

import pytest

from backend.db.groups import MONGO_JOINS, POSTGRES_ONLY_GROUPS, load_backend_flags
from backend.seed_refdata import DEFAULT_ORIGINS, build_parser, run, seed_refdata
from common.db import ReadSource, WriteMode
from common.db.flags import FlagError


@pytest.mark.parametrize(
    "env",
    [
        {},
        {"DB_READ_SOURCE": "mongo", "DB_WRITE_MODE": "dual"},
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"},
        {"DB_READ_SOURCE__refdata": "postgres", "DB_WRITE_MODE__refdata": "postgres"},
        {"DB_WRITE_MODE__analytics": ""},
        {"DB_READ_SOURCE__ai": "postgres", "DB_WRITE_MODE__AI": "postgres"},
        {"DB_READ_SOURCE__Actions": "postgres", "DB_WRITE_MODE__actions": ""},
        {"DB_READ_SOURCE__identity": "postgres", "DB_WRITE_MODE__Identity": ""},
    ],
)
def test_the_groups_are_on_postgres_whatever_the_defaults(env):
    flags = load_backend_flags(env)
    for group in POSTGRES_ONLY_GROUPS:
        assert flags.read_source(group) is ReadSource.POSTGRES
        assert flags.write_mode(group) is WriteMode.POSTGRES
    assert flags.uses_mongo(POSTGRES_ONLY_GROUPS) is False
    assert flags.requires_postgres()


def test_the_other_groups_keep_their_flags():
    flags = load_backend_flags(
        {"DB_WRITE_MODE": "dual", "DB_READ_SOURCE__responses": "postgres"}
    )
    assert flags.write_mode("forms") is WriteMode.DUAL
    assert flags.read_source("forms") is ReadSource.MONGO
    assert flags.read_source("responses") is ReadSource.POSTGRES


def test_no_mongo_query_joins_into_a_postgres_only_group():
    """A ``$lookup`` into a group served from Postgres only would find nothing
    (its Mongo collections are no longer written). identity's join into
    workspace_actions went with the actions group (the workspace repository
    reads the action's copy through the actions repository), and forms' join
    into workspaces with the identity group (both template repositories read
    the origin workspace's title through the workspace repository)."""
    for group, joined in MONGO_JOINS.items():
        assert not set(joined) & set(POSTGRES_ONLY_GROUPS), group


def test_no_mongo_query_joins_into_identity():
    """The forms group's one join into identity (the workspace a template was
    imported from) is composed over the workspace repository, so identity is
    served from Postgres only while forms still reads Mongo."""
    assert all("identity" not in joined for joined in MONGO_JOINS.values())
    flags = load_backend_flags(
        {"DB_READ_SOURCE__identity": "postgres", "DB_WRITE_MODE__identity": "postgres"}
    )
    assert flags.read_source("forms") is ReadSource.MONGO
    assert flags.write_mode("identity") is WriteMode.POSTGRES


@pytest.mark.parametrize(
    "key, value",
    [
        ("DB_READ_SOURCE__refdata", "mongo"),
        ("DB_WRITE_MODE__refdata", "dual"),
        ("DB_WRITE_MODE__analytics", "postgres_primary_dual"),
        ("DB_READ_SOURCE__ANALYTICS", "mongo"),
        ("DB_WRITE_MODE__refdata", "nonsense"),
        ("DB_READ_SOURCE__ai", "mongo"),
        ("DB_WRITE_MODE__ai", "dual"),
        ("DB_READ_SOURCE__actions", "mongo"),
        ("DB_WRITE_MODE__ACTIONS", "postgres_primary_dual"),
        ("DB_READ_SOURCE__identity", "mongo"),
        ("DB_WRITE_MODE__IDENTITY", "dual"),
    ],
)
def test_a_stale_group_flag_refuses_the_start(key, value):
    with pytest.raises(FlagError) as refused:
        load_backend_flags({key: value})
    assert f"{key}={value!r}" in str(refused.value)
    assert "served from Postgres only" in str(refused.value)
    assert "the refdata, analytics, ai, actions and identity groups" in str(
        refused.value
    )


async def test_seeding_fills_empty_tables_once(clean_postgres):
    from backend.app.container import container

    origins, providers = container.allowed_origins_repo(), container.form_provider_repo()
    assert await seed_refdata(origins, providers) == {
        "allowed_origins": 3,
        "forms_plugin_configs": 1,
    }
    assert await origins.list_origins() == list(DEFAULT_ORIGINS)
    google = await providers.get("google")
    assert google.enabled is False
    assert google.auth_callback_url == (
        "http://integrations-googleform:8000/api/v1/google/oauth/callback"
    )
    # anything already there is left alone
    await origins.delete_by_origin("http://localhost:3001")
    assert await seed_refdata(origins, providers, google_enabled=True) == {
        "allowed_origins": 0,
        "forms_plugin_configs": 0,
    }
    assert len(await origins.list_origins()) == 2
    assert (await providers.get("google")).enabled is False


async def test_the_command_seeds_what_it_is_told(clean_postgres, monkeypatch):
    from backend.app.container import container

    # the command disposes of the engine it used; the suite's stays open
    monkeypatch.setattr("backend.db.startup.dispose_postgres", _no_dispose)
    args = build_parser().parse_args(
        ["--origin", "https://forms.example", "--google-enabled", "true"]
    )
    assert await run(args) == 0
    assert await container.allowed_origins_repo().list_origins() == [
        "https://forms.example"
    ]
    assert (await container.form_provider_repo().get("google")).enabled is True


async def _no_dispose(_container):
    return None
