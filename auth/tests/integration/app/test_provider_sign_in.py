"""A login provider signs in to (or creates) the account for an email only when
it vouches the user owns that email (#758): Google with a verified email, never
Typeform, never the /callback JWT exchange for an unknown email. Runs against
whichever store the routed repository serves (Mongo, dual, Postgres)."""

import json
import uuid
from unittest.mock import AsyncMock

from auth.app.container import container
from auth.app.services import google_auth_provider, typeform_auth_provider
from auth.app.services.google_auth_provider import GoogleAuthProvider
from auth.app.services.provider_sign_in import UNVERIFIED_EMAIL, may_sign_in
from auth.app.services.typeform_auth_provider import TypeformAuthProvider
from common.models.user import User, UserInfo
from starlette.requests import Request
from tests.integration.app.test_google_auth_provider import FakeFlow


def _email():
    return f"owner-{uuid.uuid4().hex[:12]}@example.com"


def _existing(app_runner, email):
    return app_runner.portal.call(container.user_repository().save_user, email)


def _lookup(app_runner, email):
    return app_runner.portal.call(container.user_repository().get_user_by_email, email)


def _google_callback(app_runner, monkeypatch, userinfo):
    monkeypatch.setattr(
        google_auth_provider.google_auth_oauthlib.flow, "Flow", FakeFlow
    )
    provider = GoogleAuthProvider()
    provider.get_google_user = AsyncMock(return_value=userinfo)
    app_runner.portal.call(
        provider.get_basic_auth_url, "https://admin.bettercollected.com/login", True
    )
    state = FakeFlow.authorization_calls[-1]["state"]
    request = Request(
        {
            "type": "http",
            "scheme": "https",
            "server": ("bettercollected.com", 443),
            "path": "/api/v1/auth/google/basic/callback",
            "query_string": f"code=c&state={state}".encode(),
            "headers": [],
        }
    )
    return app_runner.portal.call(
        lambda: provider.basic_auth_callback("c", state, request=request)
    )


def _typeform_callback(app_runner, monkeypatch, email):
    class TokenReply:
        status_code = 200

        @staticmethod
        def json():
            return {"access_token": "t"}

    monkeypatch.setattr(
        typeform_auth_provider.requests, "post", lambda *a, **k: TokenReply()
    )
    monkeypatch.setattr(
        TypeformAuthProvider,
        "perform_typeform_request",
        staticmethod(
            lambda token, path, params=None: {"email": email, "alias": "Some One"}
        ),
    )
    state = typeform_auth_provider.crypto.encrypt(
        json.dumps({"creator": True, "client_referer_url": "https://x.test/login"})
    )
    return app_runner.portal.call(
        lambda: TypeformAuthProvider().basic_auth_callback("c", state)
    )


def _assert_refused(result, provider):
    assert "user" not in result
    assert result["error"] == UNVERIFIED_EMAIL
    assert result["provider"] == provider
    # the backend still gets the page to send the user back to
    assert result["client_referer_url"]


def test_only_a_verified_email_may_sign_in():
    assert may_sign_in("a@example.com", True) is True
    assert may_sign_in("a@example.com", False) is False
    assert may_sign_in("a@example.com", None) is False
    assert may_sign_in("a@example.com", "true") is False
    assert may_sign_in("", True) is False
    assert may_sign_in(None, True) is False


def test_google_verified_signs_in_to_the_existing_account(app_runner, monkeypatch):
    email = _email()
    existing = _existing(app_runner, email)
    result = _google_callback(
        app_runner, monkeypatch, {"email": email, "verified_email": True}
    )
    user = User(**result["user"])
    assert user.id == str(existing.id)
    assert user.email_verified is True


def test_google_verified_creates_a_new_account(app_runner, monkeypatch):
    email = _email()
    result = _google_callback(
        app_runner, monkeypatch, {"email": email, "email_verified": True}
    )
    user = User(**result["user"])
    assert user.sub == email
    assert str(_lookup(app_runner, email).id) == user.id


def test_google_unverified_is_refused_for_an_existing_account(app_runner, monkeypatch):
    email = _email()
    _existing(app_runner, email)
    result = _google_callback(
        app_runner,
        monkeypatch,
        {"email": email, "verified_email": False, "given_name": "Mallory"},
    )
    _assert_refused(result, "google")
    # the account is untouched (no profile overwrite by the refused sign-in)
    assert _lookup(app_runner, email).first_name is None


def test_google_unverified_creates_no_account(app_runner, monkeypatch):
    email = _email()
    result = _google_callback(app_runner, monkeypatch, {"email": email})
    _assert_refused(result, "google")
    assert _lookup(app_runner, email) is None


def test_typeform_is_refused_for_an_existing_account(app_runner, monkeypatch):
    email = _email()
    _existing(app_runner, email)
    result = _typeform_callback(app_runner, monkeypatch, email)
    _assert_refused(result, "typeform")
    assert _lookup(app_runner, email).first_name is None


def test_typeform_creates_no_account(app_runner, monkeypatch):
    email = _email()
    result = _typeform_callback(app_runner, monkeypatch, email)
    _assert_refused(result, "typeform")
    assert _lookup(app_runner, email) is None


def test_jwt_exchange_reissues_for_an_existing_account(app_runner):
    email = _email()
    existing = _existing(app_runner, email)
    jwt_token = container.jwt_service().encode(UserInfo(email=email))
    response = app_runner.get("auth/callback", params={"jwt_token": jwt_token})
    assert response.status_code == 200
    assert User(**response.json()).id == str(existing.id)


def test_jwt_exchange_creates_no_account(app_runner):
    email = _email()
    jwt_token = container.jwt_service().encode(UserInfo(email=email))
    response = app_runner.get("auth/callback", params={"jwt_token": jwt_token})
    assert response.status_code == 403
    assert _lookup(app_runner, email) is None
