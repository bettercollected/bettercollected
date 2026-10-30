"""ADMIN_TRUSTED_PROXIES by host name: parsing, resolution, the gate."""

import asyncio
import ipaddress
import logging
import socket
import threading

import pytest
from fastapi import Request

from backend.admin.asgi import get_admin_application, warn_shared_gateway
from backend.admin.gate import proxies as proxies_module
from backend.admin.gate.levels import Level, RouteRegistry
from backend.admin.gate.proxies import (
    MAX_ADDRESSES_PER_NAME,
    STALE_GRACE_SECONDS,
    ProxySnapshot,
    TrustedProxies,
    proxy_address_ok,
    system_resolver,
    valid_host_name,
)
from backend.admin.gate.settings import GateConfigError, GateSettings
from tests.admin.test_gate import call, make_registry

PROXY = "10.0.0.5"
MOVED = "10.0.0.9"
ENV = {"ADMIN_TRUSTED_PROXIES": "edge-proxy", "ADMIN_ALLOWED_IPS": "192.0.2.0/24"}
XFF = [("x-forwarded-for", "192.0.2.7")]


class FakeDns:
    """A resolver whose answers the test changes; a list of addresses, or an
    exception to fail with."""

    def __init__(self, **answers):
        self.answers = answers
        self.calls = []

    async def __call__(self, name):
        self.calls.append(name)
        answer = self.answers[name.replace("-", "_")]
        if isinstance(answer, BaseException):
            raise answer
        return answer


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def proxies(dns, *networks, names=("edge-proxy",), clock=None, **kw):
    return TrustedProxies(
        [ipaddress.ip_network(n) for n in networks],
        names,
        resolver=dns,
        clock=clock or Clock(),
        **kw,
    )


def specs(snapshot):
    return sorted(str(n) for n in snapshot.networks)


# ---------------------------------------------------------------- parsing


def test_names_addresses_and_cidrs_mix():
    s = GateSettings.from_env(
        {"ADMIN_TRUSTED_PROXIES": "10.0.0.2, Edge-Proxy ,fd00::/8,proxy.internal,edge-proxy"}
    )
    assert s.trusted_proxies == "10.0.0.2/32,fd00::/8"
    assert s.trusted_proxy_names == ("edge-proxy", "proxy.internal")


def test_ip_only_settings_are_unchanged():
    s = GateSettings.from_env({"ADMIN_TRUSTED_PROXIES": "10.0.0.2,10.1.0.0/16"})
    assert s.trusted_proxies == "10.0.0.2/32,10.1.0.0/16"
    assert s.trusted_proxy_names == ()
    assert GateSettings.from_env({}).trusted_proxy_names == ()


@pytest.mark.parametrize(
    "entry",
    [
        "http://proxy",
        "https://proxy.example",
        "proxy:8080",
        "proxy.example:443",
        "proxy/path",
        "proxy/24",
        "*.example.com",
        "*",
        "pro xy",
        "user@proxy",
        "-proxy",
        "proxy-",
        "proxy.",
        ".proxy",
        "proxy..example",
        "a" * 64,
        ".".join(["a" * 60] * 5),
        "proxy_nginx:80",
        "proxy_nginx/path",
        "*_proxy",
        "proxy.-a",
        "a-.proxy",
        "-.proxy",
        "proxy_-",
        "-_proxy",
        "stack_123.456",
        "pröxy",
        "10.0.0",  # an address missing a part
        "300.1.1.1",  # an address out of range
        "1.2.3",
        "1.2.3.4.5",
        "0x7f000001",  # a number the resolver would read as an address
        "2130706433",
        "proxy.123",
        "10.0.0.0/33",
        "10.0.0.0/",
        "::/0",
        "0.0.0.0/0",
        "[::1]",
        "::g",
    ],
)
def test_invalid_entries_stop_startup(entry):
    with pytest.raises(GateConfigError):
        GateSettings.from_env({"ADMIN_TRUSTED_PROXIES": entry})
    with pytest.raises(GateConfigError):  # also when mixed with a good one
        GateSettings.from_env({"ADMIN_TRUSTED_PROXIES": f"10.0.0.2,{entry}"})


