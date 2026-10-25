"""Every backend group (refdata, analytics, ai, actions, identity, forms and
responses) is served from Postgres only (4.1): the backend's
flags pin them there, a stale per-group flag refuses the start, and a fresh
store gets its reference data from ``python -m backend.seed_refdata``."""

import pytest

from backend.db.groups import (
    GROUPS,
    MONGO_JOINS,
    POSTGRES_ONLY_GROUPS,
    load_backend_flags,
)
from backend.seed_refdata import (
    DEFAULT_ORIGINS,
    build_parser,
    default_origins,
    run,
    seed_refdata,
)
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
        {"DB_READ_SOURCE__forms": "postgres", "DB_WRITE_MODE__FORMS": "postgres"},
        {"DB_READ_SOURCE__responses": "postgres", "DB_WRITE_MODE__Responses": ""},
    ],
)
def test_the_groups_are_on_postgres_whatever_the_defaults(env):
    flags = load_backend_flags(env)
    for group in POSTGRES_ONLY_GROUPS:
        assert flags.read_source(group) is ReadSource.POSTGRES
        assert flags.write_mode(group) is WriteMode.POSTGRES
    assert flags.uses_mongo(POSTGRES_ONLY_GROUPS) is False
    assert flags.requires_postgres()


def test_no_group_is_left_to_route():
    assert set(POSTGRES_ONLY_GROUPS) == set(GROUPS)
    flags = load_backend_flags({"DB_WRITE_MODE": "dual", "DB_READ_SOURCE": "mongo"})
    assert flags.uses_mongo(GROUPS) is False


def test_no_mongo_query_joins_across_groups():
    """A ``$lookup`` into a group served from Postgres only would find nothing
    (its Mongo collections are no longer written). The last ones went with
    the forms group: the responses repositories read a form's title and
    importer through the forms repositories, and the forms repositories read
    responses and responder groups through the responses group's. With the
    responses group on Postgres too no group has a Mongo store."""
    assert MONGO_JOINS == {}


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
        ("DB_READ_SOURCE__forms", "mongo"),
        ("DB_WRITE_MODE__Forms", "dual"),
        ("DB_READ_SOURCE__responses", "mongo"),
        ("DB_WRITE_MODE__Responses", "postgres_primary_dual"),
    ],
)
def test_a_stale_group_flag_refuses_the_start(key, value):
    with pytest.raises(FlagError) as refused:
        load_backend_flags({key: value})
    assert f"{key}={value!r}" in str(refused.value)
    assert "served from Postgres only" in str(refused.value)
    assert (
        "the refdata, analytics, ai, actions, identity, forms and responses groups"
        in str(refused.value)
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


@pytest.mark.parametrize(
    "client_url",
    ["http://localhost:3000", "http://127.0.0.1:3000/", "http://[::1]:3000", "", "nonsense"],
)
def test_a_local_client_url_gets_the_local_origins(client_url):
    assert default_origins(client_url) == DEFAULT_ORIGINS


@pytest.mark.parametrize(
    "client_url, origin",
    [
        ("https://admin.forms.example/", "https://admin.forms.example"),
        ("https://Admin.Forms.Example:443/workspace", "https://admin.forms.example"),
        ("http://10.0.0.5:3000", "http://10.0.0.5:3000"),
        ("https://localhost.forms.example", "https://localhost.forms.example"),
    ],
)
def test_a_public_client_url_never_gets_localhost_origins(client_url, origin):
    assert default_origins(client_url) == (origin,)


def test_origins_are_stored_the_way_browsers_send_them():
    args = build_parser().parse_args(
        ["--origin", "HTTPS://Forms.Example:443/", "--origin", "http://x.example:8080"]
    )
    assert args.origins == ["https://forms.example", "http://x.example:8080"]


@pytest.mark.parametrize(
    "value",
    [
        "forms.example",
        "*",
        "https://forms.example/app",
        "https://forms.example/?a=1",
        "https://user@forms.example",
        "ftp://forms.example",
        "https://",
    ],
)
def test_anything_but_an_origin_is_refused(value, capsys):
    with pytest.raises(SystemExit) as refused:
        build_parser().parse_args(["--origin", value])
    assert refused.value.code == 2
    assert "expected an origin" in capsys.readouterr().err


async def test_without_origins_a_public_stack_gets_its_client_origin(
    clean_postgres, monkeypatch
):
    from backend.app.container import container
    from backend.config import settings

    monkeypatch.setattr("backend.db.startup.dispose_postgres", _no_dispose)
    monkeypatch.setattr(
        settings.api_settings, "CLIENT_URL", "https://admin.forms.example"
    )
    assert await run(build_parser().parse_args([])) == 0
    origins = await container.allowed_origins_repo().list_origins()
    assert origins == ["https://admin.forms.example"]
    assert not any("localhost" in origin for origin in origins)


async def test_the_same_origin_twice_is_stored_once(clean_postgres):
    from backend.app.container import container

    origins, providers = container.allowed_origins_repo(), container.form_provider_repo()
    seeded = await seed_refdata(
        origins,
        providers,
        origins=["https://forms.example", "https://admin.example", "https://forms.example"],
    )
    assert seeded["allowed_origins"] == 2
    assert await origins.list_origins() == ["https://forms.example", "https://admin.example"]


async def _no_dispose(_container):
    return None


async def test_the_command_refuses_while_mongo_holds_unimported_refdata(
    clean_postgres, monkeypatch
):
    """Seeding the empty tables first would hide 4.0 refdata from the start's
    check (backend/db/mongo_import_guard.py): the command refuses instead."""
    from backend.app.container import container
    from backend.db import mongo_import_guard as guard

    class Collection:
        def __init__(self, name):
            self.name = name

        async def find_one(self, *args, **kwargs):
            return {"_id": 1} if self.name == "allowed_origins" else None

        async def estimated_document_count(self):
            return 5

    class Database:
        def __getitem__(self, name):
            return Collection(name)

    class Client:
        def __init__(self, uri, **kwargs):
            pass

        def __getitem__(self, name):
            return Database()

        async def close(self):
            return None

    monkeypatch.setattr("backend.db.startup.dispose_postgres", _no_dispose)
    monkeypatch.setattr(guard, "mongo_uri_configured", lambda _: "mongodb://mongo")
    monkeypatch.setattr(guard, "AsyncMongoClient", Client)
    assert await run(build_parser().parse_args([])) == 2
    assert await container.allowed_origins_repo().list_origins() == []
