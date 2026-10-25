"""The key-only internal routes stay off the public ingress
(services/internal_routes.py).

The gate runs before the key: a refused request is a 404, and one that gets
through meets the key check (403 for the wrong key here). So "404" means
refused at the edge and "403" means it reached the key."""

import socket
from unittest.mock import patch

import httpx
import pytest
import pytest_asyncio

from backend.app.controllers.admin_tasks_router import KEY_HEADER
from backend.app.services import internal_routes
from backend.config import settings

KEY = "internal-routes-test-key"
OID = "65a000000000000000000001"

# (method, path, kwargs): every route only the services inside the stack call
WORKER_ROUTES = [
    ("POST", "/api/v1/temporal/delete/submissions/s1", {}),
    ("PATCH", f"/api/v1/temporal/forms/{OID}/actions/{OID}/secrets", {"json": {}}),
    ("PATCH", f"/api/v1/workspaces/{OID}/forms/{OID}/action/{OID}/update", {}),
    ("PATCH", f"/api/v1/template/{OID}/preview", {}),
    ("DELETE", "/api/v1/auth/user", {}),
]
ADMIN_TASK_ROUTES = [
    ("GET", "/api/v1/internal/admin-tasks/case-duplicate-accounts", {}),
    ("POST", f"/api/v1/internal/admin-tasks/case-duplicate-accounts/{OID}/drop", {}),
]
WRONG_KEYS = {"api-key": "wrong", KEY_HEADER: "wrong"}

PROXY_HEADER_SAMPLES = [
    {"X-Forwarded-For": "203.0.113.9"},
    {"X-Forwarded-For": "10.0.0.2"},
    {"X-Real-IP": "203.0.113.9"},
    {"Forwarded": "for=203.0.113.9;proto=https"},
    {"X-Forwarded-Proto": "https"},
    {"X-Forwarded-Host": "api.example.test"},
    {"CF-Connecting-IP": "203.0.113.9"},
    {"True-Client-IP": "203.0.113.9"},
    {"Via": "1.1 proxy"},
    # vendor client-address headers, in any case
    {"X-Envoy-External-Address": "203.0.113.9"},
    {"x-azure-clientip": "203.0.113.9"},
    {"X-CLUSTER-CLIENT-IP": "203.0.113.9"},
    {"x-client-ip": "203.0.113.9"},
    {"Fastly-Client-IP": "203.0.113.9"},
    {"X-Original-Forwarded-For": "203.0.113.9"},
]


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setattr(settings.temporal_settings, "api_key", KEY)
    monkeypatch.setattr(settings, "ADMIN_TASKS_API_KEY", KEY)
    monkeypatch.delenv("API_INTERNAL_PORT", raising=False)
    monkeypatch.delenv("API_INTERNAL_ROUTES", raising=False)
    monkeypatch.delenv("PORT", raising=False)


def _client(app, peer: str, port: int):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=(peer, 40000)),
        base_url=f"http://backend:{port}",
    )


@pytest_asyncio.fixture(loop_scope="session")
async def make(_initialized_app):
    opened = []

    def _make(peer: str = "172.18.0.5", port: int = 8000):
        c = _client(_initialized_app, peer, port)
        opened.append(c)
        return c

    yield _make
    for c in opened:
        await c.aclose()


async def _call(client, route, headers=None):
    method, path, kwargs = route
    return await client.request(
        method, path, headers={**WRONG_KEYS, **(headers or {})}, **kwargs
    )


# ------------------------------------------------------------ proxied
@pytest.mark.parametrize("route", WORKER_ROUTES + ADMIN_TASK_ROUTES)
@pytest.mark.parametrize("port", [8000, 8001])
async def test_a_proxied_request_is_refused_on_every_port(make, route, port):
    client = make(peer="172.18.0.7", port=port)
    for headers in PROXY_HEADER_SAMPLES:
        reply = await _call(client, route, headers)
        assert reply.status_code == 404, (headers, reply.text)
        assert reply.json() == {"detail": "Not Found"}