@pytest.mark.parametrize(
    "name",
    [
        "proxy",
        "edge-proxy",
        "a",
        "proxy.internal",
        "p1.example.com",
        "xn--bcher-kva.example",
        "proxy_nginx",  # Swarm: <stack>_<service>
        "tasks.proxy_nginx",
        "stack_proxy_1",
        "_proxy",
        "proxy_",
        "a_b-c",
        "a" * 63,
    ],
)
def test_valid_host_names(name):
    assert valid_host_name(name)


def test_stack_prefixed_names_are_kept_as_written():
    s = GateSettings.from_env({"ADMIN_TRUSTED_PROXIES": "Proxy_Nginx,tasks.proxy_nginx"})
    assert s.trusted_proxy_names == ("proxy_nginx", "tasks.proxy_nginx")


def test_too_many_names():
    many = ",".join(f"proxy{i}" for i in range(17))
    with pytest.raises(GateConfigError):
        GateSettings.from_env({"ADMIN_TRUSTED_PROXIES": many})
    assert GateSettings.from_env({"ADMIN_TRUSTED_PROXIES": many.rsplit(",", 1)[0]})


@pytest.mark.parametrize(
    "value,expected",
    [(None, 60), ("", 60), ("10", 10), (" 90 ", 90), ("3600", 3600)],
)
def test_refresh_seconds(value, expected):
    env = {} if value is None else {"ADMIN_TRUSTED_PROXY_REFRESH_SECONDS": value}
    assert GateSettings.from_env(env).proxy_refresh_seconds == expected


@pytest.mark.parametrize("value", ["9", "3601", "0", "-5", "1.5", "abc", "1e2", "٣٠"])
def test_refresh_seconds_out_of_bounds_stop_startup(value):
    with pytest.raises(GateConfigError):
        GateSettings.from_env({"ADMIN_TRUSTED_PROXY_REFRESH_SECONDS": value})


# ------------------------------------------------------------ which answers


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.5",
        "10.255.255.255",
        "172.16.0.1",
        "172.18.0.3",
        "172.31.255.255",
        "192.168.1.1",
        "fc00::1",
        "fd00::5",
        "fdff:ffff::1",
    ],
)
def test_private_addresses_are_usable(address):
    assert proxy_address_ok(ipaddress.ip_address(address))


@pytest.mark.parametrize(
    "address",
    [
        # public
        "8.8.8.8",
        "2001:4860:4860::8888",
        # loopback, link-local, unspecified, multicast, reserved, broadcast
        "127.0.0.1",
        "::1",
        "169.254.1.1",
        "fe80::1",
        "0.0.0.0",
        "::",
        "224.0.0.1",
        "ff02::1",
        "240.0.0.1",
        "255.255.255.255",
        # carrier-grade NAT
        "100.64.0.1",
        "100.127.255.255",
        # transition mechanisms
        "2002:a00:1::1",  # 6to4 around a private IPv4 address
        "2002::1",
        "2001::1",  # Teredo
        "64:ff9b::a00:1",  # NAT64
        # documentation
        "192.0.2.1",
        "198.51.100.1",
        "203.0.113.1",
        "2001:db8::1",
        "3fff::1",
        # benchmarking, protocol assignments, 6to4 relay
        "198.18.0.1",
        "198.19.255.255",
        "192.0.0.1",
        "192.88.99.1",
        # just outside the private ranges
        "9.255.255.255",
        "11.0.0.1",
        "172.15.255.255",
        "172.32.0.1",
        "192.167.255.255",
        "192.169.0.1",
        "fbff::1",
        "fe00::1",
    ],
)
def test_other_addresses_are_not(address):
    assert not proxy_address_ok(ipaddress.ip_address(address))


# -------------------------------------------------------------- resolution


