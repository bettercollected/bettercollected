"""Fixtures and helpers for the portal tests (sessions, sign-in, gate levels 2-4).

Imported into ``conftest.py`` so the fixtures are visible to every admin test.
"""

from __future__ import annotations

import re
from http.cookies import SimpleCookie

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport

from backend.admin.asgi import get_admin_application
from backend.admin.config import MASTER_KEY_KEY
from backend.admin.gate.settings import GateSettings
from backend.admin.portal import Portal
from backend.admin.portal_config import PortalSettings
from backend.admin.security.clock import FakeClock
from backend.admin.security.mailer import AdminMailer, FakeTransport

HOST = "localhost:8100"
ORIGIN = "https://localhost:8100"
ADMIN = "admin@example.org"
OTHER_ADMIN = "second@example.org"
UA = "test-agent/1.0"
PEER = "127.0.0.1"
CODE_RE = re.compile(r"\b(\d{8})\b")
TOKEN_RE = re.compile(r'name="csrf_token" value="([^"]+)"')


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def transport():
    return FakeTransport()


def portal_settings(admins=(ADMIN, OTHER_ADMIN)) -> PortalSettings:
    return PortalSettings(admin_emails=frozenset(admins), public_origins=(ORIGIN,))


@pytest.fixture
def make_portal(runtime_engine, clock, transport, master_key):
    def build(admins=(ADMIN, OTHER_ADMIN)) -> Portal:
        return Portal.build(
            runtime_engine,
            env={MASTER_KEY_KEY: master_key},
            clock=clock,
            mailer=AdminMailer.for_transport(transport),
            settings=portal_settings(admins),
        )

    return build


@pytest.fixture
def portal(make_portal):
    return make_portal()


def make_app(portal: Portal):
    return get_admin_application(GateSettings.from_env({}), portal=portal)


@pytest.fixture
def app(portal):
    return make_app(portal)


class Browser:
    """A tiny cookie-keeping client over the ASGI app (no network, no jar quirks)."""

    def __init__(self, app, peer: str = PEER, ua: str = UA) -> None:
        self.http = httpx.AsyncClient(
            transport=ASGITransport(app=app, client=(peer, 40000)), base_url=ORIGIN
        )
        self.cookies: dict = {}
        self.ua = ua
        self.set_cookie_lines: list = []

    async def request(self, method, path, *, origin=ORIGIN, headers=None, **kw):
        h = {"user-agent": self.ua}
        if origin:
            h["origin"] = origin
        if self.cookies:
            h["cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        h.update(headers or {})
        response = await self.http.request(method, path, headers=h, **kw)
        for line in response.headers.get_list("set-cookie"):
            self.set_cookie_lines.append(line)
            jar = SimpleCookie()
            jar.load(line)
            for name, morsel in jar.items():
                if morsel["max-age"] == "0":
                    self.cookies.pop(name, None)
                else:
                    self.cookies[name] = morsel.value
        return response

    async def get(self, path, **kw):
        return await self.request("GET", path, **kw)

    async def post(self, path, **kw):
        return await self.request("POST", path, **kw)

    async def form_token(self, path="/login") -> str:
        response = await self.get(path)
        return TOKEN_RE.search(response.text).group(1)

    async def request_code(self, email, **kw):
        token = await self.form_token("/login")
        return await self.post("/login", data={"email": email, "csrf_token": token}, **kw)

    async def submit_code(self, code, **kw):
        token = await self.form_token("/login/code")
        return await self.post("/login/code", data={"code": code, "csrf_token": token}, **kw)

    async def aclose(self):
        await self.http.aclose()


@pytest_asyncio.fixture(loop_scope="session")
async def browser(app):
    b = Browser(app)
    yield b
    await b.aclose()


def last_code(transport: FakeTransport) -> str:
    return CODE_RE.search(transport.sent[-1].body).group(1)


async def sign_in(b: Browser, transport: FakeTransport, email: str = ADMIN) -> str:
    """Full email-code sign-in; returns the session cookie value."""
    await b.request_code(email)
    response = await b.submit_code(last_code(transport))
    assert response.status_code == 303 and response.headers["location"] == "/mfa"
    return b.cookies["__Host-bcadmin"]
