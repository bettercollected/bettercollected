"""What the portal's read-only pages show, composed from the store and the
registry. No writes; no secret value, length, prefix or hash ever leaves here.

* Health: service heartbeats (names and numbers), the admin database and its
  Alembic state, and the other schemas' revisions where this role can read them.
* Configuration: the settings registry joined with ``settings.entries`` and the
  env-override *names* services report.
* Metrics: ``admin.platform_counts()`` (counts only), cached for a minute.
* Audit: keyset pages of the audit log, masked again on the way out.
"""

from __future__ import annotations

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
from common.db.schema_guard import EngineRevisionSource, check_revision, read_revisions
from common.settings.inventory import all_specs
from common.settings.registry import SettingSpec, Tier

HEARTBEAT_STALE_SECONDS = 120
METRICS_CACHE_SECONDS = 60
MAX_VALUE_SHOWN = 200
OTHER_SCHEMAS = ("app", "auth", "google")
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


@dataclass(frozen=True)
class SchemaStatus:
    schema: str
    state: str  # current | behind | ahead | missing | readable | unavailable
    current: str
    expected: str


@dataclass(frozen=True)
class Health:
    database_ok: bool
    database_ms: Optional[int]
    admin_schema: Optional[SchemaStatus]
    other_schemas: list[SchemaStatus]
    heartbeats: list[Heartbeat]
    store_revision: Optional[int]

    @property
    def services_alive(self) -> int:
        return sum(1 for h in self.heartbeats if h.alive)

    @property
    def services_stopped(self) -> int:
        return sum(1 for h in self.heartbeats if not h.alive)


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
        beats: list[Heartbeat] = []
        store_revision = None
        if db_ok:
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
                        )
                    )
            except Exception:  # noqa: BLE001 - store tables unreadable: no heartbeats
                beats = []
        return Health(db_ok, db_ms, admin, others, beats, store_revision)

    async def _other_schema(self, schema: str) -> SchemaStatus:
        """The revision of another service's schema when this role can read its
        version table; otherwise "unavailable" (the role has no access to those
        schemas on purpose and no grant is added for this page)."""
        try:
            async with self._engine.connect() as conn:
                current = await read_revisions(conn, schema)
        except Exception:  # noqa: BLE001 - permission denied is the normal case
            current = None
        if not current:
            return SchemaStatus(schema, "unavailable", "", "")
        return SchemaStatus(schema, "readable", ", ".join(current), "")

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
