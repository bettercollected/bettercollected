"""A fake Google (token endpoint and Sheets API) for the backend's Google
Sheets OAuth flow (services/google_sheets_oauth.py). Nothing leaves the
process: any other request fails the test."""

import json
from typing import Callable, List, Optional
from urllib.parse import parse_qs

import httpx
import pytest

from backend.app.container import container
from backend.app.services.google_sheets_oauth import DRIVE_FILE_SCOPE, SHEETS_API_URL
from backend.config import settings

AUTH_URI = "https://accounts.fake-google.test/o/oauth2/auth"
TOKEN_URI = "https://oauth2.fake-google.test/token"
CLIENT_ID = "sign-in-client.apps.fake-google.test"
CLIENT_SECRET = "fake-sign-in-secret"
REDIRECT_URL = "https://app.example.test/integrations/google/callback"
ACCESS_TOKEN = "fake-access-token"
REFRESH_TOKEN = "fake-refresh-token"
SPREADSHEET_ID = "fake-spreadsheet-id"


class FakeGoogle:
    def __init__(self):
        self.requests: List[httpx.Request] = []
        self.token_status = 200
        self.token_body: dict = {
            "access_token": ACCESS_TOKEN,
            "refresh_token": REFRESH_TOKEN,
            "expires_in": 3599,
            "scope": DRIVE_FILE_SCOPE,
            "token_type": "Bearer",
        }
        self.sheets_status = 200
        self.sheets_body: dict = {"spreadsheetId": SPREADSHEET_ID}
        # raise this from every request instead of answering (timeouts, ...)
        self.fail_with: Optional[Callable[[httpx.Request], Exception]] = None

    def token_requests(self) -> List[dict]:
        return [
            {k: v[0] for k, v in parse_qs(r.content.decode()).items()}
            for r in self.requests
            if str(r.url) == TOKEN_URI
        ]

    def sheets_requests(self) -> List[httpx.Request]:
        return [r for r in self.requests if str(r.url).startswith(SHEETS_API_URL)]

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail_with is not None:
            raise self.fail_with(request)
        if request.method == "POST" and str(request.url) == TOKEN_URI:
            return httpx.Response(self.token_status, json=self.token_body)
        if request.method == "POST" and request.url.path == "/v4/spreadsheets":
            assert request.url.host == "sheets.googleapis.com"
            return httpx.Response(self.sheets_status, json=self.sheets_body)
        raise AssertionError(f"unexpected request to {request.url.host}")

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


def sheets_oauth_services():
    """Both GoogleSheetsOAuth instances the app uses: the OAuth endpoints'
    and the action saving's (two provider factories in the container)."""
    return [
        container.integration_service().integration__provider_factory.google_integration_provider.sheets_oauth,
        container.integration_provider().google_integration_provider.sheets_oauth,
    ]


@pytest.fixture()
def fake_google(monkeypatch):
    google = FakeGoogle()
    for service in sheets_oauth_services():
        monkeypatch.setattr(service, "transport", google.transport)
    return google


@pytest.fixture()
def sheets_client(monkeypatch):
    """The sign-in client configured, the switch left at its default."""
    config = settings.google_sheets
    monkeypatch.setattr(config, "CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(config, "CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setattr(config, "AUTH_URI", AUTH_URI)
    monkeypatch.setattr(config, "TOKEN_URI", TOKEN_URI)
    monkeypatch.setattr(config, "SHEET_REDIRECT_URL", REDIRECT_URL)
    return config


@pytest.fixture()
def backend_sheets_oauth(monkeypatch, sheets_client, fake_google):
    monkeypatch.setattr(sheets_client, "SHEETS_OAUTH", "backend")
    return fake_google


def decrypt_credential(ciphertext: str) -> str:
    return container.crypto().decrypt(ciphertext)


def credential_dict(ciphertext: str) -> dict:
    return json.loads(decrypt_credential(ciphertext))