async def test_refused_before_the_key_and_even_with_the_right_one(make):
    client = make(peer="172.18.0.7", port=8000)
    reply = await client.post(
        "/api/v1/temporal/delete/submissions/s1",
        headers={"api-key": KEY, "X-Forwarded-For": "203.0.113.9"},
    )
    assert reply.status_code == 404
    # unknown path and refused internal route look the same
    unknown = await client.post("/api/v1/temporal/no-such-route")
    assert reply.json() == unknown.json()


# ---------------------------------------------------------- the worker routes
@pytest.mark.parametrize("route", WORKER_ROUTES)
async def test_direct_mode_takes_in_network_requests_on_the_public_port(make, route):
    for peer in ("127.0.0.1", "172.18.0.5", "10.0.3.4", "192.168.1.2", "::1", "fd00::5"):
        reply = await _call(make(peer=peer, port=8000), route)
        assert reply.status_code == 403, (peer, reply.text)


@pytest.mark.parametrize("route", WORKER_ROUTES)
async def test_direct_mode_refuses_a_public_peer_on_the_public_port(make, route):
    for peer in ("203.0.113.9", "8.8.8.8", "2001:db8::1", "testclient", ""):
        reply = await _call(make(peer=peer, port=8000), route)
        assert reply.status_code == 404, (peer, reply.text)


@pytest.mark.parametrize("route", WORKER_ROUTES)
async def test_internal_port_mode_takes_only_the_internal_listener(make, monkeypatch, route):
    monkeypatch.setenv("API_INTERNAL_ROUTES", "internal_port")
    assert (await _call(make(peer="172.18.0.5", port=8000), route)).status_code == 404
    assert (await _call(make(peer="127.0.0.1", port=8000), route)).status_code == 404
    # an ingress-mesh source (Swarm rewrites outside clients to the overlay)
    assert (await _call(make(peer="10.0.0.2", port=8000), route)).status_code == 404
    assert (await _call(make(peer="172.18.0.5", port=8001), route)).status_code == 403


async def test_the_right_key_on_the_internal_listener_works(make, monkeypatch):
    monkeypatch.setenv("API_INTERNAL_ROUTES", "internal_port")
    from backend.app.container import container

    with patch.object(container.form_schedular(), "delete_response", return_value="ok") as done:
        reply = await make(port=8001).post(
            "/api/v1/temporal/delete/submissions/s1", headers={"api-key": KEY}
        )
    assert reply.status_code == 200, reply.text
    done.assert_called_once_with(submission_id="s1")


# ------------------------------------------------------- the admin-task routes
@pytest.mark.parametrize("route", ADMIN_TASK_ROUTES)
@pytest.mark.parametrize("mode", ["", "direct", "internal_port"])
async def test_admin_tasks_answer_on_the_internal_listener_only(make, monkeypatch, route, mode):
    monkeypatch.setenv("API_INTERNAL_ROUTES", mode)
    for peer in ("127.0.0.1", "172.18.0.5", "203.0.113.9"):
        assert (await _call(make(peer=peer, port=8000), route)).status_code == 404
    assert (await _call(make(port=8001), route)).status_code == 403


@pytest.mark.parametrize("route", ADMIN_TASK_ROUTES + WORKER_ROUTES)
async def test_without_an_internal_listener_admin_tasks_fail_closed(make, monkeypatch, route):
    monkeypatch.setenv("API_INTERNAL_PORT", "0")
    reply = await _call(make(port=8001), route)
    if route in ADMIN_TASK_ROUTES:
        assert reply.status_code == 404
    else:  # a private peer, direct mode: still the key check
        assert reply.status_code == 403


async def test_the_internal_port_moves_with_its_setting(make, monkeypatch):
    monkeypatch.setenv("API_INTERNAL_PORT", "9123")
    route = ADMIN_TASK_ROUTES[0]
    assert (await _call(make(port=8001), route)).status_code == 404
    assert (await _call(make(port=9123), route)).status_code == 403


