"""Gate settings, read from the environment. Invalid values fail startup."""

import ipaddress
import os
from dataclasses import dataclass
from typing import List, Mapping, Optional, Tuple

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


def _host(value: str) -> str:
    host = value.lower()
    if any(c in host for c in " /\\@\t") or not host.isascii():
        raise GateConfigError(f"ADMIN_ALLOWED_HOSTS: {value!r} is not a host[:port]")
    return host


@dataclass(frozen=True)
class GateSettings:
    allowed_ips: Tuple = ()
    allowed_hosts: Tuple[str, ...] = ()
    trusted_proxies: str = ""  # validated, comma-separated, for resolve_client_ip
    port: int = DEFAULT_PORT

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
        if gateway:
            try:
                addr = ipaddress.ip_address(gateway)
            except ValueError:
                raise GateConfigError("ADMIN_EDGE_GATEWAY: not an address") from None
            ips.append(ipaddress.ip_network(addr))
        if not ips:
            raise GateConfigError("ADMIN_ALLOWED_IPS: empty")

        hosts = tuple(
            _host(h)
            for h in (
                _split(env.get("ADMIN_ALLOWED_HOSTS"))
                or [f"localhost:{port}", f"127.0.0.1:{port}"]
            )
        )
        proxies = _networks("ADMIN_TRUSTED_PROXIES", env.get("ADMIN_TRUSTED_PROXIES"))
        return cls(
            allowed_ips=tuple(ips),
            allowed_hosts=hosts,
            trusted_proxies=",".join(str(n) for n in proxies),
            port=port,
        )
