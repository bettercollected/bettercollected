"""The backend API and its job worker start and serve without Mongo once every
repository group is on Postgres (common/db/mongo.py), and still refuse to start
on an unreachable Mongo while any group uses it.

Each case boots the real entry point in a fresh process, as a deployment does,
with MONGO_URI pointing at a closed port: a start that tried to reach Mongo
would fail within the URI's short server selection timeout. The processes use
this worker's Postgres database, migrated by the session fixture.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import _postgres_configured

BACKEND_DIR = Path(__file__).resolve().parents[2]
UNREACHABLE = "mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=1000"
DB_KEYS = ("DB_READ_SOURCE", "DB_WRITE_MODE", "DB_SHADOW_READ_SAMPLE", "JOBS_BACKEND")
ALL_POSTGRES = {"DB_READ_SOURCE": "postgres", "DB_WRITE_MODE": "postgres"}

API = """
from fastapi.testclient import TestClient

from backend.app import get_application
from backend.app.container import container
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser

token = access_token(testUser)
with TestClient(get_application()) as client:
    status = client.get(
        "/api/v1/persistence/status",
        cookies={"Authorization": token, "RefreshToken": token},
    )
    assert status.status_code == 200, status.status_code
    body = status.json()
    print("mongo:", body["mongo"])
    print("outbox mongo:", body["outbox"]["mongo"])
    print("mongo hosts:", sorted(container.database_client().topology_description.server_descriptions()))
"""

WORKER = """
import asyncio

from backend.app.container import container
from backend.jobs import worker


async def run_worker_async(**kwargs):
    print("worker ran:", kwargs["queues"])


worker.app.run_worker_async = run_worker_async
asyncio.run(worker.main())
print("mongo hosts:", sorted(container.database_client().topology_description.server_descriptions()))
"""

pytestmark = pytest.mark.skipif(
    not _postgres_configured(), reason="DATABASE_URL not set to a *_test database"
)


def boot(program: str, flags: dict) -> subprocess.CompletedProcess:
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(k == key or k.startswith(key + "__") for key in DB_KEYS)
    }
    env.update(flags, MONGO_URI=UNREACHABLE, DB_AUTO_MIGRATE="false")
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=240,
    )


def test_the_api_starts_and_serves_without_mongo_when_every_group_is_on_postgres():
    result = boot(API, ALL_POSTGRES)
    assert result.returncode == 0, result.stderr[-3000:]
    assert "mongo: {'used': False, 'status': 'not used'}" in result.stdout
    assert "outbox mongo: None" in result.stdout
    assert "mongo-not-used.invalid" in result.stdout


def test_the_job_worker_starts_without_mongo_when_every_group_is_on_postgres():
    result = boot(WORKER, ALL_POSTGRES)
    assert result.returncode == 0, result.stderr[-3000:]
    assert "worker ran: ['default']" in result.stdout
    assert "mongo-not-used.invalid" in result.stdout


@pytest.mark.parametrize("program", [API, WORKER], ids=["api", "worker"])
def test_one_group_still_on_mongo_keeps_mongo_required(program):
    # identity joins no other group in Mongo (its join into the actions
    # group's collection went with the actions group's move to Postgres), so
    # it may stay on Mongo alone
    result = boot(
        program,
        {
            **ALL_POSTGRES,
            "DB_READ_SOURCE__identity": "mongo",
            "DB_WRITE_MODE__identity": "dual",
        },
    )
    assert result.returncode != 0
    assert "ServerSelectionTimeoutError" in result.stderr


@pytest.mark.parametrize("program", [API, WORKER], ids=["api", "worker"])
def test_a_stale_flag_for_a_postgres_only_group_refuses_the_start(program):
    """refdata, analytics, ai and actions have no Mongo store since 4.1: a
    flag left from the cutover that sends one of them elsewhere stops the
    start, naming it."""
    result = boot(program, {"DB_WRITE_MODE__actions": "dual"})
    assert result.returncode != 0
    assert "FlagError" in result.stderr
    assert "DB_WRITE_MODE__actions='dual'" in result.stderr
    assert "served from Postgres only" in result.stderr
