import asyncio
import json
from unittest.mock import AsyncMock

from auth.app.services import google_auth_provider
from auth.app.services.google_auth_provider import (
    GoogleAuthProvider,
    PKCE_VERIFIER_STATE_KEY,
)
from starlette.requests import Request


class FakeFlow:
    calls = []
    authorization_calls = []

    @classmethod
    def from_client_config(cls, **kwargs):
        cls.calls.append(kwargs)
        return cls()

    def authorization_url(self, **kwargs):
        self.authorization_calls.append(kwargs)
        return "https://accounts.google.com/o/oauth2/auth", kwargs["state"]

    def fetch_token(self, authorization_response):
        self.authorization_response = authorization_response

    @property
    def credentials(self):
        return object()


def test_google_basic_auth_reuses_the_pkce_verifier(monkeypatch):
    FakeFlow.calls = []
    FakeFlow.authorization_calls = []
    monkeypatch.setattr(
        google_auth_provider.google_auth_oauthlib.flow, "Flow", FakeFlow
    )

    provider = GoogleAuthProvider()
    provider.get_google_user = AsyncMock(return_value=None)

    asyncio.run(
        provider.get_basic_auth_url(
            "https://admin.bettercollected.com/login", creator=True
        )
    )
    state = FakeFlow.authorization_calls[0]["state"]
    state_data = json.loads(google_auth_provider.crypto.decrypt(state))
    code_verifier = state_data[PKCE_VERIFIER_STATE_KEY]

    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "server": ("bettercollected.com", 443),
            "path": "/api/v1/auth/google/basic/callback",
            "query_string": f"code=authorization-code&state={state}".encode(),
            "headers": [],
        }
    )
    response = asyncio.run(
        provider.basic_auth_callback("authorization-code", state, request=request)
    )

    assert FakeFlow.calls[0]["code_verifier"] == code_verifier
    assert FakeFlow.calls[0]["autogenerate_code_verifier"] is False
    assert FakeFlow.calls[1]["code_verifier"] == code_verifier
    assert FakeFlow.calls[1]["autogenerate_code_verifier"] is False
    assert PKCE_VERIFIER_STATE_KEY not in response
