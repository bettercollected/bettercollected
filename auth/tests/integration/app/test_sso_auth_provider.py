"""SSO through Polis (spike, docs/sso-spike.md): Polis's HTTP is mocked."""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from auth.app.exceptions import HTTPException
from auth.app.services import sso_auth_provider
from auth.app.services.auth_provider_factory import AuthProviderFactory
from auth.app.services.sso_auth_provider import (
    PKCE_VERIFIER_STATE_KEY,
    SSO_WORKSPACE_KEY,
    SSOAuthProvider,
    pkce_challenge,
)
from auth.config.sso_settings import SSOSettings

TENANT = "65e5501d0000000000000001"
OTHER_TENANT = "65e5501d0000000000000009"
POLIS = "http://polis.test"
REDIRECT = "http://backend.test/api/v1/auth/sso/callback"


def make_settings(**overrides):
    values = dict(
        ENABLED=True,
        POLIS_URL=POLIS,
        POLIS_CLIENT_SECRET="verifier-secret",
        REDIRECT_URI=REDIRECT,
        DOMAIN_TENANTS=f"example.com:{TENANT}, Acme.io:{OTHER_TENANT}",
    )
    values.update(overrides)
    return SSOSettings(**values)


class FakePolis:
    """Polis's /api/oauth/token + /api/oauth/userinfo."""

    def __init__(self, profile=None, token_status=200, userinfo_status=200):
        self.profile = profile
        self.token_status = token_status
        self.userinfo_status = userinfo_status
        self.token_requests = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/oauth/token":
            self.token_requests.append(parse_qs(request.content.decode()))
            if self.token_status != 200:
                return httpx.Response(self.token_status, json={"error": "bad"})
            return httpx.Response(200, json={"access_token": "hex.token"})
        if request.url.path == "/api/oauth/userinfo":
            assert request.headers["authorization"] == "Bearer hex.token"
            return httpx.Response(self.userinfo_status, json=self.profile or {})
        return httpx.Response(404)


def profile(email, tenant=TENANT, product="bettercollected"):
    return {
        "id": "abc",
        "email": email,
        "firstName": "Jane",
        "lastName": "Doe",
        "requested": {"tenant": tenant, "product": product},
    }


@pytest.fixture
def saved_users(monkeypatch):
    saved = []

    async def save_user(email, **kwargs):
        saved.append((email, kwargs))
        return SimpleNamespace(
            id="6a0000000000000000000001",
            email=email,
            roles=["FORM_RESPONDER", "FORM_CREATOR"],
            plan="FREE",
        )

    repo = SimpleNamespace(save_user=AsyncMock(side_effect=save_user))
    monkeypatch.setattr(sso_auth_provider, "_user_repository", lambda: repo)
    return saved


def start(provider, email="Jane@Example.com", referer="http://app.test/login"):
    url = asyncio.run(
        provider.get_basic_auth_url(referer, creator=True, login_hint=email)
    )
    parts = urlsplit(url)
    return parts, {k: v[0] for k, v in parse_qs(parts.query).items()}


def error_of(excinfo):
    return excinfo.value.content


def test_factory_serves_the_sso_provider():
    assert isinstance(AuthProviderFactory().get_auth_provider("sso"), SSOAuthProvider)


def test_authorize_url_targets_the_tenant_with_pkce():
    provider = SSOAuthProvider(make_settings())
    parts, query = start(provider)

    assert (
        f"{parts.scheme}://{parts.netloc}{parts.path}" == f"{POLIS}/api/oauth/authorize"
    )
    assert query["client_id"] == f"tenant={TENANT}&product=bettercollected"
    assert query["redirect_uri"] == REDIRECT
    assert query["response_type"] == "code"
    assert query["code_challenge_method"] == "S256"
    assert query["login_hint"] == "jane@example.com"
    state = json.loads(sso_auth_provider.crypto.decrypt(query["state"]))
    assert state["tenant"] == TENANT
    assert query["code_challenge"] == pkce_challenge(state[PKCE_VERIFIER_STATE_KEY])
    # the verifier never leaves our encrypted state
    assert state[PKCE_VERIFIER_STATE_KEY] not in parts.query


@pytest.mark.parametrize(
    "email", ["jane@unmapped.com", "not-an-email", "", "@example.com"]
)
def test_unmapped_domain_is_refused_before_leaving(email):
    provider = SSOAuthProvider(make_settings())
    with pytest.raises(HTTPException) as excinfo:
        start(provider, email=email)
    assert excinfo.value.status_code == 404
    assert error_of(excinfo)["code"] == "sso_not_configured"


def test_disabled_by_default():
    provider = SSOAuthProvider(SSOSettings())
    with pytest.raises(HTTPException) as excinfo:
        start(provider)
    assert error_of(excinfo)["code"] == "sso_disabled"