# ---------------------------------------------------------- public routes
async def test_public_routes_are_unaffected(make):
    for headers in ({}, {"X-Forwarded-For": "203.0.113.9", "X-Forwarded-Proto": "https"}):
        for peer in ("203.0.113.9", "172.18.0.5"):
            client = make(peer=peer, port=8000)
            reply = await client.get("/api/v1/auth/status", headers=headers)
            assert reply.status_code == 401, reply.text  # not signed in, not hidden
            reply = await client.get("/api/v1/public/v1/openapi.json", headers=headers)
            assert reply.status_code == 200


# ---------------------------------------------------------------- settings
@pytest.mark.parametrize(
    "env, port",
    [
        ({}, 8001),
        ({"API_INTERNAL_PORT": ""}, 8001),
        ({"API_INTERNAL_PORT": "9000"}, 9000),
        ({"API_INTERNAL_PORT": "0"}, 0),
        ({"API_INTERNAL_PORT": "nope"}, 0),
        ({"API_INTERNAL_PORT": "70000"}, 0),
        ({"API_INTERNAL_PORT": "-1"}, 0),
        # never the public port itself
        ({"API_INTERNAL_PORT": "8000"}, 0),
        ({"API_INTERNAL_PORT": "8001", "PORT": "8001"}, 0),
        ({"PORT": "8001"}, 0),
    ],
)
def test_internal_port(monkeypatch, env, port):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert internal_routes.internal_port() == port


@pytest.mark.parametrize(
    "raw, mode",
    [
        (None, "direct"),
        ("", "direct"),
        ("direct", "direct"),
        (" DIRECT ", "direct"),
        ("internal_port", "internal_port"),
        ("typo", "internal_port"),  # unknown: the stricter one
    ],
)
def test_mode(monkeypatch, raw, mode):
    if raw is not None:
        monkeypatch.setenv("API_INTERNAL_ROUTES", raw)
    assert internal_routes.mode().value == mode


def test_main_listens_on_both_ports(monkeypatch):
    import backend.__main__ as entry

    monkeypatch.setenv("PORT", "0")
    seen = {}

    def fake_listening_socket(port):
        seen.setdefault("ports", []).append(port)
        return socket.socket()

    def fake_run(self, sockets=None):
        seen["sockets"] = sockets

    monkeypatch.setattr(entry, "get_application", lambda: object())
    monkeypatch.setattr(entry, "_listening_socket", fake_listening_socket)
    monkeypatch.setattr(entry.uvicorn.Server, "run", fake_run)
    monkeypatch.setenv("PORT", "8000")
    entry.main()
    assert seen["ports"] == [8000, 8001]
    assert len(seen["sockets"]) == 2
    for s in seen["sockets"]:
        s.close()

    seen.clear()
    monkeypatch.setenv("API_INTERNAL_PORT", "0")
    entry.main()
    assert seen["ports"] == [8000]
    for s in seen["sockets"]:
        s.close()


@pytest.mark.parametrize("route", WORKER_ROUTES + ADMIN_TASK_ROUTES)
async def test_a_vendor_header_from_a_private_peer_is_refused(make, route):
    # a load balancer that names the client only in its own header
    for port in (8000, 8001):
        reply = await _call(
            make(peer="10.0.0.2", port=port), route, {"X-Envoy-External-Address": "198.51.100.7"}
        )
        assert reply.status_code == 404


@pytest.mark.parametrize("raw, warned", [(None, True), ("direct", True), ("internal_port", False)])
def test_direct_mode_warns_once_at_startup(monkeypatch, raw, warned):
    from loguru import logger

    if raw is not None:
        monkeypatch.setenv("API_INTERNAL_ROUTES", raw)
    monkeypatch.setattr(internal_routes, "_direct_warned", False)
    seen = []
    sink = logger.add(lambda m: seen.append(m.record), level="WARNING")
    try:
        internal_routes.log_internal_routes_setup()
        internal_routes.log_internal_routes_setup()
    finally:
        logger.remove(sink)
    hits = [r for r in seen if "API_INTERNAL_ROUTES=internal_port" in r["message"]]
    assert len(hits) == (1 if warned else 0)
    for record in hits:
        assert record["level"].name == "WARNING"
        assert "ingress mesh" in record["message"]
