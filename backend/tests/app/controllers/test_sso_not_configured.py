"""Single sign-on switched on but not fully set up (docs/sso.md): the overview
says so (``reason: "not_configured"``), a refused call says so, and the startup
log names the missing settings. No setting value ever appears."""

import pytest
from common.models.user import User
from common.settings import sso_requirements
from loguru import logger

from backend.app.services.sso import startup
from backend.config import settings
from tests.app.auth_helpers import access_token
from tests.app.controllers.data import testUser
from tests.app.sso_helpers import SAML_XML, sso_on  # noqa: F401 — fixtures

# values that must never reach a reply or a log line
URL_VALUE = "https://polis-secret-host.example.net"
REDIRECT_VALUE = "https://redirect-secret-host.example.net/cb"
KEY_VALUE = "key-value-never-shown-5f1c"
VALUES = (URL_VALUE, REDIRECT_VALUE, KEY_VALUE, "polis-secret-host", "5f1c")


def _cookies(user: User) -> dict:
    token = access_token(user)
    return {"Authorization": token, "RefreshToken": token}


def sso_url(workspace, suffix=""):
    return f"/api/v1/workspaces/{workspace.id}/sso{suffix}"


def scim_url(workspace):
    return f"/api/v1/workspaces/{workspace.id}/scim"


def _set(monkeypatch, **values):
    sso = settings.sso
    base = {
        "ENABLED": False,
        "POLIS_URL": "",
        "POLIS_INTERNAL_URL": "",
        "POLIS_API_KEY": "",
        "REDIRECT_URI": "",
    }
    for key, value in {**base, **values}.items():
        monkeypatch.setattr(sso, key, value)


@pytest.fixture
def half_set_up(monkeypatch):
    """Switched on with the URLs set but no API key (values set, so a leak shows)."""
    _set(monkeypatch, ENABLED=True, POLIS_URL=URL_VALUE, REDIRECT_URI=REDIRECT_VALUE)


@pytest.fixture
def only_switched_on(monkeypatch):
    _set(monkeypatch, ENABLED=True)


def _no_values(text: str) -> None:
    for value in VALUES:
        assert value not in text


# -- settings -----------------------------------------------------------------
def test_missing_settings_and_status(monkeypatch):
    _set(monkeypatch)
    assert settings.sso.status == "disabled"
    assert settings.sso.is_configured is False

    _set(monkeypatch, ENABLED=True)
    assert settings.sso.missing_settings == (
        "SSO_POLIS_URL",
        "SSO_POLIS_API_KEY",
        "SSO_REDIRECT_URI",
    )
    assert settings.sso.status == "not_configured"

    _set(monkeypatch, ENABLED=True, POLIS_URL=URL_VALUE, REDIRECT_URI="  ")
    assert settings.sso.missing_settings == ("SSO_POLIS_API_KEY", "SSO_REDIRECT_URI")

    # the internal URL is not required: it falls back to the public one
    _set(
        monkeypatch, ENABLED=True, POLIS_URL=URL_VALUE, POLIS_API_KEY=KEY_VALUE,
        REDIRECT_URI=REDIRECT_VALUE,
    )
    assert settings.sso.missing_settings == ()
    assert settings.sso.status is None
    assert settings.sso.is_configured is True


def test_requirements_are_names_only():
    for service, names in sso_requirements.REQUIRED.items():
        assert names and all(n.startswith("SSO_") and n.isupper() for n in names)
    assert "SSO_POLIS_INTERNAL_URL" not in sso_requirements.REQUIRED["backend"]
    assert sso_requirements.OPTIONAL["auth"] == ("SSO_POLIS_CLIENT_SECRET",)


# -- overview -----------------------------------------------------------------
async def test_overview_says_not_configured(client, workspace, half_set_up):
    reply = await client.get(sso_url(workspace), cookies=_cookies(testUser))

    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["available"] is False
    assert body["reason"] == "not_configured"
    assert body["serviceProvider"] is None
    _no_values(reply.text)
    # nor the names: the workspace page is for workspace admins, not operators
    assert "SSO_POLIS" not in reply.text


async def test_overview_says_disabled_when_off(client, workspace, monkeypatch):
    _set(monkeypatch, POLIS_URL=URL_VALUE, POLIS_API_KEY=KEY_VALUE, REDIRECT_URI=REDIRECT_VALUE)
    reply = await client.get(sso_url(workspace), cookies=_cookies(testUser))
    body = reply.json()
    assert body["available"] is False
    assert body["reason"] == "disabled"
    _no_values(reply.text)


async def test_overview_has_no_reason_when_available(client, workspace, sso_on):
    body = (await client.get(sso_url(workspace), cookies=_cookies(testUser))).json()
    assert body["available"] is True
    assert body["reason"] is None


async def test_a_refused_call_says_not_fully_set_up(client, workspace, half_set_up):
    reply = await client.post(
        sso_url(workspace, "/connections"),
        json={"type": "saml", "metadataXml": SAML_XML},
        cookies=_cookies(testUser),
    )
    assert reply.status_code == 404
    # the code clients key on stays the same; the message is honest
    assert reply.json()["code"] == "sso_disabled"
    assert "not fully set up" in reply.text
    _no_values(reply.text)


async def test_scim_overview_says_not_configured(client, workspace, only_switched_on):
    reply = await client.get(scim_url(workspace), cookies=_cookies(testUser))
    assert reply.status_code == 200, reply.text
    assert reply.json()["available"] is False
    assert reply.json()["reason"] == "not_configured"


async def test_scim_overview_says_disabled_when_sso_is_off(client, workspace, monkeypatch):
    _set(monkeypatch)
    reply = await client.get(scim_url(workspace), cookies=_cookies(testUser))
    assert reply.json()["reason"] == "disabled"


# -- startup log --------------------------------------------------------------
@pytest.fixture
def log_lines():
    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="DEBUG", format="{level} {message}")
    yield lines
    logger.remove(sink)


def test_startup_log_names_missing_settings_only(half_set_up, log_lines):
    assert startup.log_if_sso_incomplete() is False
    text = "\n".join(log_lines)
    assert "WARNING" in text
    # only the one that is missing; the set ones are not listed
    assert "missing SSO_POLIS_API_KEY." in text
    assert "SSO_POLIS_URL" not in text and "SSO_REDIRECT_URI" not in text
    _no_values(text)


def test_startup_log_quiet_when_off_or_complete(monkeypatch, log_lines):
    _set(monkeypatch, POLIS_URL=URL_VALUE)
    assert startup.log_if_sso_incomplete() is True
    _set(
        monkeypatch, ENABLED=True, POLIS_URL=URL_VALUE, POLIS_API_KEY=KEY_VALUE,
        REDIRECT_URI=REDIRECT_VALUE,
    )
    assert startup.log_if_sso_incomplete() is True
    assert not [line for line in log_lines if "SSO_ENABLED" in line]
