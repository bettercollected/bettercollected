"""CF-Connecting-IP in the admin portal's address check (ADMIN_TRUST_CLOUDFLARE).

Off by default. When turned on it is believed only for a request that came
through a trusted proxy (ADMIN_TRUSTED_PROXIES) and whose first hop past the
proxies is a Cloudflare edge; from anyone else, and in any malformed shape,
the header is ignored (the same rules as the API's API_TRUST_CLOUDFLARE,
common.utils.client_ip)."""

import pytest

from backend.admin.gate.settings import GateConfigError, GateSettings
from common.utils.client_ip import CLOUDFLARE_IPS
from tests.admin.test_gate import call, make_app, make_registry

PROXY = "10.0.0.2"
EDGE = "173.245.48.5"  # inside Cloudflare's published 173.245.48.0/20
ALLOWED = "192.0.2.7"  # the operator's own address, in ADMIN_ALLOWED_IPS
STRANGER = "203.0.113.9"  # not allowed
BASE = {"ADMIN_TRUSTED_PROXIES": PROXY, "ADMIN_ALLOWED_IPS": "192.0.2.0/24"}
ON = {**BASE, "ADMIN_TRUST_CLOUDFLARE": "true"}


def via(edge, cf=None, peer=PROXY):
    """Headers of a request the proxy forwarded: X-Forwarded-For (the proxy
    appends the address it saw: the Cloudflare edge) and CF-Connecting-IP."""
    headers = [("x-forwarded-for", edge)]
    for value in [cf] if isinstance(cf, str) else (cf or []):
        headers.append(("cf-connecting-ip", value))
    return {"peer": peer, "headers": headers}


async def status_of(env, **request):
    calls = []
    app = make_app(env, registry=make_registry(calls))
    status, _, _ = await call(app, **request)
    return status, calls


# --- settings -----------------------------------------------------------------------


def test_off_by_default_and_for_every_false_word():
    assert GateSettings.from_env({}).cloudflare_ips is None
    for word in ("", "false", "0", "no", "off", "False"):
        assert GateSettings.from_env({"ADMIN_TRUST_CLOUDFLARE": word}).cloudflare_ips is None


def test_ranges_alone_do_not_turn_it_on():
    env = {"ADMIN_CLOUDFLARE_IPS": "198.51.100.0/24"}
    assert GateSettings.from_env(env).cloudflare_ips is None


def test_on_uses_the_built_in_ranges_or_the_operators_own():
    assert GateSettings.from_env({"ADMIN_TRUST_CLOUDFLARE": "true"}).cloudflare_ips == CLOUDFLARE_IPS
    own = {"ADMIN_TRUST_CLOUDFLARE": "1", "ADMIN_CLOUDFLARE_IPS": " 198.51.100.0/24 , 2001:db8::/32 "}
    assert GateSettings.from_env(own).cloudflare_ips == "198.51.100.0/24,2001:db8::/32"


@pytest.mark.parametrize(
    "env",
    [
        {"ADMIN_TRUST_CLOUDFLARE": "maybe"},
        {"ADMIN_TRUST_CLOUDFLARE": "true", "ADMIN_CLOUDFLARE_IPS": "not-a-range"},
        {"ADMIN_TRUST_CLOUDFLARE": "true", "ADMIN_CLOUDFLARE_IPS": "0.0.0.0/0"},
        {"ADMIN_TRUST_CLOUDFLARE": "true", "ADMIN_CLOUDFLARE_IPS": "198.51.100.0/24,::/0"},
        {"ADMIN_TRUST_CLOUDFLARE": "true", "ADMIN_CLOUDFLARE_IPS": "fe80::1%eth0"},
        {"ADMIN_TRUST_CLOUDFLARE": "true", "ADMIN_CLOUDFLARE_IPS": "198.51.100.0/24,2001:db8::%1/32"},
    ],
)
def test_a_bad_value_fails_startup(env):
    with pytest.raises(GateConfigError):
        GateSettings.from_env(env)