async def test_names_resolve_to_single_address_networks():
    dns = FakeDns(edge_proxy=[PROXY, "fd00::5"])
    p = proxies(dns, "10.1.0.0/16")
    assert specs(p.snapshot) == ["10.1.0.0/16"]  # before the first lookup: nothing from names
    await p.refresh()
    assert specs(p.snapshot) == ["10.0.0.5/32", "10.1.0.0/16", "fd00::5/128"]
    assert p.snapshot.spec == "10.1.0.0/16,10.0.0.5/32,fd00::5/128"
    assert p.snapshot.trusts(ipaddress.ip_address(PROXY))
    assert not p.snapshot.trusts(ipaddress.ip_address("10.0.0.6"))  # exactly the address
    assert not p.snapshot.trusts(None)


async def test_a_and_aaaa_answers_and_mapped_addresses():
    dns = FakeDns(edge_proxy=["10.0.0.5", "10.0.0.5", "fd00::5", "::ffff:10.0.0.7"])
    p = proxies(dns)
    await p.refresh()
    assert specs(p.snapshot) == ["10.0.0.5/32", "10.0.0.7/32", "fd00::5/128"]


async def test_a_new_address_replaces_the_old_one():
    dns = FakeDns(edge_proxy=[PROXY])
    p = proxies(dns)
    await p.refresh()
    before = p.snapshot
    dns.answers["edge_proxy"] = [MOVED]  # the container was recreated
    await p.refresh()
    assert specs(p.snapshot) == [f"{MOVED}/32"]
    assert not p.snapshot.trusts(ipaddress.ip_address(PROXY))
    assert specs(before) == [f"{PROXY}/32"]  # a set a request already holds does not change


async def test_an_unchanged_answer_keeps_the_same_snapshot():
    p = proxies(FakeDns(edge_proxy=[PROXY]))
    await p.refresh()
    first = p.snapshot
    await p.refresh()
    assert p.snapshot is first


@pytest.mark.parametrize(
    "failure", [socket.gaierror(-2, "not known"), asyncio.TimeoutError(), OSError("down"), RuntimeError("bug"), []]
)
async def test_failure_keeps_the_last_good_addresses_then_drops_them(failure):
    clock, dns = Clock(), FakeDns(edge_proxy=[PROXY])
    p = proxies(dns, clock=clock)
    await p.refresh()
    dns.answers["edge_proxy"] = failure
    clock.now += 60
    await p.refresh()
    assert specs(p.snapshot) == [f"{PROXY}/32"]  # a blip does not lock the proxy out
    clock.now += STALE_GRACE_SECONDS - 60  # exactly the grace since the last good answer
    await p.refresh()
    assert specs(p.snapshot) == [f"{PROXY}/32"]
    clock.now += 1
    await p.refresh()
    assert specs(p.snapshot) == []  # then trust narrows, never stays
    dns.answers["edge_proxy"] = [PROXY]
    await p.refresh()
    assert specs(p.snapshot) == [f"{PROXY}/32"]  # and comes back with the name


async def test_a_name_that_never_resolved_trusts_nobody():
    p = proxies(FakeDns(edge_proxy=socket.gaierror(-2, "x")), "10.1.0.0/16")
    await p.refresh()
    assert specs(p.snapshot) == ["10.1.0.0/16"]  # the configured addresses stay


async def test_failure_of_one_name_leaves_the_others():
    dns = FakeDns(edge_proxy=[PROXY], other=OSError())
    p = proxies(dns, names=("edge-proxy", "other"))
    await p.refresh()
    assert specs(p.snapshot) == [f"{PROXY}/32"]


@pytest.mark.parametrize(
    "answer",
    [
        ["8.8.8.8"],
        ["2001:4860:4860::8888"],
        ["127.0.0.1"],
        ["::1"],
        ["169.254.169.254"],
        ["fe80::1"],
        ["fe80::1%eth0"],
        ["0.0.0.0"],
        ["::"],
        ["not an address"],
    ],
)
async def test_unsuitable_answers_are_ignored_with_a_warning(answer, caplog):
    p = proxies(FakeDns(edge_proxy=answer))
    with caplog.at_level(logging.WARNING, logger="backend.admin.gate"):
        await p.refresh()
    assert specs(p.snapshot) == []
    lines = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(lines) == 1 and "edge-proxy" in lines[0] and "1 address" in lines[0]
    assert answer[0] not in lines[0]  # names and counts only


