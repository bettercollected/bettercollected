"""The reverse proxies the gate believes, by address and by name.

``ADMIN_TRUSTED_PROXIES`` lists addresses and CIDRs, and may also name the
proxy by host name (a container or service name on a shared network), because
a recreated container gets a new address. Names are resolved when the service
starts and again every ``ADMIN_TRUSTED_PROXY_REFRESH_SECONDS``; the trusted set
is the configured addresses plus exactly the addresses the names resolve to,
each as a single-address network.

Failure never widens trust. A name that does not resolve contributes nothing;
after a failed lookup its last good addresses stay for ``STALE_GRACE_SECONDS``
and are then dropped. An answer that is not a private-network address
(public, loopback, link-local, unspecified, multicast, reserved) is ignored.
The set is an immutable snapshot swapped in one assignment, so a request that
reads it once sees one consistent set.
"""

import asyncio
import ipaddress
import logging
import re
import socket
import time
from dataclasses import dataclass
from typing import (
    Awaitable,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    Optional,
    Sequence,
    Tuple,
    Union,
)

log = logging.getLogger("backend.admin.gate")

Network = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]
Address = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
Resolver = Callable[[str], Awaitable[Sequence[str]]]

DEFAULT_REFRESH_SECONDS = 60
MIN_REFRESH_SECONDS = 10
MAX_REFRESH_SECONDS = 3600
# how long a name's last good addresses are kept after its lookups start failing
STALE_GRACE_SECONDS = 300.0
# one lookup, and the start-up resolution as a whole, never wait longer
LOOKUP_TIMEOUT_SECONDS = 3.0
MAX_NAMES = 16
# more addresses than this behind one name are not believed (a proxy has a few)
MAX_ADDRESSES_PER_NAME = 32

_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_NUMERIC_LABEL = re.compile(r"^(\d+|0x[0-9a-f]*)$")  # inet_aton's number forms


def valid_host_name(value: str) -> bool:
    """A plain RFC 1123 host name, lower case: labels of letters, digits and
    hyphens (not at either end), at most 63 characters each and 253 in all.
    No trailing dot, port, scheme, path or wildcard. The last label must not
    be numeric, so a mistyped address ("10.0.0", "300.1.1.1") is refused
    instead of being handed to the resolver, which reads such forms as numbers."""
    if not value or len(value) > 253 or not value.isascii():
        return False
    labels = value.split(".")
    if not all(_LABEL.match(label) for label in labels):
        return False
    return not _NUMERIC_LABEL.match(labels[-1])


def proxy_address_ok(address: Address) -> bool:
    """Whether a resolved address may be a proxy of ours: an address of a
    private network, never a public, loopback, link-local, unspecified,
    multicast or reserved one."""
    return not (
        address.is_loopback
        or address.is_link_local
        or address.is_unspecified
        or address.is_multicast
        or address.is_reserved
        or address.is_global
    )


@dataclass(frozen=True)
class ProxySnapshot:
    """The trusted proxies at one moment. Immutable."""

    networks: Tuple[Network, ...] = ()
    spec: str = ""  # comma-separated, for common.utils.client_ip.resolve_client_ip

    @classmethod
    def of(cls, networks: Iterable[Network]) -> "ProxySnapshot":
        unique = tuple(dict.fromkeys(networks))
        return cls(unique, ",".join(str(n) for n in unique))

    def trusts(self, address: Optional[Address]) -> bool:
        return address is not None and any(
            address.version == net.version and address in net for net in self.networks
        )


async def system_resolver(name: str) -> Sequence[str]:
    """The addresses (A and AAAA) the system resolver gives ``name``, off the
    event loop, within ``LOOKUP_TIMEOUT_SECONDS``."""
    loop = asyncio.get_running_loop()
    infos = await asyncio.wait_for(
        loop.getaddrinfo(name, None, type=socket.SOCK_STREAM), LOOKUP_TIMEOUT_SECONDS
    )
    return [str(info[4][0]) for info in infos]


@dataclass(frozen=True)
class _Good:
    addresses: FrozenSet[Address]
    at: float


def _usable(raw: Iterable[str]) -> Tuple[FrozenSet[Address], int]:
    """The usable addresses among ``raw`` and how many answers were ignored."""
    usable, ignored = set(), 0
    for text in raw:
        try:
            address = ipaddress.ip_address(text)
        except ValueError:  # includes a scoped (fe80::1%eth0) address
            ignored += 1
            continue
        address = getattr(address, "ipv4_mapped", None) or address
        if proxy_address_ok(address):
            usable.add(address)
        else:
            ignored += 1
    return frozenset(usable), ignored


