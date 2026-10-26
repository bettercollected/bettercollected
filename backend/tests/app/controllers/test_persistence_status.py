"""The operator status endpoint: admin-only, and it reflects the jobs flags in
effect and whether Postgres answers."""

from httpx import AsyncClient

from backend.app.container import container
from tests.app.controllers.data import testUser


async def test_status_is_admin_only(client: AsyncClient, test_user_cookies_1):
    response = await client.get(
        "/api/v1/persistence/status", cookies=test_user_cookies_1
    )
    assert response.status_code == 403


async def test_status_reports_the_jobs_backends_and_postgres(
    client: AsyncClient, test_user_cookies, workspace_form_response
):
    assert testUser.is_admin()
    response = await client.get("/api/v1/persistence/status", cookies=test_user_cookies)
    assert response.status_code == 200
    body = response.json()
    flags = container.flags()
    assert body["flags"]["store"] == "postgres"
    assert (
        body["flags"]["jobs"]["delete_user"] == flags.jobs_backend("delete_user").value
    )
    # Postgres is the only store: Mongo is never used, and there is no routing
    # or outbox to report any more
    assert body["mongo"] == {"used": False, "status": "not used"}
    assert "metrics" not in body and "outbox" not in body
    assert body["postgres"] == {"configured": True, "reachable": True}
