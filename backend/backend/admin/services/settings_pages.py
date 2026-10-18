"""What the portal's settings pages need beyond ``SettingsService``.

* Fixed notice codes (the only text a redirect can ask a page to show).
* The sealed "pending change": between the page that checks a second-factor code
  and the page that applies the change, a new value is carried only as an
  AES-256-GCM blob bound to the session, the action, the key and the version the
  admin saw, valid for 120 seconds. A secret therefore never appears in HTML.
* Read models for the detail, history, notifications and integrity pages.

Nothing here logs, and no secret value, length, prefix or hash is ever returned.
"""

from __future__ import annotations

import asyncio
import base64
import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.admin.repositories import settings_views as repo
from backend.admin.loops.status import IntegrityStatus, StatusBoard
from backend.admin.security.clock import Clock
from backend.admin.services import pages as pg
from backend.admin.services.settings_store import Problem, SettingsError, SettingsService
from common.settings.inventory import all_specs
from common.settings.registry import (
    KEY_RE,
    Registry,
    Reload,
    SettingSpec,
    Tier,
    ValidationError,
    ValueType,
    is_env_only,
)

from common.settings.loader.proven import LIVE_PROVEN

PENDING_SECONDS = 120
HISTORY_SHOWN = 50
NOTIFICATIONS_SHOWN = 50
VERIFY_TIMEOUT_SECONDS = 30
ACTIONS = ("set", "clear", "restore", "purge_history")
URL_NAMES = {"set": "set", "clear": "clear", "restore": "restore", "purge_history": "purge-history"}

# (kind, text): the complete vocabulary of flash messages
NOTICES: dict[str, tuple[str, str]] = {
    "done_set": ("ok", "The setting was changed."),
    "done_clear": ("ok", "The setting was cleared."),
    "done_restore": ("ok", "The earlier version was restored as a new version."),
    "done_purge": ("ok", "The older secret versions were deleted."),
    "no_change": ("ok", "Nothing changed: the setting already has that value."),
    "stale_version": (
        "error",
        "This setting changed since you opened the page. Review the current state and try again.",
    ),
    "step_up_required": ("error", "A fresh second-factor code is needed for this change."),
    "step_up_invalid": (
        "error",
        "The confirmation expired or does not match this change. Start the change again.",
    ),
    "wrong_code": ("error", "That code was not accepted. Nothing was changed."),
    "locked": ("error", "Too many wrong codes. Wait before trying again."),
    "confirmation_required": ("error", "Type the setting name exactly to confirm this change."),
    "invalid_value": ("error", "The value was not accepted."),
    "managed_by_task": (
        "error",
        "This setting holds key material and is changed only by a maintenance task, not here.",
    ),
    "env_only": ("error", "This setting can only be set in the server's environment."),
    "unknown_key": ("error", "There is no such setting."),
    "not_set": ("error", "The setting is not set, so there is nothing to clear."),
    "not_secret": ("error", "Only secrets keep sealed history that can be purged."),
    "no_such_version": ("error", "That version is not available."),
    "nothing_to_restore": ("error", "That version holds no value to restore."),
    "cannot_open": ("error", "That sealed version could not be opened with the current master key."),
    "invalid_version": ("error", "The request was not understood."),
    "bad_request": ("error", "The request was not understood."),
    "purge_unconfirmed": ("error", "Tick the box to confirm the purge."),
    "rate_limited": ("error", "Please wait a moment before running that again."),
    "failed": ("error", "The change was refused."),
}
_GENERIC = "failed"


def notice_code(code: Optional[str]) -> Optional[str]:
    return code if isinstance(code, str) and code in NOTICES else None


def notice_for_error(error: SettingsError) -> str:
    return error.code if error.code in NOTICES else _GENERIC


def notice_view(code: Optional[str]) -> Optional[dict]:
    code = notice_code(code)
    return {"kind": NOTICES[code][0], "text": NOTICES[code][1]} if code else None


def key_or_none(raw: Any) -> Optional[str]:
    return raw if isinstance(raw, str) and KEY_RE.match(raw) else None


def refusal_code(registry: Registry, key: str) -> Optional[str]:
    """Why ``key`` cannot be edited here (a notice code), or None when it can."""
    try:
        spec = registry.get(key)
    except ValidationError:
        known = next((s for s in all_specs() if s.key == key), None)
        if is_env_only(key) or (known is not None and known.tier is Tier.T5):
            return "env_only"
        return "unknown_key"
    if spec.tier is Tier.T4:
        return "managed_by_task"
    if spec.tier is Tier.T5:
        return "env_only"
    return None


