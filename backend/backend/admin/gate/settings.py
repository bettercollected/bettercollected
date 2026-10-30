"""Gate settings, read from the environment. Invalid values fail startup."""

import ipaddress
import os
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple

from backend.admin.gate.proxies import (
    DEFAULT_REFRESH_SECONDS,
    MAX_NAMES,
    MAX_REFRESH_SECONDS,
    MIN_REFRESH_SECONDS,
    valid_host_name,
)

DEFAULT_PORT = 8100


class GateConfigError(ValueError):
    pass


def _split(value: Optional[str]) -> List[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


def _networks(name: str, value: Optional[str]):
    out = []
    for part in _split(value):
        try:
            net = ipaddress.ip_network(part, strict=False)
        except ValueError:
            raise GateConfigError(f"{name}: {part!r} is not an address or CIDR") from None
        if net.prefixlen == 0:
            raise GateConfigError(f"{name}: {part!r} would match every address")
        out.append(net)
    return tuple(out)


def _proxies(name: str, value: Optional[str]):
    """``(networks, host names)`` of a list of addresses, CIDRs and host names."""
    networks, names = [], []
    for part in _split(value):
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
            continue
        except ValueError:
            pass
        host = part.lower()
        if "/" in part or not valid_host_name(host):
            raise GateConfigError(
                f"{name}: {part!r} is not an address, a CIDR or a host name"
            ) from None
        if host not in names:
            names.append(host)
    for net in networks:
        if net.prefixlen == 0:
            raise GateConfigError(f"{name}: {net!s} would match every address")
    if len(names) > MAX_NAMES:
        raise GateConfigError(f"{name}: more than {MAX_NAMES} host names")
    return tuple(networks), tuple(names)


def _refresh_seconds(value: Optional[str]) -> int:
    raw = (value or "").strip()
    if not raw:
        return DEFAULT_REFRESH_SECONDS
    if not raw.isascii() or not raw.isdigit() or not (
        MIN_REFRESH_SECONDS <= int(raw) <= MAX_REFRESH_SECONDS
    ):
        raise GateConfigError(
            "ADMIN_TRUSTED_PROXY_REFRESH_SECONDS: not a number of seconds between "
            f"{MIN_REFRESH_SECONDS} and {MAX_REFRESH_SECONDS}"
        )
    return int(raw)


def _host(value: str) -> str:
    host = value.lower()
    if any(c in host for c in " /\\@\t") or not host.isascii():
        raise GateConfigError(f"ADMIN_ALLOWED_HOSTS: {value!r} is not a host[:port]")
    return host


@dataclass(frozen=True)
class GateSettings:
    allowed_ips: Tuple = ()
    allowed_hosts: Tuple[str, ...] = ()
    trusted_proxies: str = ""  # the configured addresses/CIDRs, comma-separated
    # host names of proxies, resolved at start and refreshed (gate/proxies.py);
    # the live set (these plus the addresses above) is a TrustedProxies snapshot
    trusted_proxy_names: Tuple[str, ...] = ()
    proxy_refresh_seconds: int = DEFAULT_REFRESH_SECONDS
    port: int = DEFAULT_PORT
    # the admin network's gateway: what host-side traffic looks like after Docker's
    # port publishing; /healthz answers it as well as loopback
    edge_gateway: Optional[ipaddress.IPv4Address | ipaddress.IPv6Address] = None

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "GateSettings":
        env = os.environ if environ is None else environ
        raw_port = (env.get("ADMIN_PORT") or str(DEFAULT_PORT)).strip()
        if not raw_port.isdigit() or not 0 < int(raw_port) < 65536:
            raise GateConfigError("ADMIN_PORT: not a port number")
        port = int(raw_port)

        ips = list(
            _networks("ADMIN_ALLOWED_IPS", env.get("ADMIN_ALLOWED_IPS") or "127.0.0.1/32")
        )
        gateway = (env.get("ADMIN_EDGE_GATEWAY") or "").strip()
        edge_gateway = None
        if gateway:
            try:
                addr = ipaddress.ip_address(gateway)
            except ValueError:
                raise GateConfigError("ADMIN_EDGE_GATEWAY: not an address") from None
            ips.append(ipaddress.ip_network(addr))
            edge_gateway = addr
        if not ips:
            raise GateConfigError("ADMIN_ALLOWED_IPS: empty")

        hosts = tuple(
            _host(h)
            for h in (
                _split(env.get("ADMIN_ALLOWED_HOSTS"))
                or [f"localhost:{port}", f"127.0.0.1:{port}"]
            )
        )
        proxies, proxy_names = _proxies(
            "ADMIN_TRUSTED_PROXIES", env.get("ADMIN_TRUSTED_PROXIES")
        )
        refresh = _refresh_seconds(env.get("ADMIN_TRUSTED_PROXY_REFRESH_SECONDS"))
        return cls(
            allowed_ips=tuple(ips),
            allowed_hosts=hosts,
            trusted_proxies=",".join(str(n) for n in proxies),
            trusted_proxy_names=proxy_names,
            proxy_refresh_seconds=refresh,
            port=port,
            edge_gateway=edge_gateway,
        )