async def test_only_the_suitable_answers_count():
    p = proxies(FakeDns(edge_proxy=[PROXY, "8.8.8.8", "127.0.0.1"]))
    await p.refresh()
    assert specs(p.snapshot) == [f"{PROXY}/32"]


async def test_an_answer_that_turned_public_does_not_fall_back_to_the_old_one():
    dns = FakeDns(edge_proxy=[PROXY])
    p = proxies(dns)
    await p.refresh()
    dns.answers["edge_proxy"] = ["8.8.8.8"]
    await p.refresh()
    assert specs(p.snapshot) == []


async def test_a_name_with_too_many_addresses_is_not_believed(caplog):
    many = [f"10.0.{i // 250}.{i % 250 + 1}" for i in range(MAX_ADDRESSES_PER_NAME + 1)]
    p = proxies(FakeDns(edge_proxy=many))
    with caplog.at_level(logging.WARNING, logger="backend.admin.gate"):
        await p.refresh()
    assert specs(p.snapshot) == []
    assert any("none of them is trusted" in r.getMessage() for r in caplog.records)
    p2 = proxies(FakeDns(edge_proxy=many[:-1]))
    await p2.refresh()
    assert len(p2.snapshot.networks) == MAX_ADDRESSES_PER_NAME


async def test_warnings_come_once_per_change_not_per_refresh(caplog):
    clock, dns = Clock(), FakeDns(edge_proxy=socket.gaierror(-2, "x"))
    p = proxies(dns, clock=clock)
    with caplog.at_level(logging.INFO, logger="backend.admin.gate"):
        for _ in range(5):
            clock.now += 60
            await p.refresh()
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "edge-proxy" in text and "gaierror" not in text and "-2" not in text


async def test_a_hanging_lookup_is_cut_off_and_trusts_nobody():
    async def hang(name):
        await asyncio.sleep(30)

    p = TrustedProxies([], ["edge-proxy"], resolver=hang, timeout=0.05)
    await asyncio.wait_for(p.start(), 2)  # start does not hang on DNS
    assert specs(p.snapshot) == []
    await p.stop()
    assert not p._inflight  # and stopping leaves nothing running


async def test_the_system_resolver_asks_for_both_families_on_its_own_threads(monkeypatch):
    seen = {}

    def fake(host, port, *args, **kw):
        seen["thread"] = threading.current_thread()
        seen["args"] = (host, kw)
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::5", 0, 0, 0)),
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    assert await system_resolver("edge-proxy") == ["10.0.0.5", "fd00::5"]
    assert seen["thread"] is not threading.main_thread()
    assert seen["thread"].name.startswith("admin-proxy-dns")  # not the default executor
    assert seen["args"][0] == "edge-proxy"
    assert "family" not in seen["args"][1]  # unspecified: A and AAAA


async def test_a_lookup_that_has_not_finished_is_never_started_again():
    gate, calls = asyncio.Event(), []

    async def blocked(name):
        calls.append(name)
        await gate.wait()
        return [PROXY]

    p = TrustedProxies([], ["edge-proxy"], resolver=blocked, timeout=0.02)
    for _ in range(4):
        await p.refresh()
    assert calls == ["edge-proxy"]  # one lookup, however many refreshes
    assert specs(p.snapshot) == []
    gate.set()
    await asyncio.sleep(0.01)
    await p.refresh()  # the finished one is dropped (too old to believe), a new one asked
    assert calls == ["edge-proxy", "edge-proxy"]
    assert specs(p.snapshot) == [f"{PROXY}/32"]
    await p.stop()


async def test_a_blocked_system_lookup_costs_one_thread_not_one_per_refresh(monkeypatch):
    release, started = threading.Event(), []

    def blocking(host, port, *args, **kw):
        started.append(threading.current_thread().name)
        release.wait(10)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PROXY, 0))]

    monkeypatch.setattr(socket, "getaddrinfo", blocking)
    p = TrustedProxies([], ["edge-proxy"], resolver=system_resolver, timeout=0.02)
    try:
        for _ in range(5):
            await p.refresh()
        assert len(started) == 1 and started[0].startswith("admin-proxy-dns")
        assert specs(p.snapshot) == []
    finally:
        release.set()
    for _ in range(200):  # the thread finishes; the next refresh asks again
        if p._inflight["edge-proxy"].done():
            break
        await asyncio.sleep(0.01)
    await p.refresh()
    assert len(started) == 2 and specs(p.snapshot) == [f"{PROXY}/32"]
    await p.stop()


