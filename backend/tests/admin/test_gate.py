import ast
import json
import logging
import pathlib
import subprocess
import sys

import pytest
import yaml
from fastapi import Request
from fastapi.routing import APIRoute

from backend.admin.asgi import get_admin_application
from backend.admin.gate.levels import LEVEL_ATTR, Level, RouteRegistry
from backend.admin.gate.settings import GateConfigError, GateSettings
from backend.admin.headers import CONTENT_SECURITY_POLICY

ROOT = pathlib.Path(__file__).resolve().parents[3]
HOST = "localhost:8100"


def make_app(env=None, checkers=None, registry=None):
    return get_admin_application(GateSettings.from_env(env or {}), checkers, registry)


def make_registry(calls=None, boom=False):
    reg = RouteRegistry()

    @reg.route("/ping", level=Level.ADDRESS, methods=["GET", "POST"])
    async def ping():
        if calls is not None:
            calls.append("ping")
        if boom:
            raise RuntimeError("secret-value /tmp/trace")
        return {"ok": True}

    @reg.route("/sink", level=Level.ADDRESS, methods=["POST"])
    async def sink(request: Request):
        await request.body()
        return {}

    @reg.route("/private", level=Level.SESSION)
    async def private():
        calls.append("private")
        return {}

    return reg


async def call(
    app, path="/ping", method="GET", peer="127.0.0.1", headers=None, body=b"", host=HOST
):
    hdrs = [] if host is None else [(b"host", host.encode())]
    hdrs += [(k.lower().encode(), v.encode()) for k, v in (headers or [])]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": hdrs,
        "client": (peer, 5555) if peer else None,
        "server": ("test", 80),
        "scheme": "http",
        "http_version": "1.1",
        "root_path": "",
    }
    sent = []
    chunks = [body[i : i + 8192] for i in range(0, len(body), 8192)] or [b""]

    async def receive():
        if chunks:
            c = chunks.pop(0)
            return {"type": "http.request", "body": c, "more_body": bool(chunks)}
        return {"type": "http.disconnect"}

    async def send(m):
        sent.append(m)

    await app(scope, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    data = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], {k.decode(): v.decode() for k, v in start["headers"]}, data


JSON_CT = ("content-type", "application/json")


@pytest.fixture
def calls():
    return []


@pytest.fixture
def app(calls):
    return make_app(registry=make_registry(calls))


async def test_allowed_peer_reaches_route(app, calls):
    status, _, _ = await call(app)
    assert status == 200 and calls == ["ping"]


@pytest.mark.parametrize("xff", [None, "127.0.0.1", "127.0.0.1, 127.0.0.1"])
async def test_outside_peer_404_with_or_without_forged_xff(app, calls, xff):
    h = [("x-forwarded-for", xff)] if xff else []
    status, _, body = await call(app, peer="203.0.113.9", headers=h)
    assert status == 404 and body == b"" and calls == []


async def test_trusted_proxy_with_legit_chain_accepted(calls):
    a = make_app(
        {"ADMIN_TRUSTED_PROXIES": "10.0.0.2", "ADMIN_ALLOWED_IPS": "192.0.2.0/24"},
        registry=make_registry(calls),
    )
    assert (await call(a, peer="10.0.0.2", headers=[("x-forwarded-for", "192.0.2.7")]))[0] == 200
    # a left-most entry the client chose cannot widen it
    s = await call(a, peer="10.0.0.2", headers=[("x-forwarded-for", "192.0.2.7, 198.51.100.1")])
    assert s[0] == 404


async def test_untrusted_private_peer_cannot_spoof(calls):
    a = make_app({"ADMIN_ALLOWED_IPS": "192.0.2.0/24"}, registry=make_registry(calls))
    for peer in ("10.0.0.2", "172.17.0.5", "192.168.1.1"):
        s = await call(a, peer=peer, headers=[("x-forwarded-for", "192.0.2.7")])
        assert s[0] == 404
    assert calls == []


async def test_garbage_and_oversized_chains_refused(calls):
    a = make_app(
        {"ADMIN_TRUSTED_PROXIES": "10.0.0.2", "ADMIN_ALLOWED_IPS": "192.0.2.0/24"},
        registry=make_registry(calls),
    )
    for xff in ("192.0.2.7, not-an-ip", "x" * 5000, "," * 100):
        s = await call(a, peer="10.0.0.2", headers=[("x-forwarded-for", xff)])
        assert s[0] == 404