def parse_int(raw: Any, minimum: int = 0) -> Optional[int]:
    if isinstance(raw, str) and raw.isascii() and raw.isdigit() and len(raw) <= 9:
        value = int(raw)
        return value if value >= minimum else None
    return None


def reload_note(spec: SettingSpec) -> tuple[str, str]:
    """``(class name, explanation)`` for the edit page."""
    if spec.reload_class is Reload.H and spec.key in LIVE_PROVEN:
        return "live", "Applies live: services pick up the change within about a minute."
    if spec.reload_class is Reload.B:
        return "build", "Applies to the next build of the web app image; a restart alone is not enough."
    return "restart", "Applies after restart: each reading service uses the new value when it next restarts."


@dataclass(frozen=True)
class FieldKind:
    """How the edit form renders one setting (HTML attributes only; the server validates)."""

    widget: str  # text | password | number | select | textarea | url
    attrs: dict = field(default_factory=dict)
    options: tuple = ()
    hint: str = ""


def field_kind(spec: SettingSpec) -> FieldKind:
    if spec.is_secret:
        return FieldKind("password", {"autocomplete": "new-password", "maxlength": "1024"})
    t = spec.type
    if t is ValueType.BOOL:
        return FieldKind("select", options=("true", "false"))
    if t is ValueType.ENUM:
        return FieldKind("select", options=tuple(spec.choices))
    if t is ValueType.INT:
        attrs = {"step": "1", "inputmode": "numeric"}
    elif t is ValueType.FLOAT:
        attrs = {"step": "any", "inputmode": "decimal"}
    else:
        attrs = {}
    if t in (ValueType.INT, ValueType.FLOAT):
        if spec.min_value is not None:
            attrs["min"] = f"{spec.min_value:g}"
        if spec.max_value is not None:
            attrs["max"] = f"{spec.max_value:g}"
        return FieldKind("number", attrs)
    if t is ValueType.JSON:
        return FieldKind("textarea", {"rows": "6", "spellcheck": "false"}, hint="A JSON object or array.")
    if t is ValueType.URL:
        return FieldKind("url", {"maxlength": "2048", "spellcheck": "false"}, hint="An absolute URL.")
    hint = {"cidr_list": "Comma-separated addresses or CIDR ranges.", "host": "A host name or address."}.get(
        spec.format, ""
    )
    if spec.max_length:
        attrs["maxlength"] = str(spec.max_length)
    return FieldKind("text", {**attrs, "spellcheck": "false"}, hint=hint)


def as_form_text(spec: SettingSpec, value: Any) -> str:
    """A stored non-secret value as text for the field (never for secrets)."""
    if value is None or spec.is_secret:
        return ""
    if spec.type is ValueType.BOOL:
        return "true" if value else "false"
    if spec.type is ValueType.JSON:
        return json.dumps(value, indent=2, ensure_ascii=False)
    return value if isinstance(value, str) else str(value)


def display_value(spec: SettingSpec, value: Any) -> Optional[str]:
    return None if spec.is_secret else pg.shown_value(value)


# -- the sealed pending change ----------------------------------------------------------
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text_value: str) -> bytes:
    return base64.urlsafe_b64decode(text_value + "=" * (-len(text_value) % 4))


def _aad(session_id: Any, action: str, key: str, version: int, expiry: int) -> bytes:
    return f"settings-pending|{session_id}|{action}|{key}|{version}|{expiry}".encode()


def seal_pending(
    box_key: bytes, clock: Clock, session_id: Any, action: str, key: str, version: int, material: Any
) -> str:
    expiry = int(clock.time()) + PENDING_SECONDS
    nonce = secrets.token_bytes(12)
    body = json.dumps({"m": material}, allow_nan=False).encode()
    sealed = AESGCM(box_key).encrypt(nonce, body, _aad(session_id, action, key, version, expiry))
    return f"{expiry}.{_b64(nonce)}.{_b64(sealed)}"


MISSING = object()


