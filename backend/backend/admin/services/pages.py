"""What the portal's read-only pages show, composed from the store and the
registry. No writes; no secret value, length, prefix or hash ever leaves here.

* Health: service heartbeats (names and numbers), the admin database and its
  Alembic state, the other schemas' Alembic state and their mirror outboxes
  (unresolved/total rows), read through narrow definer functions.
* Configuration: the settings registry joined with ``settings.entries`` and the
  env-override *names* services report.
* Metrics: ``admin.platform_counts()`` (counts only), cached for a minute.
* Audit: keyset pages of the audit log, masked again on the way out.
"""

from __future__ import annotations

import ipaddress
import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.db import MIGRATIONS
from backend.admin.repositories import views as repo
from backend.admin.security.clock import Clock
from backend.admin.services import audit as audit_service
from backend.admin.schema_heads import code_revisions
from common.db.schema_guard import EngineRevisionSource, check_revision, compare_revisions
from common.settings import sso_requirements
from common.settings.inventory import all_specs
from common.settings.registry import SettingSpec, Tier, ValidationError, coerce_value

HEARTBEAT_STALE_SECONDS = 120
METRICS_CACHE_SECONDS = 60
MAX_VALUE_SHOWN = 200
OTHER_SCHEMAS = ("app", "auth", "google")
# the service that owns each of those schemas (and its mirror outbox)
SCHEMA_SERVICE = {"app": "backend", "auth": "auth", "google": "google"}
# services that report to ``settings.service_state`` (the registry's reader names)
REPORTING = frozenset({"backend", "auth", "google", "tasks"})
TIERS = tuple(t.value for t in Tier)
AUDIT_LIMIT_DEFAULT = 50
AUDIT_LIMIT_MAX = 200

SOURCE_STORE = "store"
SOURCE_ENV = "environment"
SOURCE_DEFAULT = "default"
SOURCE_BUILD = "build argument"
SOURCE_ENV_ONLY = "environment only"

_USERINFO = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]*@")
_ACTOR = re.compile(r"^[^\s<>\"'\\]{1,254}$")
_ACTION = re.compile(r"^[a-z0-9_.:-]{1,64}$")


class BadFilter(ValueError):
    """A query parameter failed validation; the message names the parameter only."""

    def __init__(self, name: str):
        super().__init__(name)
        self.name = name


# -- health ---------------------------------------------------------------------
# a process that runs beside its service's main one labels its instance
# "<service>.<role>:<host>" (common.settings.loader.source.instance_id)
COMPONENT_LABELS = {"jobs": "jobs worker"}
# what a heartbeat's write_stores can say about MongoDB: any value naming it
_MONGO_STORE = "mongo"


def component_of(service: str, instance: str) -> str:
    """The component a heartbeat is from, by name: ``jobs worker`` for the
    backend's job worker, ``""`` for the service's main process. Only the known
    roles are named; the instance text is reported by the service itself."""
    prefix, _, _host = instance.partition(":")
    head, _, role = prefix.partition(".")
    return COMPONENT_LABELS.get(role, "") if head == service else ""


@dataclass(frozen=True)
class Heartbeat:
    service: str
    instance: str
    revision_applied: int
    behind: Optional[int]
    restart_pending: bool
    rejected: int
    age_seconds: int
    alive: bool
    component: str = ""
    write_stores: str = ""  # "", "mongo", "postgres" or "mongo,postgres"

    @property
    def writes_mongo(self) -> bool:
        return _MONGO_STORE in self.write_stores.split(",")


@dataclass(frozen=True)
class SchemaStatus:
    schema: str
    state: str  # current | behind | ahead | missing | unknown | unavailable
    current: str
    expected: str


@dataclass(frozen=True)
class OutboxStatus:
    service: str
    store: str
    state: str  # clean | pending | missing | unavailable
    unresolved: Optional[int]
    total: Optional[int]


@dataclass(frozen=True)
class SsoStatus:
    """Single sign-on on one service, by setting name only.

    ``enabled``: ``off`` (default or false in the store), ``on`` (true in the
    store), ``environment`` (set in the service's environment, whose value the
    portal never sees) or ``unknown`` (the service has not reported)."""

    service: str
    enabled: str
    missing: tuple[str, ...] = ()
    missing_optional: tuple[str, ...] = ()

    @property
    def incomplete(self) -> bool:
        return self.enabled in ("on", "environment") and bool(self.missing)