async def test_a_blocked_lookup_does_not_starve_the_loops_own_executor(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: release.wait(10) and []
    )
    p = TrustedProxies(
        [], [f"proxy{i}" for i in range(6)], resolver=system_resolver, timeout=0.02
    )
    try:
        await p.refresh()
        # the loop's default executor is free for everyone else
        assert await asyncio.wait_for(asyncio.to_thread(lambda: "free"), 2) == "free"
    finally:
        release.set()
        await p.stop()


# -------------------------------------------------------------- the loop


async def test_the_refresh_loop_starts_refreshes_and_stops():
    dns = FakeDns(edge_proxy=[PROXY])
    p = proxies(dns, interval=0.01)
    await p.start()
    assert specs(p.snapshot) == [f"{PROXY}/32"]  # resolved before start returns
    task = p._task
    await p.start()  # a second start changes nothing
    assert p._task is task
    dns.answers["edge_proxy"] = [MOVED]
    for _ in range(200):
        if specs(p.snapshot) == [f"{MOVED}/32"]:
            break
        await asyncio.sleep(0.01)
    assert specs(p.snapshot) == [f"{MOVED}/32"]
    await p.stop()
    assert task.done() and p._task is None
    seen = len(dns.calls)
    await asyncio.sleep(0.05)
    assert len(dns.calls) == seen  # no lookups after stop
    await p.stop()  # stopping twice is fine


async def test_the_loop_survives_a_failing_refresh(monkeypatch):
    p = proxies(FakeDns(edge_proxy=[PROXY]), interval=0.01)
    await p.start()
    real, count = p.refresh, {"n": 0}

    async def flaky():
        count["n"] += 1
        if count["n"] == 1:
            raise RuntimeError("boom")
        return await real()

    monkeypatch.setattr(p, "refresh", flaky)
    for _ in range(200):
        if count["n"] >= 3:
            break
        await asyncio.sleep(0.01)
    assert count["n"] >= 3 and not p._task.done()
    await p.stop()


async def test_names_expire_on_their_own_when_every_refresh_fails():
    clock, dns = Clock(), FakeDns(edge_proxy=[PROXY])
    p = proxies(dns, "10.1.0.0/16", clock=clock, interval=0.01)
    await p.start()  # the first resolution works
    assert specs(p.snapshot) == ["10.0.0.5/32", "10.1.0.0/16"]

    async def broken():
        raise RuntimeError("boom")

    p.refresh = broken  # from now on every refresh raises
    for _ in range(5):  # the loop keeps running and failing
        await asyncio.sleep(0.02)
    assert p._task is not None and not p._task.done()
    clock.now += 0.01 + STALE_GRACE_SECONDS  # the last good answer is old, within the allowance
    assert specs(p.snapshot) == ["10.0.0.5/32", "10.1.0.0/16"]
    clock.now += 1
    assert specs(p.snapshot) == ["10.1.0.0/16"]  # only what is configured is left
    assert p.snapshot.spec == "10.1.0.0/16"
    await p.stop()


async def test_expiry_counts_from_the_oldest_answer_a_trusted_address_comes_from():
    clock, dns = Clock(), FakeDns(edge_proxy=[PROXY], other=[MOVED])
    p = proxies(dns, clock=clock, names=("edge-proxy", "other"), interval=60)
    await p.refresh()
    first = clock.now
    clock.now += 100
    dns.answers["other"] = OSError()  # edge-proxy stays fresh, other keeps its old answer
    await p.refresh()
    assert p.snapshot.expires_at == first + 60 + STALE_GRACE_SECONDS