async def test_ipv6_and_mapped(calls):
    a = make_app(
        {"ADMIN_ALLOWED_IPS": "127.0.0.1/32,2001:db8::/32"}, registry=make_registry(calls)
    )
    assert (await call(a, peer="2001:db8::1"))[0] == 200
    assert (await call(a, peer="::ffff:127.0.0.1"))[0] == 200
    assert (await call(a, peer="2001:db9::1"))[0] == 404
    assert (await call(a, peer="::1"))[0] == 404
    assert (await call(a, peer=None))[0] == 404
    assert (await call(a, peer="garbage"))[0] == 404


async def test_edge_gateway_added():
    a = make_app({"ADMIN_EDGE_GATEWAY": "172.30.77.1"}, registry=make_registry([]))
    assert (await call(a, peer="172.30.77.1"))[0] == 200
    assert (await call(a, peer="172.30.77.2"))[0] == 404


@pytest.mark.parametrize(
    "host", ["evil.example", "localhost", "localhost:8100.evil.example", None]
)
async def test_host_rebinding(app, calls, host):
    assert (await call(app, host=host))[0] == 404 and calls == []


async def test_gate_order_denied_never_reaches_later_code(calls):
    seen = []

    async def checker(scope):
        seen.append(1)
        return True

    a = make_app(checkers={Level.SESSION: checker}, registry=make_registry(calls))
    for kw in ({"peer": "203.0.113.9"}, {"host": "evil.example"}):
        await call(a, path="/private", **kw)
    assert seen == [] and calls == []
    assert (await call(a, path="/private"))[0] == 200 and seen == [1]


async def test_levels_without_checker_are_denied(app, calls):
    assert (await call(app, path="/private"))[0] == 404 and calls == []


async def test_unknown_route_and_method_404(app):
    assert (await call(app, path="/login"))[0] == 404
    assert (await call(app, path="/ping", method="DELETE"))[0] == 404
    assert (await call(app, path="/docs"))[0] == 404
    assert (await call(app, path="/openapi.json"))[0] == 404


async def test_healthz_loopback_only(app):
    s, _, body = await call(app, path="/healthz", host=None)
    assert (s, body) == (200, b"ok")
    assert (await call(app, path="/healthz", peer="::1", host="x"))[0] == 200
    assert (await call(app, path="/healthz", peer="172.30.77.1"))[0] == 404
    assert (await call(app, path="/healthz", peer="203.0.113.9"))[0] == 404
    assert (await call(app, path="/healthz", method="POST"))[0] == 404


async def test_healthz_answers_the_edge_gateway_only_when_configured():
    a = make_app({"ADMIN_EDGE_GATEWAY": "172.30.77.1"}, registry=make_registry())
    s, _, body = await call(a, path="/healthz", peer="172.30.77.1", host=HOST)
    assert (s, body) == (200, b"ok")
    # only that exact address, and only GET/HEAD: not its neighbours (siblings), not other networks
    for peer in ("172.30.77.2", "172.30.77.3", "172.17.0.1", "203.0.113.9"):
        assert (await call(a, path="/healthz", peer=peer, host=HOST))[0] == 404
    assert (await call(a, path="/healthz", peer="172.30.77.1", method="POST"))[0] == 404
    # the gateway gets the same address allowlist as everything else
    assert (await call(a, path="/ping", peer="172.30.77.1", host=HOST))[0] == 200


def test_registry_requires_level():
    reg = RouteRegistry()
    with pytest.raises(TypeError):
        reg.route("/x")  # level is required
    with pytest.raises(ValueError):
        reg.route("/x", level=Level.NETWORK)
    with pytest.raises(ValueError):
        reg.route("/healthz", level=Level.ADDRESS)


def test_route_table_default_deny(calls):
    from backend.admin.asgi import registry as shared

    for application in (make_app(registry=make_registry(calls)), make_app()):
        for route in application.inner.routes:
            assert isinstance(route, APIRoute), f"unregistered route {route.path}"
            assert isinstance(getattr(route.endpoint, LEVEL_ATTR, None), Level), route.path
    for route in shared.router.routes:
        assert isinstance(getattr(route.endpoint, LEVEL_ATTR), Level)


async def test_route_without_level_is_denied(calls):
    reg = RouteRegistry()

    async def sneaky():
        calls.append("sneaky")

    reg.router.add_api_route("/sneaky", sneaky)
    a = make_app(registry=reg)
    assert (await call(a, path="/sneaky"))[0] == 404 and calls == []