@dataclass(frozen=True)
class Health:
    database_ok: bool
    database_ms: Optional[int]
    admin_schema: Optional[SchemaStatus]
    other_schemas: list[SchemaStatus]
    heartbeats: list[Heartbeat]
    store_revision: Optional[int]
    outbox: list[OutboxStatus] = field(default_factory=list)
    sso: list[SsoStatus] = field(default_factory=list)

    @property
    def sso_incomplete(self) -> bool:
        return any(s.incomplete for s in self.sso)

    @property
    def schemas_not_current(self) -> int:
        schemas = ([self.admin_schema] if self.admin_schema else []) + self.other_schemas
        return sum(1 for s in schemas if s.state != "current")

    @property
    def outbox_unresolved(self) -> int:
        return sum(o.unresolved or 0 for o in self.outbox)

    @property
    def services_alive(self) -> int:
        return sum(1 for h in self.heartbeats if h.alive)

    @property
    def services_stopped(self) -> int:
        return sum(1 for h in self.heartbeats if not h.alive)

    @property
    def jobs_workers_alive(self) -> int:
        return sum(1 for h in self.heartbeats if h.component == "jobs worker" and h.alive)

    @property
    def jobs_workers_stopped(self) -> int:
        return sum(1 for h in self.heartbeats if h.component == "jobs worker" and not h.alive)

    @property
    def mongo_writers(self) -> int:
        """Live instances that still write MongoDB (the 4.0 import window)."""
        return sum(1 for h in self.heartbeats if h.alive and h.writes_mongo)


@dataclass(frozen=True)
class AdminAccess:
    """``ADMIN_ALLOWED_IPS`` as far as the signed-in admin needs it: how many
    entries there are and which one lets this admin's own address in. The other
    entries are not shown (they say where the operator's networks are, which no
    page needs); ``PLATFORM_ADMIN_EMAILS`` is listed in full, as it always was."""

    entries: int
    address: Optional[str]
    matched_entry: Optional[str]
    via_gateway: bool  # the match is the admin network's gateway, not a real client entry


def admin_access(gate: Any, client_ip: Optional[str]) -> Optional[AdminAccess]:
    """None when the page has no gate settings (an embedded app without a gate)."""
    if gate is None:
        return None
    gateway = getattr(gate, "edge_gateway", None)
    networks = tuple(getattr(gate, "allowed_ips", ()))
    gateway_net = ipaddress.ip_network(gateway) if gateway is not None else None
    entries = len(networks) - (1 if gateway_net is not None and gateway_net in networks else 0)
    try:
        address = ipaddress.ip_address(client_ip) if client_ip else None
    except ValueError:
        address = None
    matched = next(
        (n for n in networks
         if address is not None and address.version == n.version and address in n and n != gateway_net),
        None,
    )
    via_gateway = matched is None and address is not None and gateway_net is not None and address in gateway_net
    return AdminAccess(
        entries=max(entries, 0),
        address=str(address) if address is not None else None,
        matched_entry=str(matched) if matched is not None else None,
        via_gateway=via_gateway,
    )


# -- configuration --------------------------------------------------------------
@dataclass(frozen=True)
class ConfigRow:
    key: str
    section: str
    readers: str
    type: str
    secret: bool
    reload: str
    tier: str
    source: str
    overridden: bool
    restart: bool
    value: Optional[str]
    is_set: Optional[bool]
    version: Optional[int]
    changed_by: Optional[str]
    changed_at: Optional[datetime]
    description: str


@dataclass(frozen=True)
class Config:
    rows: list[ConfigRow]
    sections: list[str]
    tiers: tuple
    total: int
    in_store: int
    overridden: int
    restart_pending_services: list[str]


# -- audit ------------------------------------------------------------------------
@dataclass(frozen=True)
class AuditFilters:
    before: Optional[int] = None
    actor: Optional[str] = None
    action: Optional[str] = None
    outcome: Optional[str] = None
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    limit: int = AUDIT_LIMIT_DEFAULT
    raw: dict = field(default_factory=dict)  # what to put back into the form


