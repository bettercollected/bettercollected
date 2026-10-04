"""A workspace's custom domain is an allowed (credentialed) CORS origin only
while the domain is verified, on the custom-domain service path and on the
legacy path; stored origins are pruned to match."""

import datetime as dt
from typing import Any, Coroutine
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.app.container import container
from backend.app.middlewares.dynamic_cors_middleware import DynamicCORSMiddleware
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.custom_domain_origins import prune_unverified_origins
from tests.app.controllers.data import proUser
from tests.app.custom_domain.conftest import SECRET
from tests.app.custom_domain.fake import FakeClient, domain_dict, signed_event

pytestmark = pytest.mark.asyncio

WORKSPACES = "/api/v1/workspaces"
HOST = "forms.customer.example"
ORIGIN = "https://" + HOST


@pytest.fixture(autouse=True)
async def _fresh_cors_cache():
    """Each test starts from what is stored, not a previous test's cache."""
    await DynamicCORSMiddleware.force_refresh_origins()
    yield


async def cors_allows(client: AsyncClient, origin: str) -> bool:
    response = await client.options(
        f"{WORKSPACES}/mine",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    allowed = response.headers.get("access-control-allow-origin") == origin
    if allowed:
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-credentials") == "true"
    else:
        assert response.status_code == 400
    return allowed


async def deliver(client: AsyncClient, event_type: str, domain: dict, created_at):
    body, signature = signed_event(SECRET, event_type, domain, created_at=created_at)
    response = await client.post(
        "/api/v1/custom-domain/webhooks",
        content=body,
        headers={
            "X-Custom-Domain-Signature": signature,
            "content-type": "application/json",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["outcome"]


async def set_domain(client, workspace, cookies, hostname=HOST):
    response = await client.patch(
        f"{WORKSPACES}/{workspace.id}",
        cookies=cookies,
        data={"custom_domain": hostname},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def make_ready(client, workspace, domain_id, hostname=HOST, minutes=5):
    at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    ready = domain_dict(
        hostname, str(workspace.id), status="ready", domain_id=domain_id, updated_at=at
    )
    assert await deliver(client, "domain.ready", ready, at) == "applied"
    return at


async def stored_origins():
    return await container.allowed_origins_repo().list_origins()


class TestCustomDomainService:
    async def test_an_unverified_domain_is_not_an_allowed_origin(
        self,
        client: AsyncClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict,
        fake_client: FakeClient,
    ):
        body = await set_domain(client, workspace_pro, test_pro_user_cookies)
        assert body["customDomainStatus"] == "pending_dns"
        assert ORIGIN not in await stored_origins()
        assert not await cors_allows(client, ORIGIN)

        # the status page reads a still-pending domain: nothing changes
        status = await client.get(
            f"{WORKSPACES}/{workspace_pro.id}/verify-domain",
            cookies=test_pro_user_cookies,
        )
        assert status.json()["verified"] is False
        assert not await cors_allows(client, ORIGIN)

    async def test_ready_webhook_makes_it_an_allowed_origin(
        self,
        client: AsyncClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict,
        fake_client: FakeClient,
    ):
        body = await set_domain(client, workspace_pro, test_pro_user_cookies)
        at = await make_ready(client, workspace_pro, body["customDomainId"])
        assert await cors_allows(client, ORIGIN)

        # losing verification takes the origin away again
        later = at + dt.timedelta(minutes=1)
        attention = domain_dict(
            HOST,
            str(workspace_pro.id),
            status="attention_required",
            domain_id=body["customDomainId"],
            updated_at=later,
        )
        outcome = await deliver(client, "domain.attention_required", attention, later)
        assert outcome == "applied"
        assert not await cors_allows(client, ORIGIN)
        assert ORIGIN not in await stored_origins()

    async def test_status_page_and_recheck_follow_verification(
        self,
        client: AsyncClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict,
        fake_client: FakeClient,
    ):
        body = await set_domain(client, workspace_pro, test_pro_user_cookies)
        url = f"{WORKSPACES}/{workspace_pro.id}"
        fake_client.set_status(body["customDomainId"], "ready")
        await client.get(f"{url}/verify-domain", cookies=test_pro_user_cookies)
        assert await cors_allows(client, ORIGIN)

        fake_client.set_status(body["customDomainId"], "attention_required")
        response = await client.post(
            f"{url}/custom-domain/recheck", cookies=test_pro_user_cookies
        )
        assert response.status_code == 200, response.text
        assert not await cors_allows(client, ORIGIN)

    async def test_changing_the_domain_removes_the_old_origin(
        self,
        client: AsyncClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict,
        fake_client: FakeClient,
    ):
        body = await set_domain(client, workspace_pro, test_pro_user_cookies)
        await make_ready(client, workspace_pro, body["customDomainId"])
        assert await cors_allows(client, ORIGIN)

        await set_domain(
            client, workspace_pro, test_pro_user_cookies, "new.customer.example"
        )
        assert not await cors_allows(client, ORIGIN)
        assert not await cors_allows(client, "https://new.customer.example")
        assert await stored_origins() == []

    async def test_clearing_the_domain_removes_its_origin(
        self,
        client: AsyncClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict,
        fake_client: FakeClient,
    ):
        body = await set_domain(client, workspace_pro, test_pro_user_cookies)
        await make_ready(client, workspace_pro, body["customDomainId"])
        assert await cors_allows(client, ORIGIN)

        response = await client.delete(
            f"{WORKSPACES}/{workspace_pro.id}/custom-domain",
            cookies=test_pro_user_cookies,
        )
        assert response.status_code == 200, response.text
        assert not await cors_allows(client, ORIGIN)
        assert await stored_origins() == []


class TestLegacyPath:
    async def test_origin_follows_legacy_verification(
        self,
        client: AsyncClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        test_pro_user_cookies: dict,
    ):
        service = container.workspace_service()
        assert not service._custom_domain_enabled
        body = await set_domain(client, workspace_pro, test_pro_user_cookies)
        assert body["customDomain"] == HOST
        assert not await cors_allows(client, ORIGIN)

        url = f"{WORKSPACES}/{workspace_pro.id}/verify-domain"
        verdict = AsyncMock(
            return_value={"domain_verified": True, "txt_verified": False}
        )
        with patch.object(service.http_client, "get", verdict):
            await client.get(url, cookies=test_pro_user_cookies)
        assert not await cors_allows(client, ORIGIN)

        verdict.return_value = {"domain_verified": True, "txt_verified": True}
        with patch.object(service.http_client, "get", verdict):
            await client.get(url, cookies=test_pro_user_cookies)
        assert await cors_allows(client, ORIGIN)

        # a new hostname starts unverified; the old one stops being allowed
        body = await set_domain(
            client, workspace_pro, test_pro_user_cookies, "new.customer.example"
        )
        assert body["customDomainVerified"] is False
        assert not await cors_allows(client, ORIGIN)
        assert not await cors_allows(client, "https://new.customer.example")

        response = await client.delete(
            f"{WORKSPACES}/{workspace_pro.id}/custom-domain",
            cookies=test_pro_user_cookies,
        )
        assert response.status_code == 200, response.text
        assert await stored_origins() == []

    async def test_deleting_the_owner_removes_the_origin(
        self, workspace_pro: Coroutine[Any, Any, WorkspaceDocument]
    ):
        await container.workspace_repo().set_fields(
            workspace_pro, {"custom_domain": HOST, "custom_domain_verified": True}
        )
        await container.allowed_origins_repo().add(ORIGIN)
        service = container.workspace_service()
        with patch.object(container.aws_service(), "delete_folder_from_s3"):
            await service.delete_workspaces_of_user_with_forms(proUser)
        assert ORIGIN not in await stored_origins()


class TestPrune:
    async def _seed(self, workspace_pro, workspace_1):
        origins = container.allowed_origins_repo()
        await container.workspace_repo().set_fields(
            workspace_pro,
            {"custom_domain": "verified.example", "custom_domain_verified": True},
        )
        await container.workspace_repo().set_fields(
            workspace_1,
            {"custom_domain": "Pending.Example", "custom_domain_verified": False},
        )
        for origin in (
            "http://localhost:3000",
            "https://app.platform.example",
            "https://verified.example",
            "https://Pending.Example",
            "https://Pending.Example",  # no unique index: duplicates happen
            "https://leftover.example",
        ):
            await origins.add(origin)
        return origins

    async def test_removes_unverified_and_keeps_the_rest(
        self,
        client: AsyncClient,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        workspace_1: Coroutine[Any, Any, WorkspaceDocument],
    ):
        origins = await self._seed(workspace_pro, workspace_1)
        workspaces = container.workspace_repo()
        await DynamicCORSMiddleware.force_refresh_origins()
        assert await cors_allows(client, "https://Pending.Example")

        dry = await prune_unverified_origins(origins, workspaces, dry_run=True)
        assert dry["removed"] == ["https://Pending.Example"]
        assert (await stored_origins()).count("https://Pending.Example") == 2

        result = await prune_unverified_origins(origins, workspaces)
        assert result["removed"] == ["https://Pending.Example"]
        assert result["orphans"] == [
            "https://app.platform.example",
            "https://leftover.example",
        ]
        assert sorted(await stored_origins()) == [
            "http://localhost:3000",
            "https://app.platform.example",
            "https://leftover.example",
            "https://verified.example",
        ]
        # the running process stops allowing it without waiting for the TTL
        assert not await cors_allows(client, "https://Pending.Example")
        assert await cors_allows(client, "https://verified.example")

        again = await prune_unverified_origins(origins, workspaces)
        assert again["removed"] == []
        assert len(await stored_origins()) == 4

    async def test_orphans_only_on_request_and_never_the_kept_ones(
        self,
        workspace_pro: Coroutine[Any, Any, WorkspaceDocument],
        workspace_1: Coroutine[Any, Any, WorkspaceDocument],
    ):
        origins = await self._seed(workspace_pro, workspace_1)
        result = await prune_unverified_origins(
            origins,
            container.workspace_repo(),
            include_orphans=True,
            keep=["https://app.platform.example/"],
        )
        assert sorted(result["removed"]) == [
            "https://Pending.Example",
            "https://leftover.example",
        ]
        assert sorted(await stored_origins()) == [
            "http://localhost:3000",
            "https://app.platform.example",
            "https://verified.example",
        ]
