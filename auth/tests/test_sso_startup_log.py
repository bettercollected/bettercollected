"""SSO_ENABLED=true with the identity bridge settings missing: auth logs the
missing setting names at startup, never a value (docs/sso.md)."""

import logging

import pytest

from auth.app import asgi
from auth.config import settings

URL_VALUE = "https://polis-value-never-logged.example.net"
SECRET_VALUE = "client-secret-never-logged-7d2e"


@pytest.fixture
def sso(monkeypatch):
    sso = settings.sso_settings
    for key in ("POLIS_URL", "POLIS_INTERNAL_URL", "POLIS_CLIENT_SECRET", "REDIRECT_URI"):
        monkeypatch.setattr(sso, key, "")
    monkeypatch.setattr(sso, "ENABLED", True)
    return sso


def test_missing_settings_names(sso, monkeypatch):
    assert sso.missing_settings == ("SSO_POLIS_URL", "SSO_REDIRECT_URI")
    monkeypatch.setattr(sso, "POLIS_URL", URL_VALUE)
    monkeypatch.setattr(sso, "REDIRECT_URI", "   ")
    assert sso.missing_settings == ("SSO_REDIRECT_URI",)
    # the client secret is optional (PKCE): never required
    monkeypatch.setattr(sso, "REDIRECT_URI", URL_VALUE + "/cb")
    assert sso.missing_settings == ()


def test_startup_logs_missing_names_only(sso, monkeypatch, caplog):
    monkeypatch.setattr(sso, "POLIS_URL", URL_VALUE)
    monkeypatch.setattr(sso, "POLIS_CLIENT_SECRET", SECRET_VALUE)
    with caplog.at_level(logging.WARNING, logger=asgi.log.name):
        assert asgi.log_if_sso_incomplete() is False
    text = caplog.text
    assert "missing SSO_REDIRECT_URI." in text
    assert "SSO_POLIS_URL" not in text
    assert URL_VALUE not in text and SECRET_VALUE not in text
    assert "polis-value" not in text and "7d2e" not in text


def test_startup_quiet_when_off_or_complete(sso, monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger=asgi.log.name):
        monkeypatch.setattr(sso, "ENABLED", False)
        assert asgi.log_if_sso_incomplete() is True
        monkeypatch.setattr(sso, "ENABLED", True)
        monkeypatch.setattr(sso, "POLIS_URL", URL_VALUE)
        monkeypatch.setattr(sso, "REDIRECT_URI", URL_VALUE + "/cb")
        assert asgi.log_if_sso_incomplete() is True
    assert "SSO_ENABLED" not in caplog.text
