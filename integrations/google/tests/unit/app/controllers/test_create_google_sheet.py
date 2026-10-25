"""The Sheets credential reaches this service in the request body only (a URL
ends up in access logs), and creating the sheet never refreshes at the
credential's own token_uri."""

import json
from unittest.mock import patch

import pytest
from common.configs.crypto import Crypto
from fastapi.testclient import TestClient

from googleform.app.asgi import get_application
from googleform.app.services.google import GoogleService
from googleform.config import settings

URL = settings.API_ROOT_PATH + "/google/forms/create_google_sheet"
FORGED = "http://10.0.0.1:6379/x"


@pytest.fixture()
def client():
    return TestClient(get_application(), raise_server_exceptions=False)


@pytest.fixture()
def create_sheet():
    with patch.object(
        GoogleService, "create_sheet", return_value="sheet-id"
    ) as create_sheet:
        yield create_sheet


def test_the_credential_is_taken_from_the_body(client, create_sheet):
    response = client.post(URL, json={"title": "Sheet", "credential": "enc-cred"})

    assert response.status_code == 200, response.text
    assert response.json() == "sheet-id"
    create_sheet.assert_called_once_with("Sheet", "enc-cred")


def test_a_credential_in_the_query_string_is_refused(client, create_sheet):
    response = client.post(URL, params={"title": "Sheet", "credential": "enc-cred"})

    assert response.status_code == 422
    assert "enc-cred" not in response.text
    create_sheet.assert_not_called()


def test_creating_a_sheet_uses_the_configured_token_endpoint():
    """google-auth refreshes an expired token by itself at the credentials'
    token_uri while the sheet is created: that is the configured endpoint,
    whatever the stored credential says."""
    credential = Crypto(settings.AUTH_AES_HEX_KEY).encrypt(
        json.dumps(
            {
                "token": "old-access",
                "refresh_token": "refresh",
                "token_uri": FORGED,
                "client_id": "client",
                "client_secret": "secret",
                "expiry": "2000-01-01T00:00:00Z",
            }
        )
    )
    seen = []

    def fake_build(serviceName, version, credentials):
        seen.append(credentials.token_uri)
        raise TimeoutError()  # stop before any request is made

    with patch("googleform.app.services.google.build", fake_build):
        with pytest.raises(Exception):
            GoogleService().create_sheet("Sheet", credential)

    assert seen == [settings.GOOGLE_TOKEN_URI]
