"""Platform admins named by PLATFORM_ADMIN_EMAILS get the ADMIN role in their
tokens (added at token time, never stored), and only on sign-ins that proved
the email: OTP, or Google reporting it verified. Never Typeform, never the
/callback JWT exchange, never an unverified session's refresh."""

import calendar
import datetime as dt
import json
from unittest.mock import AsyncMock

import pytest

from auth.app.container import container
from auth.app.services import google_auth_provider, typeform_auth_provider
from auth.app.services.google_auth_provider import GoogleAuthProvider
from auth.app.services.platform_admins import platform_admin_emails, roles_for
from auth.app.services.typeform_auth_provider import TypeformAuthProvider
from auth.config import settings
from common.models.user import User, UserInfo
from starlette.requests import Request
from tests.integration.app.test_google_auth_provider import FakeFlow

LISTED = "ops@example.com"


def test_emails_are_trimmed_case_insensitive_and_comma_separated():
    assert platform_admin_emails(" Ops@Example.com, ,b@example.com ") == {
        "ops@example.com",
        "b@example.com",
    }
    assert platform_admin_emails("") == frozenset()


def test_roles_for_adds_admin_once_only_for_verified_listed_emails():
    configured = LISTED
    assert roles_for("OPS@example.com", ["FORM_CREATOR"], True, configured) == [
        "FORM_CREATOR",
        "ADMIN",
    ]
    assert roles_for(LISTED, ["ADMIN"], True, configured) == ["ADMIN"]
    assert roles_for(LISTED, ["FORM_CREATOR"], False, configured) == ["FORM_CREATOR"]
    assert roles_for(LISTED, ["FORM_CREATOR"], None, configured) == ["FORM_CREATOR"]
    assert roles_for("other@example.com", [], True, configured) == []
    assert roles_for(None, None, True, configured) == []


@pytest.fixture
def platform_admin(monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", "Ops@Example.com")
    return LISTED


def _future_epoch(minutes=10):
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=minutes)
    return calendar.timegm(later.utctimetuple())


def test_otp_sign_in_proves_the_email(app_runner, platform_admin):
    app_runner.portal.call(
        lambda: container.user_repository().save_user(
            platform_admin, otp_code="ABC-123", otp_expiry=_future_epoch()
        )
    )
    response = app_runner.get(
        "auth/otp/validate", params={"email": platform_admin, "otp_code": "ABC-123"}
    )
    assert response.status_code == 200
    user = User(**response.json()["user"])
    assert "ADMIN" in user.roles
    assert user.email_verified is True


def test_jwt_exchange_callback_does_not_grant(app_runner, platform_admin):
    jwt_token = container.jwt_service().encode(UserInfo(email=platform_admin))
    response = app_runner.get("auth/callback", params={"jwt_token": jwt_token})
    assert response.status_code == 200
    assert "ADMIN" not in User(**response.json()).roles


def test_status_grants_only_for_a_verified_session(app_runner, platform_admin):
    # created through the routed repository (the callback saves with Beanie
    # directly, so its users are missing when Postgres serves reads)
    user = app_runner.portal.call(container.user_repository().save_user, platform_admin)
    params = {"user_id": str(user.id)}
    unverified = app_runner.get("auth/status", params=params)
    assert unverified.status_code == 200
    assert "ADMIN" not in unverified.json()["roles"]
    verified = app_runner.get("auth/status", params={**params, "email_verified": True})
    assert "ADMIN" in verified.json()["roles"]


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
    result = app_runner.portal.call(
        lambda: provider.basic_auth_callback("c", state, request=request)
    )
    return User(**result["user"])


def test_google_with_a_verified_email_grants(app_runner, platform_admin, monkeypatch):
    user = _google_callback(
        app_runner, monkeypatch, {"email": platform_admin, "verified_email": True}
    )
    assert "ADMIN" in user.roles
    assert user.email_verified is True


def test_google_with_an_unverified_email_does_not(
    app_runner, platform_admin, monkeypatch
):
    user = _google_callback(
        app_runner, monkeypatch, {"email": platform_admin, "verified_email": False}
    )
    assert "ADMIN" not in user.roles
    assert user.email_verified is False


def test_typeform_never_grants(app_runner, platform_admin, monkeypatch):
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
            lambda token, path, params=None: {
                "email": platform_admin,
                "alias": "Ops Person",
            }
        ),
    )
    state = typeform_auth_provider.crypto.encrypt(json.dumps({"creator": True}))
    result = app_runner.portal.call(
        lambda: TypeformAuthProvider().basic_auth_callback("c", state)
    )
    user = User(**result["user"])
    assert "ADMIN" not in user.roles
    assert not user.email_verified
