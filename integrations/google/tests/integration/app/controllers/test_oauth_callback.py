"""The Google Forms OAuth round trip: authorize, then the callback exchanges the
code and stores the credential, in every storage mode.

Google's token endpoint is replaced by a fake that behaves like Google: it
refuses a code exchanged without the PKCE verifier of the challenge sent with
the authorization URL, and it answers with more scopes than were requested
(the email/profile aliases and drive.file granted earlier). No request leaves
the process; the credentials are made up.
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests
from fastapi.testclient import TestClient

from googleform.app import get_application
from googleform.app.services import oauth_google
from googleform.app.services.oauth_google import (
    MESSAGE_OAUTH_INVALID_STATE,
    MESSAGE_OAUTH_SCOPES_NOT_GRANTED,
    OauthGoogleService,
    _crypto,
)
from googleform.app.containers import Container
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.config import settings
from common.constants import MESSAGE_OAUTH_INVALID_CLIENT, MESSAGE_OAUTH_INVALID_GRANT

SERVICE_DIR = Path(__file__).resolve().parents[4]
API = settings.API_ROOT_PATH + "/google"
G = "https://www.googleapis.com/auth/"
# what production saw Google return: aliases plus a scope granted earlier
GRANTED_WITH_EXTRAS = [
    "email",
    "profile",
    "openid",
    G + "userinfo.profile",
    G + "userinfo.email",
    G + "drive.file",
    G + "forms.body.readonly",
    G + "forms.responses.readonly",
]
FAKE_ACCESS_TOKEN = "fake-access-token"


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


class FakeGoogleTokenEndpoint:
    """Stands in for requests' transport: only Google's token endpoint answers."""

    def __init__(self):
        self.challenges = {}  # code -> code_challenge sent with its authorization URL
        self.granted = GRANTED_WITH_EXTRAS
        self.error = None  # (status, error code) to answer with instead
        self.requests = []

    def issue_code(self, authorization_url: str) -> str:
        query = parse_qs(urlparse(authorization_url).query)
        assert query["code_challenge_method"] == ["S256"]
        code = "fake-code-" + uuid.uuid4().hex
        self.challenges[code] = query["code_challenge"][0]
        return code

    def send(self, adapter, request, **kwargs):
        assert request.url == settings.GOOGLE_TOKEN_URI, "no other outgoing request"
        form = parse_qs(request.body if isinstance(request.body, str) else request.body.decode())
        self.requests.append(form)
        if self.error:
            status, body = self.error[0], {"error": self.error[1]}
        else:
            code = form["code"][0]
            verifier = form.get("code_verifier", [None])[0]
            if verifier is None or _challenge(verifier) != self.challenges.get(code):
                status, body = 400, {
                    "error": "invalid_grant",
                    "error_description": "Missing code verifier.",
                }
            else:
                status, body = 200, {
                    "access_token": FAKE_ACCESS_TOKEN,
                    "expires_in": 3599,
                    "refresh_token": "fake-refresh-token",
                    "scope": " ".join(self.granted),
                    "token_type": "Bearer",
                }
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body).encode()
        response.headers["Content-Type"] = "application/json"
        response.url = request.url
        response.request = request
        return response


@pytest.fixture
def google(monkeypatch):
    fake = FakeGoogleTokenEndpoint()
    monkeypatch.setattr(
        requests.adapters.HTTPAdapter,
        "send",
        lambda adapter, request, **kwargs: fake.send(adapter, request, **kwargs),
    )

    async def userinfo(self, credentials):
        assert credentials.token == FAKE_ACCESS_TOKEN
        return {"email": fake.email}

    monkeypatch.setattr(OauthGoogleService, "get_google_user", userinfo)
    fake.email = f"hot65-{uuid.uuid4().hex[:8]}@example.com"
    return fake


@pytest.fixture
def client(google):
    with TestClient(get_application(), raise_server_exceptions=False) as test_client:
        yield test_client
        test_client.delete(
            API + "/oauth/credentials", params={"email": google.email, "user_id": "u-hot65"}
        )


def _state(email: str) -> str:
    return _crypto.encrypt(
        json.dumps({"email": email, "client_referer_uri": "https://app.example/w"})
    )


def _round_trip(client, google, state=None):
    state = state or _state(google.email)
    authorize = client.get(API + "/oauth/authorize", params={"state": state})
    assert authorize.status_code == 200, authorize.text
    code = google.issue_code(authorize.json()["oauth_url"])
    return client.get(
        API + "/oauth/callback",
        params={
            "state": state,
            "code": code,
            "scope": " ".join(google.granted),
            "user_id": "u-hot65",
        },
    )


def _stored_token(client, email):
    response = client.get(API + "/credentials", params={"email": email})
    assert response.status_code == 200, response.text
    return json.loads(_crypto.decrypt(response.json()))["credentials"]["token"]


def test_callback_with_more_scopes_than_requested_stores_the_credential(client, google):
    response = _round_trip(client, google)

    assert response.status_code == 200, response.text
    assert response.json()["email"] == google.email
    # the token request carried the verifier of the authorization URL's challenge
    assert google.requests and "code_verifier" in google.requests[-1]
    assert _stored_token(client, google.email) == FAKE_ACCESS_TOKEN


def test_a_second_connect_updates_the_stored_credential(client, google):
    assert _round_trip(client, google).status_code == 200
    response = _round_trip(client, google)

    assert response.status_code == 200, response.text
    assert _stored_token(client, google.email) == FAKE_ACCESS_TOKEN


def test_reconnecting_a_legacy_row_stores_it_encrypted(client, google):
    """A row connected by an older version has no user id, so its tokens could
    not be encrypted; reconnecting gives it the signed-in user's id."""
    repo = Container.oauth_credential_repo()
    client.portal.call(
        repo.save,
        Oauth2CredentialDocument(
            email=google.email,
            provider="google",
            credentials=GoogleCredentialResponse(token="old", refresh_token="old-r"),
        ),
    )

    assert _round_trip(client, google).status_code == 200

    rows = [r for r in client.portal.call(repo.list_all) if r.email == google.email]
    assert len(rows) == 1
    assert rows[0].user_id == "u-hot65"
    assert isinstance(rows[0].credentials, bytes)
    assert _stored_token(client, google.email) == FAKE_ACCESS_TOKEN