def open_pending(
    box_key: bytes, clock: Clock, session_id: Any, action: str, key: str, version: int, blob: Any
) -> Any:
    """The sealed material, or ``MISSING`` for anything wrong with the blob
    (tampered, expired, for another session, action, key or version)."""
    try:
        if not isinstance(blob, str) or len(blob) > 8192 or blob.count(".") != 2:
            return MISSING
        raw_expiry, nonce, sealed = blob.split(".")
        if not (raw_expiry.isascii() and raw_expiry.isdigit()):
            return MISSING
        expiry = int(raw_expiry)
        if clock.time() >= expiry:
            return MISSING
        body = AESGCM(box_key).decrypt(
            _unb64(nonce), _unb64(sealed), _aad(session_id, action, key, version, expiry)
        )
        return json.loads(body)["m"]
    except (InvalidTag, ValueError, KeyError, TypeError):
        return MISSING


def is_missing(material: Any) -> bool:
    return material is MISSING


# -- read models --------------------------------------------------------------------------
@dataclass(frozen=True)
class Detail:
    spec: SettingSpec
    row: pg.ConfigRow
    version: int
    cleared: bool
    form_value: str
    kind: FieldKind
    reload_class: str
    reload_text: str
    editable: Optional[str]  # None, or the notice code saying why not


@dataclass(frozen=True)
class HistoryItem:
    version: int
    action: str
    source: str
    actor: str
    at: datetime
    secret: bool
    cleared: bool
    value: Optional[str]
    current: bool
    restorable: bool


@dataclass(frozen=True)
class NotificationItem:
    kind: str
    status: str
    attempts: int
    created_at: datetime
    sent_at: Optional[datetime]
    setting: str
    tier: str
    action: str
    version: str


class SettingsPages:
    def __init__(self, engine: AsyncEngine, service: SettingsService, pages: pg.PageService, clock: Clock):
        self._engine = engine
        self.service = service
        self._pages = pages
        self._clock = clock

    @property
    def registry(self) -> Registry:
        return self.service.registry

    async def detail(self, key: str) -> Optional[Detail]:
        spec = next((s for s in all_specs() if s.key == key), None)
        if spec is None:
            return None
        config = await self._pages.config()
        row = next((r for r in config.rows if r.key == key), None)
        if row is None:
            return None
        version, cleared, raw = 0, False, None
        if spec.tier not in (Tier.T5,):
            try:
                async with self._engine.connect() as conn:
                    found = await repo.entry_version(conn, key)
            except Exception:  # noqa: BLE001 - store not migrated: show as never written
                found = None
            if found is not None:
                version, cleared, raw = found
        shown = raw if raw is not None else (None if spec.is_secret else spec.default)
        cls, text_value = reload_note(spec)
        return Detail(
            spec, row, version, cleared, as_form_text(spec, shown), field_kind(spec), cls,
            text_value, refusal_code(self.registry, key),
        )

    async def history(self, key: str) -> list[HistoryItem]:
        async with self._engine.connect() as conn:
            current = await repo.entry_version(conn, key)
            rows = await repo.history_for_display(conn, key, HISTORY_SHOWN)
        now = current[0] if current else None
        return [
            HistoryItem(
                version=r.version, action=r.action, source=r.source, actor=r.actor, at=r.at,
                secret=r.is_secret, cleared=r.cleared, value=pg.shown_value(
                    pg.repo.parse_json(r.value) if r.value is not None else None
                ),
                current=r.version == now,
                restorable=(
                    r.version != now and not r.cleared and (r.has_blob if r.is_secret else True)
                ),
            )
            for r in rows
        ]

    async def notifications(self) -> list[NotificationItem]:
        async with self._engine.connect() as conn:
            rows = await repo.recent_notifications(conn, NOTIFICATIONS_SHOWN)
        return [
            NotificationItem(
                r.kind, r.status, r.attempts, r.created_at, r.sent_at, r.setting or "-",
                r.tier or "-", r.action or "-", r.version or "-",
            )
            for r in rows
        ]

    async def run_verify(self, board: StatusBoard) -> IntegrityStatus:
        """One bounded verification; the result (keys and reason codes only) goes
        on the shared status board, where the shell banner reads it."""
        found: list[Problem] = await asyncio.wait_for(
            self.service.verify(), timeout=VERIFY_TIMEOUT_SECONDS
        )
        problems = tuple(sorted({(p.key[:64], p.reason[:48]) for p in found}))
        board.integrity = IntegrityStatus(not problems, problems, self._clock.now())
        return board.integrity


def step_up_for(service: SettingsService, action: str, key: str, material: Any, version: int, email: str, now: datetime):
    """The service-level step-up for an action whose route token was just consumed."""
    from backend.admin.services.settings_store import StepUp

    return StepUp(
        service.action_hash(action, key, material, version), email, now + timedelta(seconds=60)
    )


