"""The operator status endpoint: admin-only, and it reflects the flags in effect,
the shared routing counters and the outbox backlog."""

import pytest
from httpx import AsyncClient

from backend.app.container import container
from tests.app.controllers.data import testUser


async def test_status_is_admin_only(client: AsyncClient, test_user_cookies_1):
    response = await client.get(
        "/api/v1/persistence/status", cookies=test_user_cookies_1
    )
    assert response.status_code == 403


async def test_status_reports_flags_counters_and_outbox(
    client: AsyncClient, test_user_cookies, workspace
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
    # the workspace fixture wrote through the routed identity repositories
    assert body["metrics"]["identity"]["calls"]
    assert set(body["outbox"]) == {"mongo", "postgres"} and body["outbox"]["mongo"] == 0
    assert body["postgres"]["configured"] == (container.pg_engine() is not None)