def test_callback_signs_in_a_tenant_email_as_verified(saved_users):
    polis = FakePolis(profile("Jane.Doe@example.com"))
    provider = SSOAuthProvider(make_settings(), httpx.MockTransport(polis.handler))
    _, query = start(provider)

    result = asyncio.run(provider.basic_auth_callback("hex.code", query["state"]))

    token_request = polis.token_requests[0]
    state = json.loads(sso_auth_provider.crypto.decrypt(query["state"]))
    assert token_request["code_verifier"] == [state[PKCE_VERIFIER_STATE_KEY]]
    assert token_request["redirect_uri"] == [REDIRECT]
    assert token_request["client_secret"] == ["verifier-secret"]
    assert saved_users[0][0] == "jane.doe@example.com"
    assert saved_users[0][1]["creator"] is True
    assert result["user"]["email_verified"] is True
    assert result["user"]["sub"] == "jane.doe@example.com"
    assert result[SSO_WORKSPACE_KEY] == TENANT
    assert result["client_referer_url"] == "http://app.test/login"
    assert PKCE_VERIFIER_STATE_KEY not in result


@pytest.mark.parametrize(
    "asserted",
    ["jane@example.org", "jane@acme.io", "jane@sub.example.com", ""],
)
def test_callback_refuses_emails_outside_the_tenant_domains(saved_users, asserted):
    # acme.io is mapped, but to another tenant: this IdP may not vouch for it.
    polis = FakePolis(profile(asserted))
    provider = SSOAuthProvider(make_settings(), httpx.MockTransport(polis.handler))
    _, query = start(provider)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(provider.basic_auth_callback("hex.code", query["state"]))

    assert excinfo.value.status_code == 403
    assert error_of(excinfo)["code"] == "sso_email_domain_not_allowed"
    assert error_of(excinfo)["client_referer_url"] == "http://app.test/login"
    assert saved_users == []  # no account created or linked


def test_callback_refuses_a_code_issued_for_another_tenant(saved_users):
    polis = FakePolis(profile("jane@example.com", tenant=OTHER_TENANT))
    provider = SSOAuthProvider(make_settings(), httpx.MockTransport(polis.handler))
    _, query = start(provider)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(provider.basic_auth_callback("hex.code", query["state"]))

    assert error_of(excinfo)["code"] == "sso_tenant_mismatch"
    assert saved_users == []


@pytest.mark.parametrize("failure", [{"token_status": 401}, {"userinfo_status": 403}])
def test_polis_failures_are_a_clean_401(saved_users, failure):
    polis = FakePolis(profile("jane@example.com"), **failure)
    provider = SSOAuthProvider(make_settings(), httpx.MockTransport(polis.handler))
    _, query = start(provider)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(provider.basic_auth_callback("hex.code", query["state"]))

    assert excinfo.value.status_code == 401
    assert error_of(excinfo)["code"] == "sso_failed"
    assert saved_users == []


def test_polis_unreachable_is_a_clean_401(saved_users):
    def unreachable(request):
        raise httpx.ConnectError("down")

    provider = SSOAuthProvider(make_settings(), httpx.MockTransport(unreachable))
    _, query = start(provider)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(provider.basic_auth_callback("hex.code", query["state"]))
    assert error_of(excinfo)["code"] == "sso_failed"


def test_tampered_or_foreign_state_is_refused(saved_users):
    provider = SSOAuthProvider(
        make_settings(), httpx.MockTransport(FakePolis().handler)
    )
    google_like = sso_auth_provider.crypto.encrypt(
        json.dumps({"client_referer_url": "x", PKCE_VERIFIER_STATE_KEY: "v"})
    )
    for state in ["garbage", google_like]:
        with pytest.raises(HTTPException) as excinfo:
            asyncio.run(provider.basic_auth_callback("hex.code", state))
        assert error_of(excinfo)["code"] == "sso_bad_state"


def test_expired_state_is_refused(saved_users, monkeypatch):
    provider = SSOAuthProvider(
        make_settings(STATE_MAX_AGE_SECONDS=60),
        httpx.MockTransport(FakePolis(profile("jane@example.com")).handler),
    )
    _, query = start(provider)
    real_time = time.time
    monkeypatch.setattr(sso_auth_provider.time, "time", lambda: real_time() + 61)

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(provider.basic_auth_callback("hex.code", query["state"]))
    assert error_of(excinfo)["code"] == "sso_expired"


def test_sso_session_counts_as_verified_for_platform_admins(saved_users, monkeypatch):
    # A tenant-domain email is treated like OTP/Google-verified: a configured
    # platform admin email gets ADMIN (why domain verification is a must, see
    # docs/sso-spike.md).
    from auth.config import settings

    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", "jane@example.com")
    provider = SSOAuthProvider(
        make_settings(),
        httpx.MockTransport(FakePolis(profile("jane@example.com")).handler),
    )
    _, query = start(provider)
    result = asyncio.run(provider.basic_auth_callback("hex.code", query["state"]))
    assert "ADMIN" in result["user"]["roles"]


def test_domain_tenant_parsing():
    s = make_settings(DOMAIN_TENANTS=" Example.com:t1 ,bad, :t2, x.io:t1,")
    assert s.domain_tenants() == {"example.com": "t1", "x.io": "t1"}
    assert s.domains_for_tenant("t1") == frozenset({"example.com", "x.io"})
    assert s.tenant_for_domain("EXAMPLE.COM") == "t1"