@dataclass(frozen=True)
class AuditItem:
    seq: int
    id: str
    at: datetime
    actor_kind: str
    actor_email: Optional[str]
    ip: Optional[str]
    action: str
    target_type: Optional[str]
    target_id: Optional[str]
    outcome: str
    request_id: Optional[str]
    before: Any
    after: Any
    detail: Any


@dataclass(frozen=True)
class AuditPage:
    items: list[AuditItem]
    next_before: Optional[int]
    head_seq: Optional[int]
    head_hash_prefix: Optional[str]
    head_at: Optional[datetime]


def parse_audit_filters(params: Any) -> AuditFilters:
    """Validate the query string; raises :class:`BadFilter` naming the parameter."""

    def one(name: str) -> Optional[str]:
        value = params.get(name)
        if value is None or value == "":
            return None
        if not isinstance(value, str) or len(value) > 254:
            raise BadFilter(name)
        return value.strip() or None

    limit = AUDIT_LIMIT_DEFAULT
    raw_limit = one("limit")
    if raw_limit is not None:
        if not raw_limit.isascii() or not raw_limit.isdigit() or not 1 <= int(raw_limit) <= AUDIT_LIMIT_MAX:
            raise BadFilter("limit")
        limit = int(raw_limit)
    before = one("before")
    if before is not None and (
        not before.isascii() or not before.isdigit() or not 1 <= int(before) < 2**62
    ):
        raise BadFilter("before")
    actor = one("actor")
    if actor is not None:
        actor = actor.lower()
        if not _ACTOR.match(actor):
            raise BadFilter("actor")
    action = one("action")
    if action is not None and not _ACTION.match(action):
        raise BadFilter("action")
    outcome = one("outcome")
    if outcome is not None and outcome not in audit_service.OUTCOMES:
        raise BadFilter("outcome")
    since = _moment(one("from"), "from", end=False)
    until = _moment(one("to"), "to", end=True)
    return AuditFilters(
        before=int(before) if before else None, actor=actor, action=action,
        outcome=outcome, since=since, until=until, limit=limit,
        raw={
            k: v
            for k, v in {
                "actor": actor, "action": action, "outcome": outcome,
                "from": one("from"), "to": one("to"),
                "limit": str(limit) if raw_limit else None,
            }.items()
            if v
        },
    )


def _moment(value: Optional[str], name: str, *, end: bool) -> Optional[datetime]:
    """``YYYY-MM-DD`` or an ISO date-time (naive means UTC). A date given as the
    upper bound includes that whole day."""
    if value is None:
        return None
    try:
        if len(value) == 10:
            day = date.fromisoformat(value)
            moment = datetime.combine(day, dtime.min, tzinfo=timezone.utc)
            return moment + timedelta(days=1) if end else moment
        moment = datetime.fromisoformat(value)
    except (ValueError, OverflowError):
        raise BadFilter(name) from None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _display_json(value: Any) -> Any:
    """Masked once more on the way out (rows are masked when written)."""
    if value is None:
        return None
    try:
        return audit_service.mask(repo.parse_json(value))
    except audit_service.AuditError:
        return audit_service.REDACTED


def audit_item(row: Any) -> AuditItem:
    return AuditItem(
        seq=row.seq, id=str(row.id), at=row.at, actor_kind=row.actor_kind,
        actor_email=row.actor_email, ip=str(row.ip) if row.ip is not None else None,
        action=row.action, target_type=row.target_type, target_id=row.target_id,
        outcome=row.outcome, request_id=row.request_id,
        before=_display_json(row.before), after=_display_json(row.after),
        detail=_display_json(row.detail),
    )


def pretty(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, default=str)


def item_json(item: AuditItem) -> dict:
    return {
        "seq": item.seq, "id": item.id, "at": item.at.isoformat(),
        "actor_kind": item.actor_kind, "actor_email": item.actor_email, "ip": item.ip,
        "action": item.action, "target_type": item.target_type,
        "target_id": item.target_id, "outcome": item.outcome,
        "request_id": item.request_id, "before": item.before, "after": item.after,
        "detail": item.detail,
    }


