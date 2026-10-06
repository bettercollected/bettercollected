"""Single sign-on through Polis (docs/sso.md): Polis's HTTP is mocked, the
user store is an in-memory fake (the routed repository is covered by the
parity test)."""

import asyncio
import json
import time
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from auth.app.exceptions import HTTPException
from auth.app.services import sso_service as sso_module
from auth.app.services.auth_provider_factory import AuthProviderFactory
from auth.app.services.sso_service import SsoService, pkce_challenge
from auth.config import settings
from auth.config.sso_settings import SSOSettings

TENANT = "65e5501d0000000000000001"
OTHER_TENANT = "65e5501d0000000000000009"
CLIENT_ID = "polis-connection-1"
POLIS = "http://polis.test"
REDIRECT = "http://backend.test/api/v1/auth/sso/callback"
CONTEXT = {"p": "login", "ws": TENANT, "c": "conn", "r": "http://app.test/login"}


def make_settings(**overrides):
    values = dict(ENABLED=True, POLIS_URL=POLIS, REDIRECT_URI=REDIRECT)
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


def profile(email, tenant=TENANT, product="bettercollected", client_id=CLIENT_ID):
    return {
        "id": "abc",
        "email": email,
        "firstName": "Jane",
        "lastName": "Doe",
        "requested": {"tenant": tenant, "product": product, "client_id": client_id},
    }


class FakeUsers:
    """The parts of the user repository single sign-on uses."""

    def __init__(self, *emails):
        self.users = [self._doc(e, i) for i, e in enumerate(emails, start=1)]
        self.saved = []

    @staticmethod
    def _doc(email, n, roles=("FORM_RESPONDER",)):
        return SimpleNamespace(
            id=f"6a00000000000000000000{n:02d}",
            email=email,
            roles=list(roles),
            plan="FREE",
        )

    async def get_user_by_email(self, email):
        return next((u for u in self.users if u.email == email), None)

    async def find_users_by_email_ci(self, email):
        return [u for u in self.users if u.email.lower() == email.lower()]

    async def save_user(self, email, **kwargs):
        self.saved.append((email, kwargs))
        user = await self.get_user_by_email(email)
        if user is None:
            user = self._doc(email, 90 + len(self.users), ("FORM_RESPONDER",))
            self.users.append(user)
        if kwargs.get("creator") and "FORM_CREATOR" not in user.roles:
            user.roles.append("FORM_CREATOR")
        return user


def service(users=None, polis=None, **overrides):
    transport = httpx.MockTransport(polis.handler) if polis else None
    return SsoService(users or FakeUsers(), make_settings(**overrides), transport)


def start(svc, email="Jane@Example.com", tenant=TENANT, client_id=CLIENT_ID):
    url = svc.authorize_url(tenant, client_id, json.dumps(CONTEXT), email)
    parts = urlsplit(url)
    return parts, {k: v[0] for k, v in parse_qs(parts.query).items()}


def content(excinfo):
    return excinfo.value.content


def callback(svc, query, code="hex.code", **kwargs):
    return asyncio.run(svc.callback(code, query["state"], **kwargs))


# -- start --------------------------------------------------------------------
def test_sso_is_not_a_basic_auth_provider():
    # the generic /{provider}/basic route never reaches SSO: it has no tenant
    with pytest.raises(HTTPException):
        AuthProviderFactory().get_auth_provider("sso")


def test_authorize_url_pins_the_connection_with_pkce():
    parts, query = start(service())

    assert (
        f"{parts.scheme}://{parts.netloc}{parts.path}" == f"{POLIS}/api/oauth/authorize"
    )
    assert query["client_id"] == CLIENT_ID
    assert query["redirect_uri"] == REDIRECT
    assert query["response_type"] == "code"
    assert query["code_challenge_method"] == "S256"
    assert query["login_hint"] == "jane@example.com"
    state = json.loads(sso_module.crypto.decrypt(query["state"]))
    assert state["tenant"] == TENANT and state["client_id"] == CLIENT_ID
    assert state["context"] == CONTEXT
    assert query["code_challenge"] == pkce_challenge(state["verifier"])
    # the verifier never leaves our encrypted state
    assert state["verifier"] not in parts.query


