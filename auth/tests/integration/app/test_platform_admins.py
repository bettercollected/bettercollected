"""Platform admins named by PLATFORM_ADMIN_EMAILS get the ADMIN role in their
tokens (added at token time, never stored)."""

import pytest

from auth.app.container import container
from auth.app.services.platform_admins import platform_admin_emails, roles_for
from auth.config import settings
from common.models.user import User, UserInfo


def test_emails_are_trimmed_case_insensitive_and_comma_separated():
    assert platform_admin_emails(" Ops@Example.com, ,b@example.com ") == {
        "ops@example.com",
        "b@example.com",
    }
    assert platform_admin_emails("") == frozenset()


def test_roles_for_adds_admin_once_and_only_for_listed_emails():
    configured = "ops@example.com"
    assert roles_for("OPS@example.com", ["FORM_CREATOR"], configured) == [
        "FORM_CREATOR",
        "ADMIN",
    ]
    assert roles_for("ops@example.com", ["ADMIN"], configured) == ["ADMIN"]
    assert roles_for("other@example.com", ["FORM_CREATOR"], configured) == [
        "FORM_CREATOR"
    ]
    assert roles_for(None, None, configured) == []


@pytest.fixture
def platform_admin(monkeypatch):
    monkeypatch.setattr(settings, "PLATFORM_ADMIN_EMAILS", "Ops@Example.com")
    return "ops@example.com"


def test_listed_email_gets_admin_in_its_token(app_runner, platform_admin):
    jwt_token = container.jwt_service().encode(UserInfo(email=platform_admin))
    response = app_runner.get("auth/callback", params={"jwt_token": jwt_token})
    assert response.status_code == 200
    assert "ADMIN" in User(**response.json()).roles


def test_other_emails_do_not(app_runner, platform_admin):
    jwt_token = container.jwt_service().encode(UserInfo(email="someone@example.com"))
    response = app_runner.get("auth/callback", params={"jwt_token": jwt_token})
    assert response.status_code == 200
    assert "ADMIN" not in User(**response.json()).roles


def test_status_used_for_token_refresh_reports_admin(app_runner, platform_admin):
    # created through the routed repository (the callback saves with Beanie
    # directly, so its users are missing when Postgres serves reads)
    user = app_runner.portal.call(container.user_repository().save_user, platform_admin)
    status = app_runner.get("auth/status", params={"user_id": str(user.id)})
    assert status.status_code == 200
    assert "ADMIN" in status.json()["roles"]