async def test_a_refresh_moves_the_expiry_and_a_set_without_names_has_none():
    clock, dns = Clock(), FakeDns(edge_proxy=[PROXY])
    p = proxies(dns, "10.1.0.0/16", clock=clock, interval=60)
    assert p.snapshot.expires_at is None  # nothing from names yet
    await p.refresh()
    first = p.snapshot.expires_at
    clock.now += 60
    await p.refresh()  # same addresses, newer answer
    assert p.snapshot.expires_at == first + 60
    dns.answers["edge_proxy"] = ["8.8.8.8"]
    await p.refresh()
    assert p.snapshot.expires_at is None and specs(p.snapshot) == ["10.1.0.0/16"]


async def test_an_expired_set_is_dropped_for_the_gate_too():
    app = gate()
    clock = Clock()
    app.proxies._clock = clock
    app.proxies._resolver = FakeDns(edge_proxy=[PROXY])
    await app.proxies.refresh()
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 200
    clock.now += 60 + STALE_GRACE_SECONDS + 1  # no refresh happened since
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 404


async def test_without_names_there_is_no_loop():
    dns = FakeDns()
    p = proxies(dns, "10.0.0.2", names=())
    await p.start()
    assert p._task is None and dns.calls == []
    assert specs(p.snapshot) == ["10.0.0.2/32"] and p.configured
    assert not TrustedProxies().configured and TrustedProxies(names=["x"]).configured


def test_snapshots_are_immutable_and_deduplicated():
    n = ipaddress.ip_network("10.0.0.5")
    s = ProxySnapshot.of([n, n])
    assert s.networks == (n,)
    with pytest.raises(Exception):
        s.spec = "0.0.0.0/0"


# ------------------------------------------------------------- the gate


def gate(calls=None, env=None):
    app = get_admin_application(
        GateSettings.from_env(env or ENV), router_registry=make_registry(calls if calls is not None else [])
    )
    return app


async def test_a_request_from_the_resolved_proxy_passes_with_the_forwarded_client():
    calls = []
    app = gate(calls)
    app.proxies._resolver = FakeDns(edge_proxy=[PROXY])
    # before the first resolution the name trusts nobody: the header is not believed
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 404
    await app.proxies.refresh()
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 200
    # a client the allowlist does not name is still refused
    assert (await call(app, peer=PROXY, headers=[("x-forwarded-for", "198.51.100.1")]))[0] == 404
    # and so is anyone else claiming a client address
    assert (await call(app, peer="10.0.0.6", headers=XFF))[0] == 404
    assert calls == ["ping"]


async def test_after_the_name_moves_the_old_address_is_no_longer_trusted():
    app = gate()
    dns = FakeDns(edge_proxy=[PROXY])
    app.proxies._resolver = dns
    await app.proxies.refresh()
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 200
    dns.answers["edge_proxy"] = [MOVED]
    await app.proxies.refresh()
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 404
    assert (await call(app, peer=MOVED, headers=XFF))[0] == 200


async def test_an_unresolvable_name_trusts_nobody():
    app = gate()
    app.proxies._resolver = FakeDns(edge_proxy=socket.gaierror(-2, "x"))
    await app.proxies.refresh()
    for peer in (PROXY, MOVED, "172.18.0.2"):
        assert (await call(app, peer=peer, headers=XFF))[0] == 404


async def test_a_name_resolving_to_a_public_address_trusts_nobody():
    app = gate()
    app.proxies._resolver = FakeDns(edge_proxy=["203.0.113.9", "8.8.8.8"])
    await app.proxies.refresh()
    assert (await call(app, peer="8.8.8.8", headers=XFF))[0] == 404


async def test_configured_addresses_and_names_work_together():
    env = {**ENV, "ADMIN_TRUSTED_PROXIES": "10.0.0.2,edge-proxy"}
    app = gate(env=env)
    app.proxies._resolver = FakeDns(edge_proxy=[PROXY])
    assert (await call(app, peer="10.0.0.2", headers=XFF))[0] == 200  # no lookup needed
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 404
    await app.proxies.refresh()
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 200


HTTPS = [("x-forwarded-proto", "https")]


