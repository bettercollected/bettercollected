"""A workspace's custom domain through the service: register, replace, check,
recheck, delete, and status updates arriving by webhook."""

import datetime as dt
from http import HTTPStatus
from typing import Any, Coroutine

import pytest
from custom_domain import RateLimitedError
from httpx import AsyncClient

from backend.app.container import container
from backend.app.schemas.workspace import WorkspaceDocument
from tests.app.custom_domain.conftest import SECRET
from tests.app.custom_domain.fake import FakeClient, domain_dict, signed_event

pytestmark = pytest.mark.asyncio

WORKSPACES = "/api/v1/workspaces"


async def test_register_replace_and_delete(
    client: AsyncClient,
    workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
    test_pro_user_cookies: dict,
    fake_client: FakeClient,
):
    url = f"{WORKSPACES}/{workspace_pro.id}"
    response = await client.patch(
        url,
        cookies=test_pro_user_cookies,
        data={"custom_domain": "Forms.Customer.Example"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["customDomain"] == "forms.customer.example"
    assert body["customDomainStatus"] == "pending_dns"
    assert body["customDomainVerified"] is False
    assert [r["type"] for r in body["customDomainDnsRecords"]] == ["TXT", "CNAME"]
    assert len(body["customDomainChecks"]) == 4
    first_id = body["customDomainId"]
    assert fake_client.domains[first_id]["reference"] == str(workspace_pro.id)

    # status endpoint reads the service, not a DNS guess
    fake_client.set_status(first_id, "ready")
    status = await client.get(f"{url}/verify-domain", cookies=test_pro_user_cookies)
    assert status.status_code == 200
    assert status.json()["provider"] == "custom-domain"
    assert status.json()["status"] == "ready" and status.json()["verified"] is True
    stored = await container.workspace_repo().find_by_id(workspace_pro.id)
    assert stored.custom_domain_verified is True

    # replacing registers the new hostname first, then deletes the old one
    response = await client.patch(
        url,
        cookies=test_pro_user_cookies,
        data={"custom_domain": "new.customer.example"},
    )
    assert response.status_code == 200, response.text
    second_id = response.json()["customDomainId"]
    assert second_id != first_id
    assert fake_client.domains[first_id]["status"] == "deleting"
    assert [c[0] for c in fake_client.calls if c[0] in ("create", "delete")][-2:] == [
        "create",
        "delete",
    ]

    # a refused replacement leaves the working domain untouched
    fake_client.fail_next = RateLimitedError(429, "rate_limited", "slow", retry_after=5)
    response = await client.patch(
        url,
        cookies=test_pro_user_cookies,
        data={"custom_domain": "third.customer.example"},
    )
    assert response.status_code == 429
    assert fake_client.domains[second_id]["status"] != "deleting"
    stored = await container.workspace_repo().find_by_id(workspace_pro.id)
    assert stored.custom_domain == "new.customer.example"
    assert stored.custom_domain_id == second_id
    origins = container.allowed_origins_repo()
    # the replacement is not verified yet, so it is not an allowed origin either
    assert not await origins.find_by_origin("https://new.customer.example")
    assert not await origins.find_by_origin("https://third.customer.example")
    assert not await origins.find_by_origin("https://forms.customer.example")

    # recheck is rate limited by the service; the UI gets retry_after
    fake_client.fail_next = RateLimitedError(
        429, "rate_limited", "slow", retry_after=17
    )
    response = await client.post(
        f"{url}/custom-domain/recheck", cookies=test_pro_user_cookies
    )
    assert response.status_code == 429
    assert response.json()["retry_after"] == 17
    assert response.headers["retry-after"] == "17"
    response = await client.post(
        f"{url}/custom-domain/recheck", cookies=test_pro_user_cookies
    )
    assert response.status_code == 200 and response.json()["id"] == second_id

    # delete stops service and clears every mirrored field
    response = await client.delete(
        f"{url}/custom-domain", cookies=test_pro_user_cookies
    )
    assert response.status_code == 200, response.text
    assert response.json()["customDomain"] == ""
    assert response.json()["customDomainId"] is None
    assert fake_client.domains[second_id]["status"] == "deleting"


async def test_delete_then_re_add_gets_a_fresh_domain(
    client: AsyncClient,
    workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
    test_pro_user_cookies: dict,
    fake_client: FakeClient,
):
    """The service replays an idempotency key for 24 hours; re-registering the
    same hostname must not hand back the deleted domain."""
    url = f"{WORKSPACES}/{workspace_pro.id}"
    first = await client.patch(
        url,
        cookies=test_pro_user_cookies,
        data={"custom_domain": "forms.customer.example"},
    )
    first_id = first.json()["customDomainId"]
    await client.delete(f"{url}/custom-domain", cookies=test_pro_user_cookies)
    again = await client.patch(
        url,
        cookies=test_pro_user_cookies,
        data={"custom_domain": "forms.customer.example"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["customDomainId"] != first_id
    assert again.json()["customDomainStatus"] == "pending_dns"
    assert fake_client.domains[first_id]["status"] == "deleting"
    # A -> B -> A within the window: a fresh domain each time
    await client.patch(
        url, cookies=test_pro_user_cookies, data={"custom_domain": "b.customer.example"}
    )
    back = await client.patch(
        url,
        cookies=test_pro_user_cookies,
        data={"custom_domain": "forms.customer.example"},
    )
    assert back.status_code == 200 and back.json()["customDomainId"] not in (
        first_id,
        again.json()["customDomainId"],
    )
    stored = await container.workspace_repo().find_by_id(workspace_pro.id)
    assert stored.custom_domain_attempt is None


async def test_a_domain_set_before_the_service_reports_unregistered(
    client: AsyncClient,
    workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
    test_pro_user_cookies: dict,
    fake_client: FakeClient,
):
    await container.workspace_repo().set_fields(
        workspace_pro, {"custom_domain": "legacy.customer.example"}
    )
    status = await client.get(
        f"{WORKSPACES}/{workspace_pro.id}/verify-domain", cookies=test_pro_user_cookies
    )
    assert status.status_code == 200, status.text
    assert (
        status.json()["status"] == "unregistered"
        and status.json()["hostname"] == "legacy.customer.example"
    )


async def test_removing_an_unregistered_domain_releases_the_imported_claim(
    client: AsyncClient,
    workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
    test_pro_user_cookies: dict,
    fake_client: FakeClient,
):
    """A legacy domain the import already holds for this workspace (not yet
    adopted) must not stay claimed after the customer removes it, or re-adding
    it would be refused as taken."""
    await container.workspace_repo().set_fields(
        workspace_pro, {"custom_domain": "legacy.customer.example"}
    )
    imported = fake_client.create_domain(
        "legacy.customer.example", str(workspace_pro.id)
    )
    url = f"{WORKSPACES}/{workspace_pro.id}"
    response = await client.delete(
        f"{url}/custom-domain", cookies=test_pro_user_cookies
    )
    assert response.status_code == 200, response.text
    assert response.json()["customDomain"] == ""
    assert fake_client.domains[imported.id]["status"] == "deleting"
    again = await client.patch(
        url,
        cookies=test_pro_user_cookies,
        data={"custom_domain": "legacy.customer.example"},
    )
    assert again.status_code == 200, again.text
    assert again.json()["customDomainId"] != imported.id


async def test_hostname_taken_by_the_service_is_a_conflict(
    client: AsyncClient,
    workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
    test_pro_user_cookies: dict,
    fake_client: FakeClient,
):
    fake_client.create_domain("forms.customer.example", "someone-else")
    response = await client.patch(
        f"{WORKSPACES}/{workspace_pro.id}",
        cookies=test_pro_user_cookies,
        data={"custom_domain": "forms.customer.example"},
    )
    assert response.status_code == 409
    stored = await container.workspace_repo().find_by_id(workspace_pro.id)
    assert not stored.custom_domain and stored.custom_domain_id is None


async def test_webhooks_update_the_workspace(
    client: AsyncClient,
    workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
    test_pro_user_cookies: dict,
    fake_client: FakeClient,
):
    url = f"{WORKSPACES}/{workspace_pro.id}"
    response = await client.patch(
        url,
        cookies=test_pro_user_cookies,
        data={"custom_domain": "forms.customer.example"},
    )
    domain_id = response.json()["customDomainId"]
    ready = domain_dict(
        "forms.customer.example",
        str(workspace_pro.id),
        status="ready",
        domain_id=domain_id,
    )

    async def deliver(event_type, domain, secret=SECRET, **kwargs):
        body, signature = signed_event(secret, event_type, domain, **kwargs)
        return await client.post(
            "/api/v1/custom-domain/webhooks",
            content=body,
            headers={
                "X-Custom-Domain-Signature": signature,
                "content-type": "application/json",
            },
        )

    bad = await deliver("domain.ready", ready, secret="whsec_forged")
    assert bad.status_code == 400

    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5)
    ready["updated_at"] = later.isoformat()
    ok = await deliver("domain.ready", ready, created_at=later)
    assert ok.status_code == 200 and ok.json()["outcome"] == "applied"
    stored = await container.workspace_repo().find_by_id(workspace_pro.id)
    assert (
        stored.custom_domain_status == "ready" and stored.custom_domain_verified is True
    )
    assert await container.allowed_origins_repo().find_by_origin(
        "https://forms.customer.example"
    )

    # an older event that arrives late does not move the workspace backwards
    earlier = later - dt.timedelta(minutes=2)
    attention = domain_dict(
        "forms.customer.example",
        str(workspace_pro.id),
        status="attention_required",
        domain_id=domain_id,
        updated_at=earlier,
    )
    stale = await deliver("domain.attention_required", attention, created_at=earlier)
    assert stale.json()["outcome"] == "stale"
    stored = await container.workspace_repo().find_by_id(workspace_pro.id)
    assert stored.custom_domain_status == "ready"

    unknown = domain_dict("other.example", "nobody", status="ready")
    assert (await deliver("domain.ready", unknown)).json()[
        "outcome"
    ] == "unknown_domain"

    gone = domain_dict(
        "forms.customer.example",
        str(workspace_pro.id),
        status="deleting",
        domain_id=domain_id,
        updated_at=later + dt.timedelta(minutes=1),
    )
    deleted = await deliver(
        "domain.deleted", gone, created_at=later + dt.timedelta(minutes=1)
    )
    assert deleted.json()["outcome"] == "applied"
    stored = await container.workspace_repo().find_by_id(workspace_pro.id)
    assert stored.custom_domain_id is None and stored.custom_domain_verified is False
    # the hostname stays so the customer sees what happened; CORS no longer allows it
    assert stored.custom_domain == "forms.customer.example"
    assert stored.custom_domain_status == "deleting"
    assert not await container.allowed_origins_repo().find_by_origin(
        "https://forms.customer.example"
    )
    status = await client.get(f"{url}/verify-domain", cookies=test_pro_user_cookies)
    assert status.json()["status"] == "removed" and status.json()["dns_records"] == []
