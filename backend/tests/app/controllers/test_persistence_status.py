"""The operator status endpoint: admin-only, and it reflects the flags in effect,
the shared routing counters and the outbox backlog."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.db.groups import GROUPS
from tests.app.controllers.data import testUser


async def test_status_is_admin_only(client: AsyncClient, test_user_cookies_1):
    response = await client.get(
        "/api/v1/persistence/status", cookies=test_user_cookies_1
    )
    assert response.status_code == 403


async def test_status_reports_flags_counters_and_outbox(
    client: AsyncClient, test_user_cookies, workspace_form
):
    assert testUser.is_admin()
    response = await client.get("/api/v1/persistence/status", cookies=test_user_cookies)
    assert response.status_code == 200
    body = response.json()
    flags = container.flags()
    assert (
        body["flags"]["groups"]["identity"]["read_source"]
        == flags.read_source("identity").value
    )
    assert (
        body["flags"]["jobs"]["delete_user"] == flags.jobs_backend("delete_user").value
    )
    # the workspace_form fixture wrote through the routed forms repositories
    # (identity is served from Postgres only, without routing)
    assert body["metrics"]["forms"]["calls"]
    mongo_used = flags.uses_mongo(GROUPS)
    assert body["mongo"] == {
        "used": mongo_used,
        "status": "used" if mongo_used else "not used",
    }
    # a store the backend does not use has no backlog to report (None)
    assert set(body["outbox"]) == {"mongo", "postgres"}
    assert body["outbox"]["mongo"] == (0 if mongo_used else None)
    assert body["postgres"]["configured"] == (container.pg_engine() is not None)