async def test_body_cap_and_content_type(app):
    ok = [JSON_CT, ("content-length", "2")]
    assert (await call(app, method="POST", headers=ok, body=b"{}"))[0] == 200
    big = b"a" * (64 * 1024 + 1)
    declared = [JSON_CT, ("content-length", str(len(big)))]
    assert (await call(app, path="/sink", method="POST", headers=declared, body=big))[0] == 413
    # an undeclared length is capped while streaming
    chunked = [JSON_CT, ("transfer-encoding", "chunked")]
    assert (await call(app, path="/sink", method="POST", headers=chunked, body=big))[0] == 413
    text = [("content-type", "text/plain"), ("content-length", "2")]
    assert (await call(app, method="POST", headers=text, body=b"hi"))[0] == 415
    assert (await call(app, method="POST", headers=[("content-length", "2")], body=b"hi"))[0] == 415
    form = [("content-type", "application/x-www-form-urlencoded; charset=utf-8"), ("content-length", "1")]
    assert (await call(app, method="POST", headers=form, body=b"a"))[0] == 200
    assert (await call(app, method="POST", headers=[("content-length", "abc")]))[0] == 400


async def test_headers_on_every_response_and_no_cors():
    a = make_app(registry=make_registry([], boom=True))
    big = b"a" * (64 * 1024 + 1)
    responses = [
        await call(
            make_app(registry=make_registry([])),
            headers=[("origin", "https://evil.example")],
        ),
        await call(a, path="/nope"),
        await call(a, peer="203.0.113.9"),
        await call(a, path="/healthz", host=None),
        await call(
            a, method="POST", headers=[JSON_CT, ("content-length", str(len(big)))], body=big
        ),
        await call(a),  # forced 500
    ]
    assert [r[0] for r in responses] == [200, 404, 404, 200, 413, 500]
    for _, h, _ in responses:
        assert h["content-security-policy"] == CONTENT_SECURITY_POLICY
        assert h["referrer-policy"] == "same-origin"
        assert h["x-content-type-options"] == "nosniff"
        assert h["cache-control"] == "no-store"
        assert h["cross-origin-opener-policy"] == "same-origin"
        assert h["cross-origin-resource-policy"] == "same-origin"
        assert h["permissions-policy"] == ""
        assert h["x-request-id"]
        assert not any(k.startswith("access-control-") for k in h)
        assert "server" not in h
    assert "default-src 'none'" in CONTENT_SECURITY_POLICY
    assert responses[5][2] == b""  # no trace, no secret
    assert len({r[1]["x-request-id"] for r in responses}) == len(responses)


async def test_preflight_gets_no_cors(app):
    s, h, _ = await call(
        app,
        method="OPTIONS",
        headers=[
            ("origin", "https://evil.example"),
            ("access-control-request-method", "POST"),
        ],
    )
    assert s == 404 and not any(k.startswith("access-control-") for k in h)


async def test_denial_log_is_sanitised_and_limited(app, caplog):
    caplog.set_level(logging.WARNING, logger="backend.admin.gate")
    evil = "1.2.3.4\r\nFAKE LOG LINE" + "z" * 500
    for _ in range(50):
        await call(app, peer="203.0.113.9", headers=[("x-forwarded-for", evil)])
    lines = [r.getMessage() for r in caplog.records]
    assert 1 <= len(lines) <= 5
    assert all("\n" not in x and "\r" not in x and len(x) < 700 for x in lines)
    assert "reason=address" in lines[0] and "203.0.113.9" in lines[0]


@pytest.mark.parametrize(
    "env",
    [
        {"ADMIN_ALLOWED_IPS": "nope"},
        {"ADMIN_ALLOWED_IPS": "0.0.0.0/0"},
        {"ADMIN_ALLOWED_IPS": "::/0"},
        {"ADMIN_TRUSTED_PROXIES": "10.0.0.0/33"},
        {"ADMIN_EDGE_GATEWAY": "x"},
        {"ADMIN_PORT": "0"},
        {"ADMIN_PORT": "abc"},
        {"ADMIN_ALLOWED_HOSTS": "a/b"},
    ],
)
def test_invalid_settings_fail_loudly(env):
    with pytest.raises(GateConfigError):
        GateSettings.from_env(env)


