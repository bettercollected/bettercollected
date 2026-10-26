"""auth is served from Postgres only (4.1): it starts and serves without Mongo,
refuses to start on a stale ``DB_READ_SOURCE`` / ``DB_WRITE_MODE`` (or their
``__auth`` overrides) naming another store, and refuses to start without
DATABASE_URL.

The boots run the app factory in a fresh process, as a deployment does, with
MONGO_URI unset (a fresh install): the start never builds a Mongo client. A
MONGO_URI that is set but unreachable refuses the start, because Mongo may hold
4.0 data that was never imported (auth/db/import_guard.py;
tests/db/test_import_guard.py drives that check against a real Mongo).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from auth.db.flags import POSTGRES_ONLY, load_auth_flags
from common.db.flags import FlagError

SERVICE_DIR = Path(__file__).resolve().parents[1]
UNREACHABLE = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=1000"
NO_MONGO = ""
DB_KEYS = ("DB_READ_SOURCE", "DB_WRITE_MODE", "DB_SHADOW_READ_SAMPLE")

PROGRAM = """
import gc

from fastapi.testclient import TestClient
from pymongo import AsyncMongoClient, MongoClient

from auth.app import get_application
from auth.config import settings

with TestClient(get_application()) as client:
    ready = client.get(settings.API_ROOT_PATH + "/ready")
    assert ready.status_code == 200, ready.status_code
    print("ready")
    clients = [o for o in gc.get_objects() if isinstance(o, (AsyncMongoClient, MongoClient))]
    print("mongo clients:", len(clients))
"""


def boot(env_changes: dict, mongo_uri: str = NO_MONGO) -> subprocess.CompletedProcess:
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(k == key or k.startswith(key + "__") for key in DB_KEYS)
    }
    env.update(env_changes, MONGO_URI=mongo_uri)
    env = {k: v for k, v in env.items() if v is not None}
    return subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


# -- the flags -------------------------------------------------------------------
@pytest.mark.parametrize(
    "env",
    [
        {},
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"},
        {"DB_READ_SOURCE": "", "DB_WRITE_MODE__auth": " Postgres "},
        {"DB_READ_SOURCE__auth": "postgres", "DB_WRITE_MODE__AUTH": "postgres"},
        # another service's group, and shadow reads: no store of this service
        {"DB_READ_SOURCE__identity": "mongo", "DB_WRITE_MODE__google": "dual"},
        {"DB_SHADOW_READ_SAMPLE": "0.5"},
    ],
)
def test_auth_is_on_postgres(env):
    flags = load_auth_flags(env)
    assert flags == POSTGRES_ONLY
    assert flags.describe()["store"] == "postgres"


@pytest.mark.parametrize(
    "key, value",
    [
        ("DB_READ_SOURCE", "mongo"),
        ("DB_WRITE_MODE", "dual"),
        ("DB_WRITE_MODE", "postgres_primary_dual"),
        ("DB_READ_SOURCE__auth", "mongo"),
        ("DB_WRITE_MODE__auth", "dual"),
        ("DB_WRITE_MODE__AUTH", "postgres_primary_dual"),
        ("DB_WRITE_MODE__auth", "mongo"),
        ("DB_READ_SOURCE__Auth", "nonsense"),
    ],
)
def test_a_stale_flag_is_refused_naming_the_setting(key, value):
    with pytest.raises(FlagError) as refused:
        load_auth_flags({key: value})
    assert f"{key}={value!r}" in str(refused.value)
    assert "Postgres only since 4.1" in str(refused.value)


# -- the process -----------------------------------------------------------------
@pytest.mark.parametrize(
    "flags",
    [
        {},
        {
            "DB_READ_SOURCE": "postgres",
            "DB_WRITE_MODE": "postgres",
            "DB_SHADOW_READ_SAMPLE": "0.5",
        },
    ],
    ids=["no flags", "postgres flags"],
)
def test_starts_and_serves_without_mongo(_postgres_schema, flags):
    result = boot(flags)
    assert result.returncode == 0, result.stderr[-3000:]
    assert "ready" in result.stdout
    # nothing ever built a Mongo client
    assert "mongo clients: 0" in result.stdout


@pytest.mark.parametrize("key", ["DB_WRITE_MODE", "DB_WRITE_MODE__auth"])
def test_refuses_to_start_on_a_stale_flag(_postgres_schema, key):
    result = boot({key: "dual"})
    assert result.returncode != 0
    assert f"{key}='dual'" in result.stderr
    assert "ready" not in result.stdout


def test_refuses_to_start_without_a_database():
    result = boot({"DATABASE_URL": None})
    assert result.returncode != 0
    assert "DATABASE_URL is not set" in result.stderr


def test_a_set_but_unreachable_mongo_uri_refuses_the_start(_postgres_schema):
    """MONGO_URI set means Mongo may hold 4.0 accounts: the start cannot tell
    whether they were imported, so it refuses (fails closed)."""
    result = boot({}, mongo_uri=UNREACHABLE)
    assert result.returncode != 0
    assert "UnimportedMongoData" in result.stderr
    assert "MONGO_URI is set but Mongo could not be read" in result.stderr
    assert "ready" not in result.stdout
    assert "127.0.0.1" not in result.stderr.split("UnimportedMongoData")[-1]