def test_disabled_by_default():
    with pytest.raises(HTTPException) as excinfo:
        SsoService(FakeUsers(), SSOSettings()).authorize_url(TENANT, CLIENT_ID)
    assert content(excinfo)["code"] == "sso_disabled"


@pytest.mark.parametrize("context", ["not json", "[1, 2]", "x" * 5000])
def test_a_bad_context_is_refused(context):
    with pytest.raises(HTTPException):
        service().authorize_url(TENANT, CLIENT_ID, context)


def test_an_invalid_login_hint_is_dropped():
    _, query = start(service(), email="not an email")
    assert "login_hint" not in query


# -- callback -----------------------------------------------------------------
def test_callback_returns_the_asserted_email_without_creating_an_account():
    users = FakeUsers()
    polis = FakePolis(profile("Jane.Doe@Example.com"))
    svc = service(users, polis)
    _, query = start(svc)

    result = callback(svc, query)

    assert result["email"] == "jane.doe@example.com"
    assert result["tenant"] == TENANT
    assert result["polis_client_id"] == CLIENT_ID
    assert result["context"] == CONTEXT
    assert result["existing_user_id"] is None
    assert result["account_conflict"] is False
    assert result["assertion"]
    assert users.saved == []  # the backend checks domain and seats first
    sent = polis.token_requests[0]
    state = json.loads(sso_module.crypto.decrypt(query["state"]))
    assert sent["code_verifier"] == [state["verifier"]]
    assert sent["redirect_uri"] == [REDIRECT]
    assert sent["client_id"] == [CLIENT_ID]
    assert "client_secret" not in sent  # PKCE: no shared secret needed


def test_the_client_secret_is_sent_when_configured():
    polis = FakePolis(profile("jane@example.com"))
    svc = service(polis=polis, POLIS_CLIENT_SECRET="verifier-secret")
    _, query = start(svc)
    callback(svc, query)
    assert polis.token_requests[0]["client_secret"] == ["verifier-secret"]


@pytest.mark.parametrize(
    "requested",
    [
        {"tenant": OTHER_TENANT},
        {"product": "other-product"},
        {"client_id": "another-connection"},
    ],
)
def test_a_code_for_another_tenant_or_connection_is_refused(requested):
    asserted = profile("jane@example.com")
    asserted["requested"].update(requested)
    svc = service(polis=FakePolis(asserted))
    _, query = start(svc)

    with pytest.raises(HTTPException) as excinfo:
        callback(svc, query)

    assert excinfo.value.status_code == 403
    assert content(excinfo)["code"] == "sso_tenant_mismatch"
    assert content(excinfo)["context"] == CONTEXT


def test_an_existing_account_is_matched_ignoring_case():
    users = FakeUsers("Bob@Example.com")
    svc = service(users, FakePolis(profile("bob@example.com")))
    _, query = start(svc)

    result = callback(svc, query)

    assert result["existing_user_id"] == users.users[0].id
    assert result["account_conflict"] is False


def test_several_case_variants_are_a_conflict():
    users = FakeUsers("Bob@Example.com", "BOB@example.com")
    svc = service(users, FakePolis(profile("bob@example.com")))
    _, query = start(svc)

    result = callback(svc, query)

    assert result["existing_user_id"] is None
    assert result["account_conflict"] is True


def test_an_exact_match_wins_over_case_variants():
    users = FakeUsers("Bob@Example.com", "bob@example.com")
    svc = service(users, FakePolis(profile("BOB@example.com")))
    _, query = start(svc)

    result = callback(svc, query)

    assert result["existing_user_id"] == users.users[1].id


@pytest.mark.parametrize("email", ["", "not-an-email", None])
def test_no_usable_email_is_refused(email):
    svc = service(polis=FakePolis(profile(email)))
    _, query = start(svc)
    with pytest.raises(HTTPException) as excinfo:
        callback(svc, query)
    # its own code: not the same as an address on the wrong domain
    assert content(excinfo)["code"] == "sso_email_missing"
    # a regular sign-in reports nothing about the claims
    assert "claim_names" not in content(excinfo)


