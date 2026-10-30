"""The reverse proxies the gate believes, by address and by name.

``ADMIN_TRUSTED_PROXIES`` lists addresses and CIDRs, and may also name the
proxy by host name (a container or service name on a shared network), because
a recreated container gets a new address. Names are resolved when the service
starts and again every ``ADMIN_TRUSTED_PROXY_REFRESH_SECONDS``; the trusted set
is the configured addresses plus exactly the addresses the names resolve to,
each as a single-address network.

Failure never widens trust. A name that does not resolve contributes nothing;
after a failed lookup its last good addresses stay for ``STALE_GRACE_SECONDS``
and are then dropped; should the refresh itself stop working, the addresses
that came from names expire on their own (``ProxySnapshot.expires_at``). Only
an address of a private network (RFC 1918, unique local) is accepted from a
name; anything else is ignored. A lookup that has not finished is never
started a second time (a stuck resolver costs one thread per name, not one per
refresh), on a small executor of its own. The set is an immutable snapshot
swapped in one assignment, so a request that reads it once sees one
consistent set.
"""

import asyncio
import ipaddress
import logging
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
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

# letters, digits, "-" and "_" (Docker names a stack's services <stack>_<service> and its
# DNS resolves them), 1 to 63 characters, no "-" at either end
_LABEL = re.compile(r"^([a-z0-9_]|[a-z0-9_][a-z0-9_-]{0,61}[a-z0-9_])$")
_NUMERIC_LABEL = re.compile(r"^(\d+|0x[0-9a-f]*)$")  # inet_aton's number forms


def valid_host_name(value: str) -> bool:
    """A plain host name, lower case: labels of letters, digits, hyphens and
    underscores (no hyphen at either end), at most 63 characters each and 253
    in all. No trailing dot, port, scheme, path or wildcard. The last label
    must not be numeric, so a mistyped address ("10.0.0", "300.1.1.1") is
    refused instead of being handed to the resolver, which reads such forms as
    numbers."""
    if not value or len(value) > 253 or not value.isascii():
        return False
    labels = value.split(".")
    if not all(_LABEL.match(label) for label in labels):
        return False
    return not _NUMERIC_LABEL.match(labels[-1])


# the only places a proxy of ours can be found: the private ranges. An allowlist,
# not "whatever is not global": what Python calls global moves between versions
# (6to4, Teredo, documentation and benchmarking ranges, 3fff::/20), and carrier-grade
# NAT (100.64.0.0/10) is not a network we run.
PRIVATE_RANGES = tuple(
    ipaddress.ip_network(n)
    for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7")
)


def proxy_address_ok(address: Address) -> bool:
    """Whether a resolved address may be a proxy of ours: an address in
    10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 or fc00::/7, nothing else."""
    return any(
        address.version == net.version and address in net for net in PRIVATE_RANGES
    )


@dataclass(frozen=True)
class ProxySnapshot:
    """The trusted proxies at one moment. Immutable."""

    networks: Tuple[Network, ...] = ()
    spec: str = ""  # comma-separated, for common.utils.client_ip.resolve_client_ip
    # clock time after which the addresses that came from names are no longer
    # believed (None: there are none); the configured networks never expire
    expires_at: Optional[float] = field(default=None, compare=False)

    @classmethod
    def of(
        cls, networks: Iterable[Network], expires_at: Optional[float] = None
    ) -> "ProxySnapshot":
        unique = tuple(dict.fromkeys(networks))
        return cls(unique, ",".join(str(n) for n in unique), expires_at)

    def trusts(self, address: Optional[Address]) -> bool:
        return address is not None and any(
            address.version == net.version and address in net for net in self.networks
        )


_executor: Optional[ThreadPoolExecutor] = None


def _dns_executor() -> ThreadPoolExecutor:
    """A small pool of its own: a resolver that hangs can hold these threads,
    never the loop's default executor that the rest of the service uses."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(2, thread_name_prefix="admin-proxy-dns")
    return _executor


async def system_resolver(name: str) -> Sequence[str]:
    """The addresses (A and AAAA) the system resolver gives ``name``, looked up
    on the DNS executor. It has no timeout of its own: the caller stops waiting
    (``TrustedProxies``) but must not start another lookup while this one runs,
    because a thread in ``getaddrinfo`` cannot be cancelled."""
    infos = await asyncio.get_running_loop().run_in_executor(
        _dns_executor(), partial(socket.getaddrinfo, name, None, type=socket.SOCK_STREAM)
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
        self._inflight: Dict[str, "asyncio.Future"] = {}  # one lookup per name at most
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
        """The current set; read it once per request. Addresses that came
        from names are dropped here once they are too old, whether or not the
        refresh is still running."""
        snapshot = self._snapshot
        if snapshot.expires_at is not None and self._clock() > snapshot.expires_at:
            snapshot = self._snapshot = ProxySnapshot.of(self._static)
            log.warning(
                "admin gate: the proxy names were not refreshed in time; "
                "only the configured addresses are trusted"
            )
        return snapshot

    @property
    def configured(self) -> bool:
        """Whether any proxy is configured, resolved or not."""
        return bool(self._static or self.names)

    async def _lookup(self, name: str) -> Optional[Sequence[str]]:
        """The answer for ``name``, or None: no answer in time, an error, or a
        lookup of an earlier refresh that is still running (never a second one
        beside it)."""
        pending = self._inflight.get(name)
        if pending is not None:
            if not pending.done():
                return None  # still stuck: wait for it, do not add a thread
            del self._inflight[name]
            if not pending.cancelled():
                pending.exception()  # an old answer is not used; mark it read
        lookup = asyncio.ensure_future(self._resolver(name))
        self._inflight[name] = lookup
        lookup.add_done_callback(lambda f: f.cancelled() or f.exception())  # mark read
        await asyncio.wait({lookup}, timeout=self._timeout)  # does not cancel it
        if not lookup.done():
            return None
        del self._inflight[name]
        if lookup.cancelled() or lookup.exception() is not None:
            return None  # NXDOMAIN, a refused query, a resolver bug: "no answer"
        return lookup.result() or None

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
            return self.snapshot
        answers = await asyncio.gather(*(self._lookup(n) for n in self.names))
        now = self._clock()
        resolved = set()
        oldest = None  # the oldest good answer a trusted address comes from
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
            if addresses:
                resolved.update(addresses)
                at = self._good[name].at
                oldest = at if oldest is None else min(oldest, at)
        found = sorted(resolved, key=lambda a: (a.version, int(a)))  # v4 and v6 mix
        expires = None if oldest is None else oldest + self.interval + self._grace
        new = ProxySnapshot.of(
            (*self._static, *(ipaddress.ip_network(a) for a in found)), expires
        )
        if new != self._snapshot or new.expires_at != self._snapshot.expires_at:
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
        for lookup in self._inflight.values():
            lookup.cancel()
        self._inflight.clear()
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