def test_default_settings():
    s = GateSettings.from_env({})
    assert s.allowed_hosts == ("localhost:8100", "127.0.0.1:8100")
    assert s.trusted_proxies == ""
    assert [str(n) for n in s.allowed_ips] == ["127.0.0.1/32"]
    assert GateSettings.from_env({"ADMIN_PORT": "9000"}).allowed_hosts[0] == "localhost:9000"


# ---- isolation from the public app -------------------------------------------------

FORBIDDEN = (
    "backend.app.router",
    "backend.app.container",
    "backend.app.controllers",
    "common.services.crypto_service",
)


def test_public_app_has_no_admin_routes():
    from backend.app.asgi import get_application

    paths = {getattr(r, "path", "") for r in get_application().routes}
    assert "/healthz" not in paths
    assert not [p for p in paths if "admin-service" in p or p.startswith("/admin")]


def _imports(path):
    for n in ast.walk(ast.parse(path.read_text())):
        if isinstance(n, ast.Import):
            yield from (a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            yield n.module
            yield from (f"{n.module}.{a.name}" for a in n.names)


def test_admin_package_imports_ast():
    for f in (ROOT / "backend/backend/admin").rglob("*.py"):
        for name in _imports(f):
            assert not name.startswith(FORBIDDEN), f"{f} imports {name}"


def test_admin_import_pulls_in_no_public_modules():
    code = (
        "import sys, backend.admin.asgi, backend.admin.serve;"
        f"bad=[m for m in sys.modules if m.startswith({FORBIDDEN!r})];"
        "print(','.join(bad)); sys.exit(1 if bad else 0)"
    )
    r = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=ROOT / "backend",
    )
    assert r.returncode == 0, r.stdout + r.stderr


# ---- deployment properties ---------------------------------------------------------


def _compose():
    return yaml.safe_load((ROOT / "docker-compose.deployment.yml").read_text())


def test_compose_admin_service():
    c = _compose()
    admin = c["services"]["admin"]
    assert all(p.startswith("127.0.0.1:") for p in admin["ports"])
    assert "env_file" not in admin
    assert admin["read_only"] is True and admin["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in admin["security_opt"]
    assert str(admin["user"]).split(":")[0] not in ("0", "root")
    assert "/tmp" in json.dumps(admin["tmpfs"]) and "healthcheck" in admin
    env = admin["environment"]
    # no other service's secrets; its own database password, master key and mail
    # password only as substitutions from the root .env, never literal values
    assert not any(k in json.dumps(env) for k in ("MONGO", "KEYSET", "AUTH_", "JWT"))
    for key in ("SETTINGS_MASTER_KEY", "MAIL_PASSWORD", "ADMIN_DATABASE_URL"):
        assert "${" in env[key], key
    assert "BC_ADMIN_MIG_PASSWORD" not in json.dumps(env)
    assert "bc_admin:" in env["ADMIN_DATABASE_URL"] and "bc_admin_mig" not in env["ADMIN_DATABASE_URL"]
    # the portal's optional settings default to empty (bare-gate mode), so
    # `docker compose config` works for stacks that never ran the new deploy.sh
    for key in ("SETTINGS_MASTER_KEY", "PLATFORM_ADMIN_EMAILS"):
        assert env[key].startswith("${" + key + ":-"), key
    for key in ("ADMIN_PUBLIC_ORIGINS", "ADMIN_ALLOWED_HOSTS", "ADMIN_EDGE_GATEWAY"):
        assert key in env


def test_compose_admin_networks():
    c = _compose()
    services = c["services"]

    def on(net):
        return sorted(n for n, s in services.items() if net in (s.get("networks") or []))

    # the published port rides the pinned edge network, and only admin is on it
    assert on("admin-edge") == ["admin"]
    assert "admin-edge" in c["networks"]
    # the database path is a separate internal network shared by exactly two services
    assert on("admin-db") == ["admin", "app-postgres"]
    assert c["networks"]["admin-db"]["internal"] is True
    # admin is not on the default network, so no sibling container can reach it
    assert list(services["admin"]["networks"]) == ["admin-edge", "admin-db"]
    assert "default" in services["app-postgres"]["networks"]
    assert not services["app-postgres"].get("ports")
    assert not any("admin" in str(s.get("networks", "")) for n, s in services.items()
                   if n not in ("admin", "app-postgres"))


def test_admin_not_in_nginx_conf():
    confs = list(ROOT.glob("nginx*.conf"))
    assert confs
    for conf in confs:
        text = conf.read_text().lower()
        assert "http://admin" not in text and "8100" not in text