# -- the service ------------------------------------------------------------------
def _origin_only(value: str) -> str:
    """``scheme://host[:port]`` of a URL; anything after it (a path, query or
    fragment can carry a token, as chat-style webhooks do) is hidden."""
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = f":{parts.port}" if parts.port else ""
    except ValueError:
        return "[hidden]"
    if not parts.scheme or not host:
        return "[hidden]"
    more = bool(parts.path.strip("/") or parts.query or parts.fragment)
    return f"{parts.scheme}://{host}{port}" + ("/[path hidden]" if more else "")


def shown_value(raw: Any, is_url: bool = False) -> Optional[str]:
    """A non-secret value as text: bounded; for a URL setting only its origin,
    for other text credentials in URLs removed."""
    if raw is None:
        return None
    text_value = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    if is_url:
        return _origin_only(text_value)
    text_value = _USERINFO.sub(r"\1[removed]@", text_value)
    if len(text_value) > MAX_VALUE_SHOWN:
        text_value = text_value[:MAX_VALUE_SHOWN] + "..."
    return text_value


KNOWN_PROVIDERS = ("self", "google", "typeform", "unknown")


def _known_providers(by_provider: dict) -> dict:
    """Provider names come from stored form settings (user-controlled text), so
    only the known ones are shown by name; the rest are summed as ``other``."""
    shown: dict = {}
    for name, n in by_provider.items():
        key = name if name in KNOWN_PROVIDERS else "other"
        shown[key] = shown.get(key, 0) + n
    return shown


def _stored(entry: Any) -> Any:
    """A live store row's value: True for a secret (only whether it is set is
    known), the decoded value otherwise; None when absent or cleared."""
    if entry is None or entry.cleared:
        return None
    if entry.is_secret:
        return True
    try:
        return repo.parse_json(entry.value) if entry.value is not None else None
    except ValueError:
        return None


_SSO_ENABLED_SPEC = next(s for s in all_specs() if s.key == sso_requirements.ENABLED_KEY)


def _stored_enabled(entry: Any) -> bool:
    """Whether the store row switches single sign-on on, parsed the way the
    services parse it (``coerce_value``: "true", "1", "yes", "on" in any case,
    or a JSON true). A value they cannot use leaves the default, off."""
    value = _stored(entry)
    if value is None:
        return False
    try:
        return coerce_value(_SSO_ENABLED_SPEC, value) is True
    except ValidationError:
        return False


def sso_status(service: str, states: list, entries: dict) -> SsoStatus:
    """Single sign-on on ``service`` from its heartbeats and the store rows.
    Live instances count when there are any; a setting is set when the store
    holds it or every counted instance has it in its environment."""
    rows = [s for s in states if s.service == service]
    if not rows:
        return SsoStatus(service, "unknown")
    alive = [s for s in rows if s.age_seconds <= HEARTBEAT_STALE_SECONDS]
    rows = alive or rows
    env_sets = [set(s.env_overrides or ()) for s in rows]

    def is_set(name: str) -> bool:
        value = _stored(entries.get(name))
        if value not in (None, "", False) and str(value).strip():
            return True
        return all(name in names for names in env_sets)

    if any(sso_requirements.ENABLED_KEY in names for names in env_sets):
        enabled = "environment"
    else:
        enabled = "on" if _stored_enabled(entries.get(sso_requirements.ENABLED_KEY)) else "off"
    if enabled == "off":
        return SsoStatus(service, enabled)
    return SsoStatus(
        service, enabled,
        sso_requirements.missing(service, is_set),
        sso_requirements.missing_optional(service, is_set),
    )


def _write_stores(value: Any) -> str:
    """Only the four values the column allows; anything else counts as not said."""
    return value if value in ("mongo", "postgres", "mongo,postgres") else ""