class TrustedProxies:
    """Configured networks plus resolved names, as a live ``snapshot``."""

    def __init__(
        self,
        networks: Iterable[Network] = (),
        names: Iterable[str] = (),
        interval: float = DEFAULT_REFRESH_SECONDS,
        resolver: Resolver = system_resolver,
        clock: Callable[[], float] = time.monotonic,
        grace: float = STALE_GRACE_SECONDS,
        timeout: float = LOOKUP_TIMEOUT_SECONDS,
    ) -> None:
        self._static = tuple(networks)
        self.names = tuple(dict.fromkeys(names))
        self.interval = interval
        self._resolver = resolver
        self._clock = clock
        self._grace = grace
        self._timeout = timeout
        self._good: Dict[str, _Good] = {}
        self._status: Dict[str, str] = {}  # last logged state per name
        self._task: Optional["asyncio.Task[None]"] = None
        self._snapshot = ProxySnapshot.of(self._static)

    @classmethod
    def from_settings(cls, settings, **kw) -> "TrustedProxies":
        networks = [
            ipaddress.ip_network(part)
            for part in settings.trusted_proxies.split(",")
            if part
        ]
        return cls(
            networks,
            settings.trusted_proxy_names,
            interval=settings.proxy_refresh_seconds,
            **kw,
        )

    @property
    def snapshot(self) -> ProxySnapshot:
        """The current set; read it once per request."""
        return self._snapshot

    @property
    def configured(self) -> bool:
        """Whether any proxy is configured, resolved or not."""
        return bool(self._static or self.names)

    async def _lookup(self, name: str) -> Optional[Sequence[str]]:
        try:
            answer = await asyncio.wait_for(self._resolver(name), self._timeout)
        except asyncio.CancelledError:
            raise
        except Exception:  # timeout, NXDOMAIN, a resolver bug: all "no answer"
            return None
        return answer or None

    def _note(self, name: str, state: str, count: int) -> None:
        """One WARNING per change of a name's state, not one per refresh."""
        key = f"{state}:{count}"
        if self._status.get(name) == key:
            return
        self._status[name] = key
        if state == "ok":
            log.info(
                "admin gate: proxy name %s resolves to %d address(es)", name, count
            )
        elif state == "failed":
            log.warning(
                "admin gate: proxy name %s did not resolve; it is trusted for "
                "%d address(es) kept from earlier",
                name,
                count,
            )
        elif state == "many":
            log.warning(
                "admin gate: proxy name %s resolves to %d addresses, more than %d: "
                "none of them is trusted",
                name,
                count,
                MAX_ADDRESSES_PER_NAME,
            )
        elif state == "ignored":
            log.warning(
                "admin gate: proxy name %s: %d address(es) are not private-network "
                "addresses and are ignored",
                name,
                count,
            )

    async def refresh(self) -> ProxySnapshot:
        """Resolve every name and swap in the new set. Never raises for a
        lookup; a name that fails keeps its last good addresses only until the
        grace period ends."""
        if not self.names:
            return self._snapshot
        answers = await asyncio.gather(*(self._lookup(n) for n in self.names))
        now = self._clock()
        resolved = set()
        for name, raw in zip(self.names, answers):
            if raw is None:
                previous = self._good.get(name)
                if previous is not None and now - previous.at <= self._grace:
                    addresses = previous.addresses
                else:
                    self._good.pop(name, None)
                    addresses = frozenset()
                self._note(name, "failed", len(addresses))
            else:
                addresses, ignored = _usable(raw)
                too_many = len(addresses) > MAX_ADDRESSES_PER_NAME
                if too_many:
                    addresses = frozenset()
                self._good[name] = _Good(addresses, now)
                if too_many:
                    self._note(name, "many", len(raw))
                elif ignored:
                    self._note(name, "ignored", ignored)
                else:
                    self._note(name, "ok", len(addresses))
            resolved.update(addresses)
        found = sorted(resolved, key=lambda a: (a.version, int(a)))  # v4 and v6 mix
        new = ProxySnapshot.of(
            (*self._static, *(ipaddress.ip_network(a) for a in found))
        )
        if new != self._snapshot:
            self._snapshot = new  # one assignment: readers see the old set or the new
        return new

    async def start(self) -> None:
        """Resolve once (bounded: a name that does not answer in time is just
        not trusted yet) and keep refreshing in the background."""
        if not self.names or self._task is not None:
            return
        try:
            await asyncio.wait_for(self.refresh(), self._timeout * 2)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("admin gate: the first proxy name lookup did not finish")
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            try:
                await self.refresh()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # the loop must outlive any one failure
                log.error("admin gate: proxy name refresh failed: %s", type(exc).__name__)

    async def stop(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
