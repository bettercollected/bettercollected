"""Deleting a user's stored credentials revokes the grant at Google first in
GOOGLE_FORMS_IMPORT=on and readonly (one call that ends our access); off makes
no call. The local delete happens whatever the revocation's outcome."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from googleform.app.services.oauth_google import OauthGoogleService
from googleform.config import settings

pytestmark = pytest.mark.asyncio


def _service(credential):
    repo = MagicMock()
    repo.credentials_to_revoke = AsyncMock(
        return_value=[] if credential is None else [credential]
    )
    repo.delete_oauth_credential_for_user = AsyncMock(return_value=1)
    service = OauthGoogleService.__new__(OauthGoogleService)
    service.oauth_credential_repo = repo
    return service, repo


def _credential(refresh="refresh-1", token="access-1"):
    return SimpleNamespace(
        user_id="u1",
        credentials=SimpleNamespace(refresh_token=refresh, token=token),
    )


@pytest.fixture()
def mode(monkeypatch):
    return lambda value: monkeypatch.setattr(settings, "GOOGLE_FORMS_IMPORT", value)


@pytest.fixture()
def revoke():
    with patch(
        "googleform.app.services.oauth_google.AiohttpClient.post",
        AsyncMock(return_value=SimpleNamespace(status=200)),
    ) as post:
        yield post


@pytest.mark.parametrize("value", ["on", "readonly"])
async def test_on_and_readonly_revoke_the_refresh_token_then_delete(mode, revoke, value):
    mode(value)
    service, repo = _service(_credential())

    await service.delete_oauth_credentials_for_user(email="a@example.com", user_id="u1")

    assert revoke.await_count == 1
    repo.credentials_to_revoke.assert_awaited_once_with(
        email="a@example.com", user_id="u1"
    )
    assert revoke.await_args.args[0] == settings.GOOGLE_REVOKE_CREDENTIALS_URL
    assert revoke.await_args.kwargs["data"] == {"token": "refresh-1"}
    repo.delete_oauth_credential_for_user.assert_awaited_once_with(
        email="a@example.com", user_id="u1"
    )


async def test_the_access_token_is_revoked_without_a_refresh_token(mode, revoke):
    mode("on")
    service, _ = _service(_credential(refresh=None))
    await service.delete_oauth_credentials_for_user(email="a@example.com", user_id="u1")
    assert revoke.await_args.kwargs["data"] == {"token": "access-1"}


async def test_off_makes_no_call_to_google(mode, revoke):
    mode("off")
    service, repo = _service(_credential())

    await service.delete_oauth_credentials_for_user(email="a@example.com", user_id="u1")

    revoke.assert_not_awaited()
    repo.credentials_to_revoke.assert_not_awaited()
    repo.delete_oauth_credential_for_user.assert_awaited_once()


@pytest.mark.parametrize(
    "failure",
    [aiohttp.ClientConnectionError("down"), asyncio.TimeoutError()],
)
async def test_a_failed_revocation_never_blocks_the_delete(mode, failure, caplog):
    mode("on")
    service, repo = _service(_credential())
    with patch(
        "googleform.app.services.oauth_google.AiohttpClient.post",
        AsyncMock(side_effect=failure),
    ):
        await service.delete_oauth_credentials_for_user(
            email="a@example.com", user_id="u1"
        )

    repo.delete_oauth_credential_for_user.assert_awaited_once()
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "u1" in logged and "refresh-1" not in logged and "a@example.com" not in logged


async def test_a_rejected_revocation_still_deletes(mode):
    mode("readonly")
    service, repo = _service(_credential())
    with patch(
        "googleform.app.services.oauth_google.AiohttpClient.post",
        AsyncMock(return_value=SimpleNamespace(status=400)),
    ):
        await service.delete_oauth_credentials_for_user(
            email="a@example.com", user_id="u1"
        )
    repo.delete_oauth_credential_for_user.assert_awaited_once()


async def test_nothing_stored_means_no_call(mode, revoke):
    mode("on")
    service, repo = _service(None)
    await service.delete_oauth_credentials_for_user(email="a@example.com", user_id="u1")
    revoke.assert_not_awaited()
    repo.delete_oauth_credential_for_user.assert_awaited_once()


async def test_every_revocable_row_of_the_account_is_revoked(mode, revoke):
    mode("on")
    service, repo = _service(None)
    repo.credentials_to_revoke.return_value = [
        _credential(refresh="refresh-1"),
        _credential(refresh="refresh-2"),
    ]
    await service.delete_oauth_credentials_for_user(email="a@example.com", user_id="u1")
    tokens = [call.kwargs["data"]["token"] for call in revoke.await_args_list]
    assert tokens == ["refresh-1", "refresh-2"]
    repo.delete_oauth_credential_for_user.assert_awaited_once()
