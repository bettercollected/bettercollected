"""Workspace API keys — creation, masking, revocation, authentication."""

from typing import Any, Coroutine

from httpx import AsyncClient

from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.ai.api_keys import APIKeyService


class TestAPIKeys:
    async def test_create_shows_token_once_and_list_masks_it(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        created = await client.post(
            f"/api/v1/workspaces/{workspace.id}/api-keys",
            cookies=test_user_cookies,
            json={"name": "CI key", "scopes": ["forms:read", "forms:write"]},
        )
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["token"].startswith("bc_") and len(body["token"]) > 40
        assert body["prefix"] == body["token"][:11]
        assert body["scopes"] == ["forms:read", "forms:write"]

        listed = await client.get(
            f"/api/v1/workspaces/{workspace.id}/api-keys", cookies=test_user_cookies
        )
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        # The token itself never appears again.
        assert "token" not in listed.json()[0]
        assert listed.json()[0]["prefix"] == body["prefix"]

    async def test_unknown_scope_rejected(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        response = await client.post(
            f"/api/v1/workspaces/{workspace.id}/api-keys",
            cookies=test_user_cookies,
            json={"name": "bad", "scopes": ["root:everything"]},
        )
        assert response.status_code == 400
        assert "Unknown scopes" in response.text

    async def test_authenticate_and_revoke(
        self,
        client: AsyncClient,
        workspace: Coroutine[Any, Any, WorkspaceDocument],
        test_user_cookies: dict[str, str],
    ):
        created = await client.post(
            f"/api/v1/workspaces/{workspace.id}/api-keys",
            cookies=test_user_cookies,
            json={"name": "smoke", "scopes": ["forms:read"]},
        )
        token = created.json()["token"]
        key_id = created.json()["id"]

        # The token authenticates and carries its scopes + acting user.
        document = await APIKeyService.authenticate(token)
        assert str(document.workspace_id) == str(workspace.id)
        assert document.scopes == ["forms:read"]
        assert document.last_used_at is not None

        # Scope gate
        APIKeyService.require_scope(document, "forms:read")
        try:
            APIKeyService.require_scope(document, "forms:write")
            assert False, "should have raised"
        except HTTPException as e:
            assert e.status_code == 403

        # Revocation kills authentication.
        revoked = await client.delete(
            f"/api/v1/workspaces/{workspace.id}/api-keys/{key_id}",
            cookies=test_user_cookies,
        )
        assert revoked.status_code == 200
        assert revoked.json()[0]["revoked"] is True
        try:
            await APIKeyService.authenticate(token)
            assert False, "revoked key must not authenticate"
        except HTTPException as e:
            assert e.status_code == 401

    async def test_garbage_tokens_rejected(self):
        for bad in ["", "nope", "bc_deadbeef"]:
            try:
                await APIKeyService.authenticate(bad)
                assert False
            except HTTPException as e:
                assert e.status_code == 401


async def test_a_request_in_flight_never_brings_a_revoked_key_back(
    client: AsyncClient,
    workspace: Coroutine[Any, Any, WorkspaceDocument],
    test_user_cookies: dict[str, str],
    monkeypatch,
):
    """A request that read the key before it was revoked records its use
    without saving its stale copy: the key stays revoked, the request is
    refused, and nothing else of the stored key changes."""
    from backend.app.container import container

    created = await client.post(
        f"/api/v1/workspaces/{workspace.id}/api-keys",
        cookies=test_user_cookies,
        json={"name": "in flight", "scopes": ["forms:read"]},
    )
    token, key_id = created.json()["token"], created.json()["id"]
    repo = container.workspace_api_key_repo()
    stale = await repo.find_by_key_hash(
        (await repo.get_or_404(key_id)).key_hash
    )  # read by the request before the revocation
    revoked = await client.delete(
        f"/api/v1/workspaces/{workspace.id}/api-keys/{key_id}",
        cookies=test_user_cookies,
    )
    assert revoked.status_code == 200

    async def stale_read(_key_hash):
        return stale

    monkeypatch.setattr(repo, "find_by_key_hash", stale_read)
    try:
        await APIKeyService.authenticate(token)
        assert False, "a key revoked meanwhile must not authenticate"
    except HTTPException as e:
        assert e.status_code == 401
    stored = await repo.get_or_404(key_id)
    assert stored.revoked is True
    assert stored.last_used_at is None


async def test_touch_last_used_changes_only_that_field(clean_postgres):
    import datetime as dt

    from backend.app.container import container
    from backend.app.repositories.postgres.identity import (
        PostgresWorkspaceAPIKeyRepository,
    )
    from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
    from common.records import RecordId

    repo = PostgresWorkspaceAPIKeyRepository(container.pg_sessionmaker())
    key = WorkspaceAPIKeyDocument(
        id=RecordId(),
        workspace_id=RecordId(),
        name="ci",
        key_hash="hash-touch",
        prefix="hash-t",
        scopes=["forms:read"],
        created_by="tester",
    )
    await repo.save(key)
    stale = await repo.get_or_404(key.id)
    renamed = await repo.get_or_404(key.id)
    renamed.name = "renamed"
    await repo.save(renamed)
    now = dt.datetime(2030, 1, 2, 3, 4, 5, tzinfo=dt.timezone.utc)
    assert await repo.touch_last_used(stale.id, now) is True
    stored = await repo.get_or_404(key.id)
    assert stored.last_used_at == now and stored.name == "renamed"
    stored.revoked = True
    await repo.save(stored)
    later = now + dt.timedelta(hours=1)
    assert await repo.touch_last_used(key.id, later) is False
    assert await repo.touch_last_used(RecordId(), later) is False
    stored = await repo.get_or_404(key.id)
    assert stored.revoked is True and stored.last_used_at == now
