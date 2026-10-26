"""The Google Forms service is served from Postgres only (since 4.1): it
starts and serves without Mongo whatever the defaults, and a storage flag left
from the cutover that names another store refuses the start, naming it
(googleform/db/flags.py).

Each case boots the app factory in a fresh process, as a deployment does, with
MONGO_URI unset (a fresh install): the start never builds a Mongo client. A
MONGO_URI that is set but unreachable refuses the start, because Mongo may hold
4.0 data that was never imported (googleform/db/import_guard.py;
tests/integration/test_import_guard.py drives that check against a real Mongo).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[2]
UNREACHABLE = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=1000"
NO_MONGO = ""
DB_KEYS = ("DB_READ_SOURCE", "DB_WRITE_MODE", "DB_SHADOW_READ_SAMPLE")

PROGRAM = """
from fastapi.testclient import TestClient

from googleform.app import get_application
from googleform.config import settings

with TestClient(get_application()) as client:
    # a write through the credential repository
    deleted = client.post(
        settings.API_ROOT_PATH + "/google/oauth/credentials/erase",
        json={"user_id": "nobody", "email": "nobody@example.com"},
    )
    print("credentials status:", deleted.status_code)
    import gc

    from pymongo import AsyncMongoClient

    print("mongo clients:", sum(isinstance(o, AsyncMongoClient) for o in gc.get_objects()))
"""


def boot(flags: dict, mongo_uri: str = NO_MONGO) -> subprocess.CompletedProcess:
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(k == key or k.startswith(key + "__") for key in DB_KEYS)
    }
    env.update(flags, MONGO_URI=mongo_uri)
    return subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.mark.parametrize(
    "flags",
    [
        {},  # the defaults
        {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"},
        {"DB_READ_SOURCE__google": "postgres", "DB_WRITE_MODE__GOOGLE": "postgres"},
        # other services' groups and shadow reads mean nothing here
        {"DB_READ_SOURCE__forms": "mongo", "DB_SHADOW_READ_SAMPLE": "0.5"},
    ],
)
def test_starts_and_serves_without_mongo(_postgres_schema, flags):
    result = boot(flags)
    assert result.returncode == 0, result.stderr[-3000:]
    assert "credentials status: 200" in result.stdout, result.stdout
    assert "mongo clients: 0" in result.stdout, result.stdout


@pytest.mark.parametrize(
    "flags,named",
    [
        ({"DB_READ_SOURCE": "mongo"}, "DB_READ_SOURCE='mongo'"),
        ({"DB_WRITE_MODE": "dual"}, "DB_WRITE_MODE='dual'"),
        (
            {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres_primary_dual"},
            "DB_WRITE_MODE='postgres_primary_dual'",
        ),
        (
            {"DB_READ_SOURCE__google": "mongo", "DB_WRITE_MODE__google": "dual"},
            "DB_READ_SOURCE__google='mongo', DB_WRITE_MODE__google='dual'",
        ),
    ],
)
def test_a_stale_store_flag_refuses_the_start(_postgres_schema, flags, named):
    result = boot(flags)
    assert result.returncode != 0
    assert named in result.stderr
    assert "Postgres only since 4.1" in result.stderr


def test_a_set_but_unreachable_mongo_uri_refuses_the_start(_postgres_schema):
    """MONGO_URI set means Mongo may hold 4.0 Google data: the start cannot
    tell whether it was imported, so it refuses (fails closed)."""
    result = boot({}, mongo_uri=UNREACHABLE)
    assert result.returncode != 0
    assert "UnimportedMongoData" in result.stderr
    assert "MONGO_URI is set but Mongo could not be read" in result.stderr
    assert "credentials status" not in result.stdout
    assert "127.0.0.1" not in result.stderr.split("UnimportedMongoData")[-1]
