"""Internal routes stay off the public ingress.

A few routes are only ever called by services inside the stack, with a shared
key: the admin task runner (``/internal/admin-tasks/*``, ``ADMIN_TASKS_API_KEY``)
and the Temporal worker and actions-executor (the ``api-key`` routes,
``TEMPORAL_API_KEY``: ``/temporal/*``, ``DELETE /auth/user``, the action update
and the template preview). The key must not be their only guard, so they are
also refused when the request did not come from inside the stack:

* The backend listens on a second port, ``API_INTERNAL_PORT`` (8001 by default,
  0 = off), that is never published or proxied (``backend/__main__.py``). A
  request is "on the internal listener" when the socket it arrived on is that
  port (``scope["server"]``, from the socket itself: no header can fake it).
* ``API_INTERNAL_ROUTES`` decides what else the worker routes accept:

  - ``direct`` (default, for the transition): also the public port, for a
    direct in-network request only: the TCP peer is a loopback or private
    address and the request carries no proxy header.
  - ``internal_port``: the internal listener only.

* The admin-task routes accept the internal listener only, whatever the mode
  (fail closed: without an internal listener they are unreachable).
* A request carrying any proxy header (``X-Forwarded-For``, ``Forwarded``, …)
  is refused on every port: the in-stack callers never send one.

A refused request gets the same 404 as an unknown path, before any key is
checked, so the internet learns nothing about the keys.
"""

import ipaddress
import os
from enum import Enum
from typing import Optional

from fastapi import Request
from loguru import logger
from starlette.exceptions import HTTPException as StarletteHTTPException

DEFAULT_INTERNAL_PORT = 8001

# Headers a reverse proxy, load balancer or CDN adds; an in-stack caller sends
# none. Lower case: Starlette's header lookup ignores case.
PROXY_HEADERS = (
    "forwarded",
    "x-forwarded-for",
    "x-forwarded-host",
    "x-forwarded-proto",
    "x-forwarded-port",
    "x-forwarded-server",
    "x-real-ip",
    "x-client-ip",
    "x-original-forwarded-for",
    "x-cluster-client-ip",
    "true-client-ip",
    "cf-connecting-ip",
    "fastly-client-ip",
    "akamai-origin-hop",
    "x-envoy-external-address",
    "x-envoy-original-path",
    "x-azure-clientip",
    "x-azure-socketip",
    "x-appengine-user-ip",
    "x-arr-clientip",
    "x-proxyuser-ip",
    "via",
)


# The addresses a container or the host itself has inside a stack: loopback and
# the private ranges (RFC 1918, IPv6 unique local). Not ``is_private``: that
# also covers documentation, benchmark and reserved ranges.
INTERNAL_NETWORKS = tuple(
    ipaddress.ip_network(n)
    for n in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    )
)


class InternalRoutesMode(str, Enum):
    DIRECT = "direct"
    INTERNAL_PORT = "internal_port"


def _public_port() -> int:
    try:
        return int(os.getenv("PORT", "8000"))
    except ValueError:
        return 8000


def internal_port() -> int:
    """The internal listener's port; 0 when there is none (unset value: 8001).

    Environment only (``API_INTERNAL_PORT``). An invalid value, or the public
    port itself, counts as no internal listener: never treat the public port
    as the internal one."""
    raw = (os.getenv("API_INTERNAL_PORT") or "").strip()
    if not raw:
        port = DEFAULT_INTERNAL_PORT
    else:
        try:
            port = int(raw)
        except ValueError:
            return 0
    if not 0 < port < 65536 or port == _public_port():
        return 0
    return port


def mode() -> InternalRoutesMode:
    """``API_INTERNAL_ROUTES`` (environment only); anything unknown is the
    stricter ``internal_port``."""
    raw = (os.getenv("API_INTERNAL_ROUTES") or "").strip().lower()
    if not raw or raw == InternalRoutesMode.DIRECT.value:
        return InternalRoutesMode.DIRECT
    return InternalRoutesMode.INTERNAL_PORT


def _not_found() -> StarletteHTTPException:
    # what FastAPI answers for a path it doesn't know
    return StarletteHTTPException(status_code=404)


def _on_internal_listener(request: Request) -> bool:
    port = internal_port()
    server = request.scope.get("server")
    return bool(port and server and len(server) > 1 and server[1] == port)


def _proxied(request: Request) -> bool:
    return any(name in request.headers for name in PROXY_HEADERS)


def _peer_is_internal(request: Request) -> bool:
    peer = request.scope.get("client")
    host: Optional[str] = peer[0] if peer else None
    if not host:
        return False
    try:
        address = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        return False
    if getattr(address, "ipv4_mapped", None):
        address = address.ipv4_mapped
    return any(address in network for network in INTERNAL_NETWORKS)


def require_internal_listener(request: Request) -> None:
    """For the admin-task routes: the internal listener, no proxy header."""
    if _proxied(request) or not _on_internal_listener(request):
        raise _not_found()


def require_in_network(request: Request) -> None:
    """For the worker routes: the internal listener, or (``direct`` mode) a
    direct request from a loopback or private address on the public port;
    never a request that came through a proxy."""
    if _proxied(request):
        raise _not_found()
    if _on_internal_listener(request):
        return
    if mode() is InternalRoutesMode.DIRECT and _peer_is_internal(request):
        return
    raise _not_found()


_direct_warned = False


def log_internal_routes_setup() -> None:
    """At startup: say where the internal routes are served."""
    port = internal_port()
    if not port:
        logger.warning(
            "No internal listener (API_INTERNAL_PORT is 0, invalid or the public "
            "port): the admin-task routes are unreachable, and the worker routes "
            "only accept direct requests from private addresses on the public port."
        )
    global _direct_warned
    if mode() is InternalRoutesMode.DIRECT and not _direct_warned:
        _direct_warned = True
        logger.warning(
            "API_INTERNAL_ROUTES=direct: the workers' key-only routes also answer on "
            "the public port to requests from private addresses without proxy "
            "headers. Anything that rewrites an outside client's address to a "
            "private one (Swarm's ingress mesh, Docker's userland-proxy, a host "
            "proxy that adds no X-Forwarded-For) lets outside callers through to "
            "the key check. Point the workers' SERVER_URL at the internal port and "
            "set API_INTERNAL_ROUTES=internal_port."
        )