async def test_a_stack_prefixed_name_is_trusted_like_any_other():
    app = gate(env={**ENV, "ADMIN_TRUSTED_PROXIES": "proxy_nginx"})
    app.proxies._resolver = FakeDns(proxy_nginx=[PROXY])
    await app.proxies.refresh()
    assert (await call(app, peer=PROXY, headers=XFF))[0] == 200
    assert (await call(app, peer=MOVED, headers=XFF))[0] == 404


def scope_from(peer, headers=(), scheme="http"):
    return {
        "type": "http",
        "scheme": scheme,
        "client": (peer, 5555),
        "headers": [(k.encode(), v.encode()) for k, v in headers],
    }


async def test_forwarded_proto_follows_the_same_set():
    app = gate()
    dns = FakeDns(edge_proxy=[PROXY])
    app.proxies._resolver = dns
    https = [("x-forwarded-proto", "https")]
    assert not app._is_https(scope_from(PROXY, https))  # not resolved yet
    await app.proxies.refresh()
    assert app._is_https(scope_from(PROXY, https))
    assert not app._is_https(scope_from(PROXY, [("x-forwarded-proto", "http")]))
    assert not app._is_https(scope_from(MOVED, https))  # someone else's header
    assert app._is_https(scope_from(MOVED, scheme="https"))  # the ASGI scheme still counts
    dns.answers["edge_proxy"] = [MOVED]
    await app.proxies.refresh()
    assert not app._is_https(scope_from(PROXY, https))
    assert app._is_https(scope_from(MOVED, https))


async def test_a_request_keeps_one_set_even_when_it_changes_meanwhile():
    seen, holder = {}, {}
    reg = RouteRegistry()

    @reg.route("/ping", level=Level.ADDRESS)
    async def ping(request: Request):
        app = holder["app"]
        seen["during"] = request.scope["state"]["trusted_proxies"]
        holder["dns"].answers["edge_proxy"] = [MOVED]
        await app.proxies.refresh()  # the set changes while this request is served
        seen["after"] = app.proxies.snapshot
        # the decisions the gate takes for this request still use the set it started with
        seen["https_now"] = app._is_https(request.scope)
        seen["https_new_request"] = app._is_https(scope_from(PROXY, HTTPS))
        return {}

    app = holder["app"] = get_admin_application(
        GateSettings.from_env(ENV), router_registry=reg
    )
    dns = holder["dns"] = FakeDns(edge_proxy=[PROXY])
    app.proxies._resolver = dns
    await app.proxies.refresh()
    first = app.proxies.snapshot
    status, _, _ = await call(app, peer=PROXY, headers=[*XFF, *HTTPS])
    assert status == 200  # the address decision used the set before the swap
    assert seen["during"] is first and seen["after"] is not first
    assert seen["https_now"] is True  # the proto decision of the request: the old set
    assert seen["https_new_request"] is False  # a request that starts now sees the new one


async def test_the_lifespan_resolves_at_start_and_stops_the_loop_at_the_end():
    app = gate()
    dns = FakeDns(edge_proxy=[PROXY])
    app.proxies._resolver = dns
    inner = app.inner
    async with inner.router.lifespan_context(inner):
        assert specs(app.proxies.snapshot) == [f"{PROXY}/32"]
        task = app.proxies._task
        assert task is not None and not task.done()
    assert task.done() and app.proxies._task is None


async def test_the_lifespan_starts_when_the_name_does_not_resolve_yet(caplog):
    app = gate()
    app.proxies._resolver = FakeDns(edge_proxy=socket.gaierror(-2, "x"))
    inner = app.inner
    with caplog.at_level(logging.WARNING, logger="backend.admin.gate"):
        async with inner.router.lifespan_context(inner):
            assert specs(app.proxies.snapshot) == []
    assert any("edge-proxy" in r.getMessage() for r in caplog.records)


def test_a_named_proxy_counts_as_a_configured_proxy(caplog):
    base = {"ADMIN_EDGE_GATEWAY": "172.30.77.1"}
    assert warn_shared_gateway(GateSettings.from_env(base)) is True
    named = GateSettings.from_env({**base, "ADMIN_TRUSTED_PROXIES": "edge-proxy"})
    with caplog.at_level(logging.WARNING, logger="backend.admin"):
        assert warn_shared_gateway(named) is False
