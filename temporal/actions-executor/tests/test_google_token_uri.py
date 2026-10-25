"""Google tokens are refreshed only at Google's token endpoint. The
``token_uri`` stored in a credential is not trusted: a forged one (an internal
address, say) must never receive the client secret and refresh token, neither
from this worker's own refresh nor from google-auth's automatic one."""

import json
from datetime import datetime, timedelta

import pytest
from cryptography.fernet import Fernet

from settings.application import settings

# configs.crypto refuses to load without a key; the shared settings object may
# have been created before any test set one
if not settings.aes_hex_key:
    settings.aes_hex_key = Fernet.generate_key().decode()

from models.date import GOOGLE_DATETIME_FORMAT  # noqa: E402
from utilities import google_service  # noqa: E402

FORGED = "http://10.0.0.1:6379/x"
LEGACY = "https://accounts.google.com/o/oauth2/token"


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture
def posts(monkeypatch):
    """Every POST the module makes, by URL; answers like Google does."""
    calls = []

    def fake_post(url, data=None, **kwargs):
        calls.append((url, data))
        return _Response({"access_token": "new-access", "expires_in": 3600})

    monkeypatch.setattr(google_service.httpx, "post", fake_post)
    # the refreshed credential is sent back to the backend: not under test
    monkeypatch.setattr(google_service, "update_credentials_in_form", lambda *a: None)
    return calls


def _credential(token_uri, expired=True):
    expiry = datetime.now() + timedelta(hours=-1 if expired else 1)
    return {
        "token": "old-access",
        "refresh_token": "refresh",
        "token_uri": token_uri,
        "client_id": "client",
        "client_secret": "secret",
        "scopes": "x https://www.googleapis.com/auth/drive.file",
        "expiry": expiry.strftime(GOOGLE_DATETIME_FORMAT),
    }


def test_forged_token_uri_never_receives_a_request(posts, caplog):
    credential = _credential(FORGED)

    refreshed = google_service.fetch_oauth_token(credential, "action-1", "form-1")

    assert [url for url, _ in posts] == [google_service.DEFAULT_GOOGLE_TOKEN_URI]
    assert refreshed["token"] == "new-access"
    # the stored field is kept as it was, only not used
    assert refreshed["token_uri"] == FORGED
    # logged with the action id, never the stored value or a token
    assert "action-1" in caplog.text
    assert FORGED not in caplog.text
    assert "secret" not in caplog.text and "old-access" not in caplog.text


@pytest.mark.parametrize("token_uri", [None, "", "https://evil.example/token"])
def test_missing_or_foreign_token_uri_refreshes_at_google(posts, token_uri):
    google_service.refresh_access_token(_credential(token_uri), action_id="a")
    assert [url for url, _ in posts] == [google_service.DEFAULT_GOOGLE_TOKEN_URI]


@pytest.mark.parametrize("token_uri", sorted(google_service.GOOGLE_TOKEN_URIS))
def test_a_real_credential_still_refreshes(posts, token_uri):
    credential = _credential(token_uri)

    refreshed = google_service.fetch_oauth_token(credential, "action-1", "form-1")

    assert len(posts) == 1
    url, data = posts[0]
    assert url == token_uri
    assert data == {
        "client_id": "client",
        "client_secret": "secret",
        "refresh_token": "refresh",
        "grant_type": "refresh_token",
    }
    assert refreshed["token"] == "new-access"
    assert datetime.strptime(refreshed["expiry"], GOOGLE_DATETIME_FORMAT) > (
        datetime.now()
    )


def test_a_valid_token_is_not_refreshed(posts):
    credential = _credential(FORGED, expired=False)
    assert google_service.fetch_oauth_token(credential, "a", "f") is credential
    assert posts == []


def test_google_auth_automatic_refresh_is_pinned_too():
    """build_google_service hands the credential to google-auth, which
    refreshes by itself at its token_uri: that must be Google's too."""
    seen = []

    def transport(url, method="GET", body=None, headers=None, **kwargs):
        seen.append(url)

        class _R:
            status = 200
            headers = {}
            data = json.dumps(
                {"access_token": "new-access", "expires_in": 3600}
            ).encode()

        return _R()

    credentials = google_service.dict_to_credential(_credential(FORGED), "action-2")
    credentials.refresh(transport)

    assert seen == [google_service.DEFAULT_GOOGLE_TOKEN_URI]