class PageService:
    def __init__(self, engine: AsyncEngine, clock: Clock):
        self._engine = engine
        self._clock = clock
        self._metrics: Optional[tuple[float, dict]] = None

    # health
    async def health(self) -> Health:
        started = time.monotonic()
        try:
            async with self._engine.connect() as conn:
                db_ok = await repo.ping(conn)
        except Exception:  # noqa: BLE001 - reported as "not reachable"
            db_ok = False
        db_ms = round((time.monotonic() - started) * 1000) if db_ok else None
        admin = None
        if db_ok:
            try:
                check = await check_revision(MIGRATIONS, EngineRevisionSource(self._engine))
                admin = SchemaStatus(
                    "admin", check.state.value, ", ".join(check.current) or "none",
                    ", ".join(check.expected) or "none",
                )
            except Exception:  # noqa: BLE001
                admin = SchemaStatus("admin", "unavailable", "", "")
        others = [await self._other_schema(name) for name in OTHER_SCHEMAS] if db_ok else []
        outbox = [await self._outbox(name) for name in OTHER_SCHEMAS] if db_ok else []
        beats: list[Heartbeat] = []
        store_revision = None
        sso: list[SsoStatus] = []
        if db_ok:
            sso = await self._sso()
            try:
                async with self._engine.connect() as conn:
                    rows = await repo.service_states(conn)
                    store_revision = await repo.manifest_revision(conn)
                for r in rows:
                    behind = (
                        max(store_revision - r.revision_applied, 0)
                        if store_revision is not None
                        else None
                    )
                    beats.append(
                        Heartbeat(
                            r.service, r.instance, r.revision_applied, behind,
                            r.restart_pending, r.rejected, max(int(r.age_seconds), 0),
                            r.age_seconds <= HEARTBEAT_STALE_SECONDS,
                            component_of(r.service, r.instance),
                            _write_stores(r.write_stores),
                        )
                    )
            except Exception:  # noqa: BLE001 - store tables unreadable: no heartbeats
                beats = []
        return Health(db_ok, db_ms, admin, others, beats, store_revision, outbox, sso)

    async def _sso(self) -> list[SsoStatus]:
        """Which settings single sign-on still needs on each service, from the
        names services report as set in their environment and the store's
        live rows (secret values are never selected). Names only."""
        try:
            async with self._engine.connect() as conn:
                states = await repo.service_states(conn)
                entries = {r.key: r for r in await repo.entries_for_display(conn)}
        except Exception:  # noqa: BLE001 - store not readable: nothing to say
            return [SsoStatus(svc, "unknown") for svc in sso_requirements.REQUIRED]
        return [sso_status(svc, states, entries) for svc in sso_requirements.REQUIRED]

    async def _other_schema(self, schema: str) -> SchemaStatus:
        """Another service's schema against the head its deployed code expects.
        The revision comes from that schema's definer function (the admin role
        has no access to the schema itself); "unavailable" when the function
        is missing or refuses (the roles script has not run since this release)."""
        try:
            async with self._engine.connect() as conn:
                current = await repo.schema_revisions(conn, schema)
        except Exception:  # noqa: BLE001 - reported as "unavailable", never the message
            return SchemaStatus(schema, "unavailable", "", "")
        code = code_revisions(schema)
        if code is None:
            shown = ", ".join(current or ()) or "none"
            return SchemaStatus(schema, "unknown", shown, "")
        check = compare_revisions(schema, current, code.heads, code.known)
        return SchemaStatus(
            schema, check.state.value, ", ".join(check.current) or "none",
            ", ".join(check.expected) or "none",
        )

    async def _outbox(self, schema: str) -> OutboxStatus:
        """The Postgres mirror outbox of the service owning ``schema``: counts only."""
        service = SCHEMA_SERVICE[schema]
        try:
            async with self._engine.connect() as conn:
                counts = await repo.outbox_counts(conn, schema)
        except Exception:  # noqa: BLE001 - reported as "unavailable", never the message
            return OutboxStatus(service, "postgres", "unavailable", None, None)
        if counts is None:
            return OutboxStatus(service, "postgres", "missing", None, None)
        unresolved, total = counts
        return OutboxStatus(service, "postgres", "pending" if unresolved else "clean", unresolved, total)

    # configuration
    async def config(self) -> Config:
        specs = sorted(all_specs(), key=lambda s: (s.section, s.key))
        try:
            async with self._engine.connect() as conn:
                entries = {r.key: r for r in await repo.entries_for_display(conn)}
                states = await repo.service_states(conn)
        except Exception:  # noqa: BLE001 - store not migrated yet: show the registry alone
            entries, states = {}, []
        env_names = {n for s in states for n in (s.env_overrides or ())}
        restart_services = sorted({s.service for s in states if s.restart_pending})
        rows = [
            self._config_row(spec, entries.get(spec.key), env_names, restart_services)
            for spec in specs
        ]
        return Config(
            rows=rows,
            sections=sorted({s.section for s in specs}),
            tiers=TIERS,
            total=len(rows),
            in_store=sum(1 for r in rows if r.source == SOURCE_STORE),
            overridden=sum(1 for r in rows if r.overridden),
            restart_pending_services=restart_services,
        )

    @staticmethod
    def _config_row(spec: SettingSpec, entry: Any, env_names: set, restart_services: list) -> ConfigRow:
        base = dict(
            key=spec.key, section=spec.section, readers=", ".join(spec.readers),
            type=spec.type.value, secret=spec.is_secret, reload=spec.reload_class.value,
            tier=spec.tier.value, description=spec.description,
        )
        if spec.tier is Tier.T5:
            source = SOURCE_BUILD if spec.key.startswith("NEXT_PUBLIC_") else SOURCE_ENV_ONLY
            return ConfigRow(
                **base, source=source, overridden=False, restart=False, value=None,
                is_set=None, version=None, changed_by=None, changed_at=None,
            )
        live = entry if entry is not None and not entry.cleared else None
        overridden = spec.key in env_names
        source = SOURCE_ENV if overridden else SOURCE_STORE if live else SOURCE_DEFAULT
        pending = any(s in restart_services for s in spec.readers if s in REPORTING)
        restart = live is not None and pending and spec.reload_class.value == "R"
        value = None
        is_set = None
        if spec.is_secret:
            is_set = overridden or live is not None
        elif not overridden:
            raw = (
                repo.parse_json(live.value)
                if live is not None and live.value is not None
                else spec.default
            )
            value = shown_value(raw, spec.type.value == "url")
        return ConfigRow(
            **base, source=source, overridden=overridden, restart=restart, value=value,
            is_set=is_set, version=entry.version if entry is not None else None,
            changed_by=entry.updated_by if entry is not None else None,
            changed_at=entry.updated_at if entry is not None else None,
        )

    async def restart_pending(self) -> list[str]:
        try:
            async with self._engine.connect() as conn:
                return sorted({s.service for s in await repo.service_states(conn) if s.restart_pending})
        except Exception:  # noqa: BLE001
            return []

    # metrics
    async def metrics(self) -> tuple[Optional[dict], Optional[str]]:
        """(counts, None) or (None, why); cached for a minute."""
        now = time.monotonic()
        if self._metrics and now - self._metrics[0] < METRICS_CACHE_SECONDS:
            return self._metrics[1], None
        try:
            async with self._engine.connect() as conn:
                counts = await repo.platform_counts(conn)
        except Exception as exc:  # noqa: BLE001 - type only, never the message
            return None, type(exc).__name__
        counts = dict(counts)
        counts["forms"] = {**counts["forms"], "by_provider": _known_providers(counts["forms"]["by_provider"])}
        self._metrics = (now, counts)
        return counts, None

    # audit
    async def audit(self, filters: AuditFilters) -> AuditPage:
        async with self._engine.connect() as conn:
            rows = await repo.audit_page(
                conn, before_seq=filters.before, actor=filters.actor,
                action=filters.action, outcome=filters.outcome, since=filters.since,
                until=filters.until, limit=filters.limit,
            )
            head = await repo.audit_head(conn)
        more = len(rows) > filters.limit
        items = [audit_item(r) for r in rows[: filters.limit]]
        return AuditPage(
            items=items,
            next_before=items[-1].seq if more and items else None,
            head_seq=head[0] if head else None,
            head_hash_prefix=head[1].hex()[:16] if head else None,
            head_at=head[2] if head else None,
        )

    async def live_sessions(self, email: str) -> int:
        async with self._engine.connect() as conn:
            return await repo.live_session_count(conn, email.strip().lower(), self._clock.now())
