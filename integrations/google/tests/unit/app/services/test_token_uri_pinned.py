"""Google tokens are refreshed only at the configured GOOGLE_TOKEN_URI. The
``token_uri`` stored in a credential is not trusted: a forged one (an internal
address, say) must never receive the client secret and refresh token, neither
from this service's own refresh nor from google-auth's automatic one."""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from common.constants import GOOGLE_DATETIME_FORMAT

from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.services.oauth_google import OauthGoogleService
from googleform.app.utils.google import GOOGLE_TOKEN_URIS, dict_to_credential
from googleform.config import settings

FORGED = "http://10.0.0.1:6379/x"


def _credential(token_uri, expired=True):
    expiry = datetime.now() + timedelta(hours=-1 if expired else 1)
    return SimpleNamespace(
        id="cred-1",
        email="a@example.com",
        updated_at=None,
        credentials=GoogleCredentialResponse(
            token="old-access",
            refresh_token="refresh",
            token_uri=token_uri,
            client_id="client",
            client_secret="secret",
            scopes="openid",
            expiry=expiry.strftime(GOOGLE_DATETIME_FORMAT),
        ),
    )


def _service():
    repo = MagicMock()
    repo.update = AsyncMock(side_effect=lambda email, doc: doc)
    service = OauthGoogleService.__new__(OauthGoogleService)
    service.oauth_credential_repo = repo
    return service, repo


@pytest.fixture()
def token_post():
    response = MagicMock()
    response.json = AsyncMock(
        return_value={"access_token": "new-access", "expires_in": 3600}
    )
    with patch(
        "googleform.app.services.oauth_google.AiohttpClient.post",
        AsyncMock(return_value=response),
    ) as post:
        yield post


@pytest.mark.asyncio
async def test_forged_token_uri_never_receives_a_request(token_post, caplog):
    service, repo = _service()

    saved = await service.fetch_oauth_token(_credential(FORGED))

    assert [call.args[0] for call in token_post.await_args_list] == [
        settings.GOOGLE_TOKEN_URI
    ]
    assert saved.credentials.token == "new-access"
    # the stored field is kept as it was, only not used
    assert saved.credentials.token_uri == FORGED
    repo.update.assert_awaited_once()
    # logged with the credential id, never the stored value or a secret
    assert "cred-1" in caplog.text
    assert FORGED not in caplog.text
    assert "secret" not in caplog.text and "old-access" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("token_uri", sorted(GOOGLE_TOKEN_URIS) + [None])
async def test_a_real_credential_still_refreshes(token_post, token_uri, caplog):
    service, _ = _service()

    saved = await service.fetch_oauth_token(_credential(token_uri))

    assert token_post.await_count == 1
    url, data = token_post.await_args.args
    assert url == settings.GOOGLE_TOKEN_URI
    assert data == {
        "client_id": "client",
        "client_secret": "secret",
        "refresh_token": "refresh",
        "grant_type": "refresh_token",
    }
    assert saved.credentials.token == "new-access"
    assert "Ignored" not in caplog.text


@pytest.mark.asyncio
async def test_a_configured_token_uri_is_used(token_post, monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_TOKEN_URI", "https://token.test/token")
    service, _ = _service()
    await service.fetch_oauth_token(_credential(FORGED))
    assert token_post.await_args.args[0] == "https://token.test/token"


@pytest.mark.asyncio
async def test_a_valid_token_is_not_refreshed(token_post):
    service, _ = _service()
    credential = _credential(FORGED, expired=False)
    assert await service.fetch_oauth_token(credential) is credential
    token_post.assert_not_awaited()


def test_google_auth_automatic_refresh_is_pinned_too():
    """Built Google API clients refresh by themselves at the credential's
    token_uri: that is the configured endpoint too."""
    seen = []

    def transport(url, method="GET", body=None, headers=None, **kwargs):
        seen.append(url)
        return SimpleNamespace(
            status=200,
            headers={},
            data=json.dumps(
                {"access_token": "new-access", "expires_in": 3600}
            ).encode(),
        )

    stored = _credential(FORGED).credentials.model_dump()
    credentials = dict_to_credential(stored)
    credentials.refresh(transport)

    assert seen == [settings.GOOGLE_TOKEN_URI]
    assert stored["token_uri"] == FORGED