# --- the gate -----------------------------------------------------------------------


async def test_off_the_header_is_ignored_even_from_the_trusted_proxy():
    # the first hop is the edge's address; no header can say otherwise
    status, calls = await status_of(BASE, **via(EDGE, ALLOWED))
    assert status == 404 and calls == []


async def test_on_a_cloudflare_request_through_the_trusted_proxy_uses_the_header():
    status, calls = await status_of(ON, **via(EDGE, ALLOWED))
    assert status == 200 and calls == ["ping"]
    # and the header decides: a stranger behind Cloudflare is refused
    status, calls = await status_of(ON, **via(EDGE, STRANGER))
    assert status == 404 and calls == []


async def test_on_the_state_carries_the_header_address():
    seen = []

    from fastapi import Request

    from backend.admin.gate.levels import Level, RouteRegistry

    reg = RouteRegistry()

    @reg.route("/who", level=Level.ADDRESS)
    async def who(request: Request):
        seen.append(request.scope["state"]["client_ip"])
        return {}

    app = make_app(ON, registry=reg)
    status, _, _ = await call(app, path="/who", **via(EDGE, ALLOWED))
    assert status == 200 and seen == [ALLOWED]


# --- spoofing: the header from a source that is not Cloudflare through our proxy -----


async def test_an_untrusted_peer_cannot_send_it():
    # the peer is not ADMIN_TRUSTED_PROXIES: its headers are its own words
    for peer in (STRANGER, "10.0.0.9", EDGE):
        status, calls = await status_of(ON, **via(EDGE, ALLOWED, peer=peer))
        assert status == 404 and calls == [], peer


async def test_an_untrusted_peer_cannot_send_it_with_no_proxy_configured():
    env = {"ADMIN_TRUST_CLOUDFLARE": "true", "ADMIN_ALLOWED_IPS": "192.0.2.0/24"}
    status, calls = await status_of(env, **via(EDGE, ALLOWED, peer=EDGE))
    assert status == 404 and calls == []


async def test_a_client_that_is_not_cloudflare_cannot_send_it_through_our_proxy():
    # the proxy saw 198.51.100.4, not a Cloudflare edge: the header is the client's own
    status, calls = await status_of(ON, **via("198.51.100.4", ALLOWED))
    assert status == 404 and calls == []
    # even when the client's own X-Forwarded-For starts with an edge address
    status, calls = await status_of(
        ON,
        peer=PROXY,
        headers=[("x-forwarded-for", f"{EDGE}, 198.51.100.4"), ("cf-connecting-ip", ALLOWED)],
    )
    assert status == 404 and calls == []


async def test_two_headers_or_garbage_are_ignored():
    for cf in ([ALLOWED, STRANGER], ["not-an-ip"], ["x" * 5000], [""]):
        status, calls = await status_of(ON, **via(EDGE, cf))
        assert status == 404 and calls == [], cf


async def test_a_header_with_the_switch_off_but_ranges_set_is_still_ignored():
    env = {**BASE, "ADMIN_CLOUDFLARE_IPS": "173.245.48.0/20"}
    status, calls = await status_of(env, **via(EDGE, ALLOWED))
    assert status == 404 and calls == []


async def test_the_operators_ranges_replace_the_built_in_ones():
    env = {**ON, "ADMIN_CLOUDFLARE_IPS": "198.51.100.0/24"}
    assert (await status_of(env, **via("198.51.100.4", ALLOWED)))[0] == 200
    status, calls = await status_of(env, **via(EDGE, ALLOWED))
    assert status == 404 and calls == []


async def test_a_request_without_the_header_is_judged_by_its_edge_address():
    status, calls = await status_of(ON, **via(EDGE))
    assert status == 404 and calls == []
    env = {**ON, "ADMIN_ALLOWED_IPS": f"192.0.2.0/24,{EDGE}/32"}
    assert (await status_of(env, **via(EDGE)))[0] == 200
