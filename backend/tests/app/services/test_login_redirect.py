"""After sign-in the browser goes back to the page the sign-in started from,
but only when that page is on one of this instance's origins (the client URL
and the ``allowed_origins`` the API trusts, custom domains included)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.app.services.auth_service import AuthService
from backend.app.services.login_redirect import (
    is_allowed_redirect,
    origin_of,
    safe_redirect,
)
from backend.config import settings

ALLOWED = [
    "https://admin.example.com",
    "https://forms.example.com",
    "https://forms.acme-custom.org",  # a workspace's custom domain
    "http://localhost:3000",
]


@pytest.mark.parametrize(
    "url",
    [
        "https://admin.example.com/login",
        "https://admin.example.com/dashboard?tab=forms#top",
        "https://ADMIN.example.com:443/login",
        "https://forms.acme-custom.org/my-form",
        "http://localhost:3000/login?type=responder",
    ],
)
def test_own_origins_are_allowed(url):
    assert is_allowed_redirect(url, ALLOWED)
    assert safe_redirect(url, ALLOWED, "https://admin.example.com/") == url


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example",
        "https://evil.example/login",
        "//evil.example",
        "//evil.example/login",
        "https://admin.example.com.evil.com/login",
        "https://evil.com/https://admin.example.com",
        "https://admin.example.com@evil.com/",
        "https://user:pw@admin.example.com/",
        "http://admin.example.com/login",  # scheme differs
        "https://admin.example.com:8443/login",  # port differs
        "http://localhost:3001/",
        "https:\\\\evil.example",
        "/\\evil.example",
        "https://admin.example.com\t.evil.com",
        "javascript:alert(1)",
        "data:text/html,hi",
        "/relative/path",
        "",
        None,
        "https://admin.example.com:notaport/",
    ],
)
def test_other_targets_fall_back_to_the_default(url):
    assert not is_allowed_redirect(url, ALLOWED)
    assert safe_redirect(url, ALLOWED, "https://admin.example.com/") == (
        "https://admin.example.com/"
    )


def test_origin_normalises_case_and_default_ports():
    assert origin_of("HTTPS://Admin.Example.com:443/x") == "https://admin.example.com"
    assert origin_of("http://localhost:3000/x") == "http://localhost:3000"
    assert origin_of("http://localhost:80/") == "http://localhost"


def _service(origins, response):
    service = AuthService.__new__(AuthService)
    service.allowed_origins_repo = SimpleNamespace(
        list_origins=AsyncMock(return_value=origins)
    )
    service.http_client = SimpleNamespace(get=AsyncMock(return_value=response))
    service.user_tags_service = SimpleNamespace(add_user_tag=AsyncMock())
    return service


async def test_sign_in_returns_to_an_allowed_page(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CLIENT_URL", "https://admin.example.com")
    service = _service(
        ["https://forms.acme-custom.org"],
        {"client_referer_url": "https://forms.acme-custom.org/f/1"},
    )
    _, url = await service.basic_auth_callback("google", "code", "state")
    assert url == "https://forms.acme-custom.org/f/1"


async def test_the_client_url_is_always_allowed(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CLIENT_URL", "https://admin.example.com")
    service = _service([], {"client_referer_url": "https://admin.example.com/login"})
    _, url = await service.basic_auth_callback("google", "code", "state")
    assert url == "https://admin.example.com/login"


@pytest.mark.parametrize(
    "referer", ["https://evil.example/x", "//evil.example", None, ""]
)
async def test_sign_in_never_redirects_off_site(monkeypatch, referer):
    monkeypatch.setattr(settings.api_settings, "CLIENT_URL", "https://admin.example.com/")
    service = _service([], {"client_referer_url": referer})
    _, url = await service.basic_auth_callback("google", "code", "state")
    assert url == "https://admin.example.com/"


async def test_a_refused_sign_in_off_site_goes_to_our_login_page(monkeypatch):
    monkeypatch.setattr(settings.api_settings, "CLIENT_URL", "https://admin.example.com")
    service = _service(
        [],
        {
            "client_referer_url": "https://evil.example/login",
            "error": "unverified_email",
        },
    )
    _, url = await service.basic_auth_callback("google", "code", "state")
    parts = urlsplit(url)
    assert (parts.scheme, parts.netloc, parts.path) == (
        "https",
        "admin.example.com",
        "/login",
    )
    assert parse_qs(parts.query)["login_error"] == ["unverified_email"]