# -- "Test connection" ----------------------------------------------------------
def start_test(svc, protocol="saml"):
    url = svc.authorize_url(
        TENANT, CLIENT_ID, json.dumps(CONTEXT), None, test=True, protocol=protocol
    )
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def test_a_regular_sign_in_reuses_the_idp_session():
    _, query = start(service())
    assert "forceAuthn" not in query and "prompt" not in query


def test_a_saml_test_asks_for_a_fresh_sign_in():
    query = start_test(service(), "saml")
    assert query["forceAuthn"] == "true"
    assert "prompt" not in query


def test_an_oidc_test_adds_no_parameter():
    # Polis would not forward one (OPENID_REQUEST_FORWARD_PARAMS stays off)
    query = start_test(service(), "oidc")
    assert set(query) == {
        "response_type",
        "client_id",
        "redirect_uri",
        "state",
        "code_challenge",
        "code_challenge_method",
    }


def test_an_unknown_protocol_is_refused():
    with pytest.raises(HTTPException) as excinfo:
        start_test(service(), "kerberos")
    assert content(excinfo)["code"] == "sso_failed"


def _raw_profile(email, raw):
    return {**profile(email), "raw": raw}


RAW = {
    "preferred_username": "dev@example.com",
    "upn": "dev@example.com",
    "http://schemas.microsoft.com/identity/claims/objectidentifier": "0000-1111",
    "bad name with spaces": "x",
    "dev@example.com": "a value-looking key",
    "x" * 200: "too long",
}


def test_a_test_reports_claim_names_never_values():
    svc = service(polis=FakePolis(_raw_profile("dev@example.com", RAW)))
    query = start_test(svc)

    result = callback(svc, query)

    assert result["claim_names"] == [
        "http://schemas.microsoft.com/identity/claims/objectidentifier",
        "preferred_username",
        "upn",
    ]
    assert "0000-1111" not in json.dumps(result["claim_names"])


def test_a_missing_email_in_a_test_reports_the_claim_names():
    raw = {k: v for k, v in RAW.items() if k in ("preferred_username", "upn")}
    svc = service(polis=FakePolis(_raw_profile(None, raw)))
    query = start_test(svc, "oidc")
    with pytest.raises(HTTPException) as excinfo:
        callback(svc, query)
    assert content(excinfo)["code"] == "sso_email_missing"
    assert content(excinfo)["claim_names"] == ["preferred_username", "upn"]
    assert content(excinfo)["context"] == CONTEXT


def test_claim_names_are_capped():
    raw = {f"claim_{n:03d}": "v" for n in range(80)}
    svc = service(polis=FakePolis(_raw_profile("dev@example.com", raw)))
    result = callback(svc, start_test(svc))
    assert len(result["claim_names"]) == sso_module.MAX_CLAIM_NAMES


def test_no_raw_claims_reports_an_empty_list():
    svc = service(polis=FakePolis(profile("dev@example.com")))
    assert callback(svc, start_test(svc))["claim_names"] == []


def test_a_regular_sign_in_never_reports_claim_names():
    svc = service(polis=FakePolis(_raw_profile("dev@example.com", RAW)))
    _, query = start(svc)
    assert "claim_names" not in callback(svc, query)


@pytest.mark.parametrize(
    "polis",
    [
        FakePolis(token_status=401),
        FakePolis(token_status=403),
        FakePolis(profile("x@example.com"), userinfo_status=500),
    ],
)
def test_polis_failures_are_sso_failed(polis):
    svc = service(polis=polis)
    _, query = start(svc)
    with pytest.raises(HTTPException) as excinfo:
        callback(svc, query)
    assert excinfo.value.status_code == 401
    assert content(excinfo)["code"] == "sso_failed"


def test_polis_unreachable_is_sso_failed():
    def unreachable(request):
        raise httpx.ConnectError("down")

    svc = SsoService(FakeUsers(), make_settings(), httpx.MockTransport(unreachable))
    _, query = start(svc)
    with pytest.raises(HTTPException) as excinfo:
        callback(svc, query)
    assert content(excinfo)["code"] == "sso_failed"


