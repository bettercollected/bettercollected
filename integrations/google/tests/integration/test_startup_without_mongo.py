"""The Google Forms service is served from Postgres only (since 4.1): it
starts and serves without Mongo whatever the defaults, and a storage flag left
from the cutover that names another store refuses the start, naming it
(googleform/db/flags.py).

Each case boots the app factory in a fresh process, as a deployment does, with
MONGO_URI pointing at a closed port: a start that tried to reach Mongo would
fail within the URI's short server selection timeout.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SERVICE_DIR = Path(__file__).resolve().parents[2]
UNREACHABLE = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=1000"
DB_KEYS = ("DB_READ_SOURCE", "DB_WRITE_MODE", "DB_SHADOW_READ_SAMPLE")

PROGRAM = """
from fastapi.testclient import TestClient

from googleform.app import get_application
from googleform.app.services import database_service
from googleform.config import settings

with TestClient(get_application()) as client:
    # a write through the credential repository
    deleted = client.post(
        settings.API_ROOT_PATH + "/google/oauth/credentials/erase",
        json={"user_id": "nobody", "email": "nobody@example.com"},
    )
    print("credentials status:", deleted.status_code)
    print("mongo used:", database_service.uses_mongo())
    print("mongo hosts:", sorted(database_service._client.topology_description.server_descriptions()))
"""


def boot(flags: dict) -> subprocess.CompletedProcess:
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(k == key or k.startswith(key + "__") for key in DB_KEYS)
    }
    env.update(flags, MONGO_URI=UNREACHABLE)
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
    assert "mongo used: False" in result.stdout
    assert "mongo-not-used.invalid" in result.stdout


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