def test_a_missing_forms_scope_is_refused_clearly(client, google):
    google.granted = [s for s in GRANTED_WITH_EXTRAS if s != G + "forms.responses.readonly"]

    response = _round_trip(client, google)

    assert response.status_code == 403
    assert response.json() == MESSAGE_OAUTH_SCOPES_NOT_GRANTED
    stored = client.get(API + "/credentials", params={"email": google.email})
    assert stored.status_code != 200


def test_the_email_alias_counts_as_the_email_scope(client, google):
    google.granted = [s for s in GRANTED_WITH_EXTRAS if s != G + "userinfo.email"]

    assert _round_trip(client, google).status_code == 200


@pytest.mark.parametrize(
    "error, message",
    [
        ((400, "invalid_grant"), MESSAGE_OAUTH_INVALID_GRANT),
        ((401, "invalid_client"), MESSAGE_OAUTH_INVALID_CLIENT),
        ((400, "redirect_uri_mismatch"), "Could not fetch oauth token!"),
    ],
)
def test_google_refusals_answer_417_with_their_message(client, google, error, message):
    google.error = error

    response = _round_trip(client, google)

    assert response.status_code == 417
    assert response.json() == message


def test_a_state_that_does_not_decrypt_is_refused_before_the_exchange(client, google):
    response = client.get(
        API + "/oauth/callback",
        params={"state": "not-a-state", "code": "c", "user_id": "u-hot65"},
    )

    assert response.status_code == 400
    assert response.json() == MESSAGE_OAUTH_INVALID_STATE
    assert google.requests == []


def test_the_verifier_follows_from_the_state():
    verifier = oauth_google.pkce_code_verifier("some-state")

    assert verifier == oauth_google.pkce_code_verifier("some-state")
    assert verifier != oauth_google.pkce_code_verifier("other-state")
    assert len(verifier) == 43 and set(verifier) <= set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
    )


def test_relaxed_token_scope_does_not_depend_on_the_environment():
    env = {k: v for k, v in os.environ.items() if k != "OAUTHLIB_RELAX_TOKEN_SCOPE"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, googleform.app.services.oauth_google;"
            "print(os.environ.get('OAUTHLIB_RELAX_TOKEN_SCOPE'))",
        ],
        cwd=SERVICE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "1"