def test_an_idp_error_returns_the_context():
    svc = service()
    _, query = start(svc)
    with pytest.raises(HTTPException) as excinfo:
        callback(svc, query, code=None, idp_error=True)
    assert content(excinfo)["code"] == "sso_failed"
    assert content(excinfo)["context"] == CONTEXT


@pytest.mark.parametrize("state", ["garbage", "", sso_module.crypto.encrypt("{}")])
def test_tampered_state_is_refused(state):
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(service().callback("code", state))
    assert content(excinfo)["code"] == "sso_bad_state"


def test_expired_state_is_refused(monkeypatch):
    svc = service(polis=FakePolis(profile("jane@example.com")))
    _, query = start(svc)
    later = time.time() + 601
    monkeypatch.setattr(sso_module.time, "time", lambda: later)
    with pytest.raises(HTTPException) as excinfo:
        callback(svc, query)
    assert content(excinfo)["code"] == "sso_expired"
    assert content(excinfo)["context"] == CONTEXT


# -- account ------------------------------------------------------------------
def _assertion(svc, email="jane@example.com", users=None):
    _, query = start(svc)
    return callback(svc, query)["assertion"]


def test_account_creates_a_verified_sso_account():
    users = FakeUsers()
    svc = service(users, FakePolis(profile("Jane@Example.com")))
    user = asyncio.run(svc.account(_assertion(svc)))

    assert user.sub == "jane@example.com"
    assert user.email_verified is True
    assert user.auth_method == "sso"
    assert "FORM_CREATOR" in user.roles
    email, kwargs = users.saved[0]
    assert email == "jane@example.com"
    assert kwargs["creator"] is True and kwargs["first_name"] == "Jane"


def test_account_uses_an_existing_mixed_case_account():
    users = FakeUsers("Bob@Example.com")
    svc = service(users, FakePolis(profile("bob@example.com")))
    user = asyncio.run(svc.account(_assertion(svc)))

    assert user.id == users.users[0].id
    assert users.saved[0][0] == "Bob@Example.com"
    assert len(users.users) == 1  # no second account


def test_account_never_grants_the_platform_admin_role(monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", "root@example.com")
    svc = service(FakeUsers(), FakePolis(profile("root@example.com")))
    user = asyncio.run(svc.account(_assertion(svc)))
    assert "ADMIN" not in user.roles


def test_account_strips_a_stored_admin_role():
    users = FakeUsers()
    users.users.append(
        FakeUsers._doc(
            "root@example.com", 50, ("FORM_RESPONDER", "FORM_CREATOR", "ADMIN")
        )
    )
    svc = service(users, FakePolis(profile("root@example.com")))
    user = asyncio.run(svc.account(_assertion(svc)))
    assert "ADMIN" not in user.roles and "FORM_CREATOR" in user.roles


def test_account_refuses_a_forged_or_expired_assertion(monkeypatch):
    svc = service(FakeUsers(), FakePolis(profile("jane@example.com")))
    forged = sso_module.crypto.encrypt(json.dumps({"email": "x@example.com"}))
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(svc.account(forged))
    assert content(excinfo)["code"] == "sso_bad_state"
    with pytest.raises(HTTPException):
        asyncio.run(svc.account("garbage"))

    assertion = _assertion(svc)
    later = time.time() + 121
    monkeypatch.setattr(sso_module.time, "time", lambda: later)
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(svc.account(assertion))
    assert content(excinfo)["code"] == "sso_expired"


def test_account_refuses_a_state_as_assertion():
    svc = service()
    _, query = start(svc)
    with pytest.raises(HTTPException):
        asyncio.run(svc.account(query["state"]))


def test_settings_defaults():
    defaults = SSOSettings()
    assert defaults.ENABLED is False
    assert defaults.STATE_MAX_AGE_SECONDS == 600
    custom = SSOSettings(POLIS_URL="http://p.test/", POLIS_INTERNAL_URL="")
    assert custom.polis_internal_url == "http://p.test"


# -- routes -------------------------------------------------------------------
def test_routes_need_the_internal_key(app_runner, monkeypatch):
    from tests.integration.conftest import without_internal_key

    monkeypatch.setattr(settings, "sso_settings", make_settings())
    reply = app_runner.get(
        "/auth/sso/authorize", params={"tenant": TENANT, "client_id": CLIENT_ID}
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["auth_url"].startswith(f"{POLIS}/api/oauth/authorize?")

    reply = without_internal_key(app_runner).get(
        "/auth/sso/authorize", params={"tenant": TENANT, "client_id": CLIENT_ID}
    )
    assert reply.status_code == 403


def test_the_authorize_route_validates_the_test_flags(app_runner, monkeypatch):
    monkeypatch.setattr(settings, "sso_settings", make_settings())
    base = {"tenant": TENANT, "client_id": CLIENT_ID, "test": "true"}

    reply = app_runner.get("/auth/sso/authorize", params={**base, "protocol": "oidc"})
    assert reply.status_code == 200, reply.text
    query = parse_qs(urlsplit(reply.json()["auth_url"]).query)
    assert "prompt" not in query and "forceAuthn" not in query

    for protocol in ("ldap", "saml&prompt=none"):
        reply = app_runner.get(
            "/auth/sso/authorize", params={**base, "protocol": protocol}
        )
        assert reply.status_code == 422
    # anything else is not passed on
    reply = app_runner.get(
        "/auth/sso/authorize",
        params={**base, "protocol": "saml", "prompt": "none", "acr_values": "x"},
    )
    query = parse_qs(urlsplit(reply.json()["auth_url"]).query)
    assert query["forceAuthn"] == ["true"]
    assert "prompt" not in query and "acr_values" not in query


def test_account_route_creates_the_account(app_runner, monkeypatch):
    monkeypatch.setattr(settings, "sso_settings", make_settings())
    svc = service(FakeUsers(), FakePolis(profile("route@example.com")))
    assertion = _assertion(svc)

    reply = app_runner.post("/auth/sso/account", json={"assertion": assertion})

    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["sub"] == "route@example.com"
    assert body["email_verified"] is True and body["auth_method"] == "sso"


# -- directory sync (SCIM) ----------------------------------------------------
def test_directory_account_looks_up_without_creating():
    users = FakeUsers("Bob@Example.com")
    svc = service(users)

    found = asyncio.run(svc.directory_account("bob@example.com", create=False))
    missing = asyncio.run(svc.directory_account("new@example.com", create=False))

    assert found["user"].id == users.users[0].id and found["conflict"] is False
    assert missing == {"user": None, "conflict": False}
    assert users.saved == []


def test_directory_account_creates_a_verified_account_without_admin(monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", "root@example.com")
    users = FakeUsers()
    svc = service(users)
    reply = asyncio.run(
        svc.directory_account(
            "Root@Example.com", create=True, first_name="Ro", last_name="Ot"
        )
    )
    user = reply["user"]
    assert user.sub == "root@example.com" and user.email_verified is True
    assert "ADMIN" not in user.roles and "FORM_CREATOR" in user.roles
    assert users.saved[0][1]["first_name"] == "Ro"


def test_directory_account_reports_a_case_conflict():
    users = FakeUsers("Jane@Example.com", "JANE@example.com")
    svc = service(users)
    reply = asyncio.run(svc.directory_account("jane@example.com", create=True))
    assert reply == {"user": None, "conflict": True}
    assert users.saved == []


@pytest.mark.parametrize("email", ["", "not-an-email", "a b@example.com"])
def test_directory_account_refuses_bad_emails(email):
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(service().directory_account(email, create=True))
    assert content(excinfo)["code"] == "invalid_email"


def test_directory_account_needs_sso():
    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(
            service(ENABLED=False).directory_account("a@example.com", create=True)
        )
    assert content(excinfo)["code"] == "sso_disabled"


def test_directory_account_route_needs_the_internal_key(app_runner, monkeypatch):
    from tests.integration.conftest import without_internal_key

    monkeypatch.setattr(settings, "sso_settings", make_settings())
    body = {"email": "scim-route@example.com", "create": False}
    reply = app_runner.post("/auth/sso/directory-account", json=body)
    assert reply.status_code == 200, reply.text
    assert reply.json() == {"user": None, "conflict": False}
    reply = without_internal_key(app_runner).post(
        "/auth/sso/directory-account", json=body
    )
    assert reply.status_code == 403
