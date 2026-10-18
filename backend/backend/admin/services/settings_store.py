"""The settings store's write service.

Every change (set, clear, restore, purge, one-time import, re-wrap) runs in ONE
transaction on one connection: take the writer lock, bump the version, write the
entry and its history row with a fresh signature, rebuild and re-sign the
manifest, append the audit row (fail closed: an audit failure rolls the change
back), and enqueue a notification for tier T2 and T3 changes.

Nothing here logs, prints or returns a value. Errors carry a code and the key
name only. Secrets are sealed with ``SectionKeys.seal`` (a fresh data key per
write) and appear in the audit log only as ``"set"`` / ``"cleared"`` plus a
keyed digest.

Step-up protocol (the portal wires it): a mutating call for a T2/T3 setting
takes a :class:`StepUp` the caller got from the step-up module after verifying
a fresh second factor and consuming a single-use token. The service checks that
the token is bound to exactly this action (``SettingsService.action_hash``),
is unexpired and belongs to the acting admin; it cannot check single use.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Optional

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from backend.admin.repositories import settings as repo
from backend.admin.services import audit
from common.configs import shipped_secrets
from common.settings.canonical import (
    SettingRow,
    canonical_json,
    canonical_manifest,
    lp,
    u64,
)
from common.settings.keys import SectionKeys
from common.settings.registry import (
    Registry,
    SettingSpec,
    Tier,
    ValidationError,
    default_registry,
    is_env_only,
)
from common.settings.signing import Manifest, sign_manifest, verify_manifest

HISTORY_KEEP = 5  # encrypted versions kept per secret
REWRAP_BATCH = 50
_ACTION_DOMAIN = b"bc-settings-action-v1"
_DIGEST_DOMAIN = b"bc-settings-digest-v1"
TIERS_WITH_NOTICE = (Tier.T2, Tier.T3)
TIERS_NEEDING_STEP_UP = (Tier.T2, Tier.T3)


class SettingsError(Exception):
    """A refusal. ``code`` is a short stable word; the message never has a value."""

    def __init__(self, code: str, key: str = "", detail: str = ""):
        self.code = code
        self.key = key
        self.detail = detail
        super().__init__(f"{key or 'settings'}: {code}" + (f" ({detail})" if detail else ""))


@dataclass(frozen=True)
class Actor:
    kind: str  # admin | cli | system
    email: Optional[str] = None
    session_id: Optional[str] = None
    ip: Optional[str] = None
    ua: Optional[str] = None
    request_id: Optional[str] = None

    @property
    def label(self) -> str:
        return (self.email or self.kind)[:320]

    @property
    def source(self) -> str:
        return {"admin": "portal", "cli": "cli"}.get(self.kind, "task")


@dataclass(frozen=True)
class StepUp:
    """A verified, single-use step-up, bound to one action."""

    action_hash: str
    actor_email: str
    expires_at: datetime


@dataclass(frozen=True)
class Change:
    key: str
    version: int
    revision: int
    changed: bool = True
    audit_seq: Optional[int] = None


@dataclass(frozen=True)
class Problem:
    key: str
    reason: str


@dataclass(frozen=True)
class RewrapResult:
    rewrapped: int
    resigned: int
    batches: int


def shipped_secret_problems(key: str, value: str) -> list[str]:
    return shipped_secrets.secret_problems(jwt_secrets={key: value})


def store_registry() -> Registry:
    """The registry the store validates with: strength checks for secrets."""
    return default_registry(secret_problems=shipped_secret_problems)


def value_digest(keys: SectionKeys, spec: SettingSpec, key: str, version: int, material: Any) -> str:
    """Digest of what a version holds, for the audit cross-check. Ordinary
    values are public in the audit row anyway (plain SHA-256); a secret's is
    keyed (HMAC), so it reveals nothing without the master key. ``material`` is
    the value, the plaintext, or None for a cleared setting."""
    if material is None:
        kind, payload = b"c", b""
    elif spec.is_secret:
        kind, payload = b"s", str(material).encode("utf-8")
    else:
        kind, payload = b"v", canonical_json(material).encode("utf-8")
    message = lp(_DIGEST_DOMAIN) + lp(key.encode()) + u64(version) + lp(kind) + lp(payload)
    if spec.is_secret and material is not None:
        return hmac.new(keys.signing_key(), message, hashlib.sha256).hexdigest()
    return hashlib.sha256(message).hexdigest()


def manifest_entries(rows: Iterable[repo.EntryRow]) -> dict:
    return {r.key: (r.version, r.sig, tuple(sorted(r.readers))) for r in rows if not r.cleared}


class SettingsService:
    def __init__(
        self,
        engine: AsyncEngine,
        registry: Registry,
        keys: SectionKeys,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        step_up_max_age: timedelta = timedelta(seconds=120),
    ):
        self._engine = engine
        self.registry = registry
        self.keys = keys
        self._clock = clock
        self._max_age = step_up_max_age

    # ---------------------------------------------------------------- guards

    def _spec(self, key: str) -> SettingSpec:
        try:
            return self.registry.get(key)
        except ValidationError:
            if isinstance(key, str) and is_env_only(key):
                raise SettingsError("env_only", key[:64]) from None
            raise SettingsError("unknown_key", str(key)[:64]) from None

    def _settable(self, spec: SettingSpec) -> None:
        if spec.tier is Tier.T4:
            raise SettingsError("managed_by_task", spec.key)
        if spec.tier is Tier.T5:
            raise SettingsError("env_only", spec.key)

    def action_hash(self, action: str, key: str, material: Any = None) -> str:
        """What a step-up must be bound to: the action, the key and (for a
        set) the new value, keyed so the hash does not reveal a secret."""
        body = b"" if material is None else canonical_json(material).encode("utf-8")
        message = lp(_ACTION_DOMAIN) + lp(action.encode()) + lp(key.encode()) + lp(body)
        return hmac.new(self.keys.signing_key(), message, hashlib.sha256).hexdigest()

    def _gate(
        self,
        spec: SettingSpec,
        action: str,
        material: Any,
        actor: Actor,
        step_up: Optional[StepUp],
        confirmation: Optional[str],
    ) -> None:
        if actor.kind == "admin" and not actor.email:
            raise SettingsError("actor_required", spec.key)
        if spec.tier not in TIERS_NEEDING_STEP_UP:
            return
        if step_up is None:
            raise SettingsError("step_up_required", spec.key)
        expected = self.action_hash(action, spec.key, material)
        now = self._clock()
        if (
            not hmac.compare_digest(step_up.action_hash, expected)
            or step_up.expires_at <= now
            or step_up.expires_at > now + self._max_age
            or (actor.email or "").lower() != step_up.actor_email.lower()
        ):
            raise SettingsError("step_up_invalid", spec.key)
        if spec.tier is Tier.T3 and confirmation != spec.key:
            raise SettingsError("confirmation_required", spec.key)

    def _validate(self, spec: SettingSpec, value: Any) -> Any:
        try:
            return self.registry.validate(spec.key, value)
        except ValidationError as exc:
            raise SettingsError("invalid_value", spec.key, exc.reason) from None

    # ----------------------------------------------------------- operations

    async def set(
        self,
        key: str,
        value: Any,
        actor: Actor,
        *,
        step_up: Optional[StepUp] = None,
        confirmation: Optional[str] = None,
    ) -> Change:
        spec = self._spec(key)
        self._settable(spec)
        new = self._validate(spec, value)
        self._gate(spec, "set", new, actor, step_up, confirmation)
        return await self._single(spec, "set", new, actor, history="set")

    async def clear(
        self,
        key: str,
        actor: Actor,
        *,
        step_up: Optional[StepUp] = None,
        confirmation: Optional[str] = None,
    ) -> Change:
        spec = self._spec(key)
        self._settable(spec)
        self._gate(spec, "clear", None, actor, step_up, confirmation)
        return await self._single(spec, "clear", None, actor, history="clear")

    async def restore(
        self,
        key: str,
        version: int,
        actor: Actor,
        *,
        step_up: Optional[StepUp] = None,
        confirmation: Optional[str] = None,
    ) -> Change:
        spec = self._spec(key)
        self._settable(spec)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise SettingsError("invalid_version", key)
        self._gate(spec, "restore", version, actor, step_up, confirmation)
        return await self._single(spec, "restore", version, actor, history="restore")

    async def purge_history(
        self, key: str, actor: Actor, *, step_up: Optional[StepUp] = None, confirmation: Optional[str] = None
    ) -> int:
        """Delete every encrypted version of ``key`` except the current one."""
        spec = self._spec(key)
        self._settable(spec)
        if not spec.is_secret:
            raise SettingsError("not_secret", key)
        self._gate(spec, "purge_history", None, actor, step_up, confirmation)
        async with self._engine.begin() as conn:
            revision = await repo.lock(conn)
            current = await repo.get_entry(conn, key, for_update=True)
            if current is None:
                raise SettingsError("not_set", key)
            deleted = await repo.prune_history(conn, key, current.version)
            await audit.write(
                conn,
                "settings.purge_history",
                "setting",
                key,
                None,
                None,
                "success",
                detail={"deleted": deleted, "revision": revision},
                **_audit_actor(actor),
            )
        return deleted

    async def import_once(self, key: str, value: Any, actor: Actor) -> Optional[Change]:
        """Write ``key`` only if the store has never held it (any tier except
        T5, T4 included): the CLI import and task paths. Returns None when the
        key exists, a tombstone included. Never needs a step-up."""
        if actor.kind == "admin":
            raise SettingsError("not_for_admins", key)
        spec = self._spec(key)
        if spec.tier is Tier.T5:
            raise SettingsError("env_only", key)
        new = self._validate(spec, value)
        return await self._single(spec, "import", new, actor, history="import", only_new=True)

    # ------------------------------------------------------------ the writer

    async def _single(
        self,
        spec: SettingSpec,
        action: str,
        arg: Any,
        actor: Actor,
        *,
        history: str,
        only_new: bool = False,
    ) -> Optional[Change]:
        key = spec.key
        async with self._engine.begin() as conn:
            revision = await repo.lock(conn)
            current = await repo.get_entry(conn, key, for_update=True)
            if only_new and current is not None:
                return None
            plain: Any
            if action == "clear":
                if current is None or current.cleared:
                    raise SettingsError("not_set", key)
                plain = None
            elif action == "restore":
                plain = await self._restored(conn, spec, arg)
            else:
                plain = arg
                if (
                    not spec.is_secret
                    and current is not None
                    and not current.cleared
                    and canonical_json(current.value) == canonical_json(plain)
                ):
                    return Change(key, current.version, revision, changed=False)
            return await self._write(conn, spec, current, plain, actor, history, revision)

    async def _restored(self, conn: AsyncConnection, spec: SettingSpec, version: int) -> Any:
        old = await repo.get_history(conn, spec.key, version)
        if old is None:
            raise SettingsError("no_such_version", spec.key)
        if old.cleared:
            raise SettingsError("nothing_to_restore", spec.key)
        if spec.is_secret:
            if old.blob is None:
                raise SettingsError("nothing_to_restore", spec.key)
            try:
                plain = self.keys.open(old.section, spec.key, old.version, old.blob)
            except Exception:  # noqa: BLE001 - never carry the cause
                raise SettingsError("cannot_open", spec.key) from None
        else:
            plain = old.value
        return self._validate(spec, plain)

    async def _write(
        self,
        conn: AsyncConnection,
        spec: SettingSpec,
        current: Optional[repo.EntryRow],
        plain: Any,
        actor: Actor,
        history_action: str,
        revision: int,
        *,
        audit_action: Optional[str] = None,
    ) -> Change:
        key = spec.key
        cleared = plain is None
        version = 1 if current is None else current.version + 1
        now = await repo.db_now(conn)
        blob = None
        value = None
        if not cleared:
            if spec.is_secret:
                blob = self.keys.seal(spec.section, key, version, plain)
            else:
                value = plain
        entry = repo.EntryRow(
            key=key,
            section=spec.section,
            readers=tuple(sorted(spec.readers)),
            is_secret=spec.is_secret,
            reload_class=spec.reload_class.value,
            tier=spec.tier.value,
            value=value,
            blob=blob,
            cleared=cleared,
            version=version,
            source="import" if history_action == "import" else actor.source,
            updated_by=actor.label,
            updated_at=now,
            sig="",
        )
        try:
            signed = self.keys.sign_row(entry.to_setting_row())
        except Exception:  # noqa: BLE001
            raise SettingsError("cannot_sign", key) from None
        entry = _with_sig(entry, signed.sig)
        if current is None:
            await repo.insert_entry(conn, entry)
        else:
            await repo.update_entry(conn, entry)
        await repo.insert_history(conn, entry, action=history_action, actor=actor.label, at=now)
        if spec.is_secret:
            await repo.prune_history(conn, key, version - HISTORY_KEEP + 1)
        new_revision = await self._rebuild_manifest(conn, revision)
        digest = value_digest(self.keys, spec, key, version, None if cleared else plain)
        before = _state(spec, current, current_digest=None)
        after = _state(spec, entry, current_digest=digest, present=not cleared)
        written = await audit.write(
            conn,
            audit_action or f"settings.{history_action}",
            "setting",
            key,
            before,
            after,
            "success",
            detail={"revision": new_revision, "tier": spec.tier.value},
            **_audit_actor(actor),
        )
        if spec.tier in TIERS_WITH_NOTICE:
            await repo.enqueue_notification(
                conn,
                "settings.changed",
                {
                    "setting": key,
                    "tier": spec.tier.value,
                    "action": history_action,
                    "version": version,
                    "actor": actor.label,
                },
                written.seq,
            )
        return Change(key, version, new_revision, True, written.seq)

    async def _rebuild_manifest(self, conn: AsyncConnection, revision: int) -> int:
        rows = await repo.list_entries(conn)
        new_revision = revision + 1
        entries = manifest_entries(rows)
        manifest = sign_manifest(new_revision, entries, self.keys.signing_key())
        digest = hashlib.sha256(canonical_manifest(new_revision, entries)).hexdigest()
        await repo.write_manifest(
            conn, new_revision, digest, manifest.to_json()["entries"], manifest.sig
        )
        return new_revision

    # ---------------------------------------------------------------- rewrap

    async def rewrap(self, actor: Actor) -> RewrapResult:
        """Re-wrap every data key under the current master key and re-sign every
        row that the current key did not sign, in batches under the writer lock.
        Values and versions do not change. Needs ``master_previous`` on the keys
        while old material remains; with none to do it changes nothing."""
        async with self._engine.connect() as conn:
            keys = [e.key for e in await repo.list_entries(conn)]
        rewrapped = resigned = batches = 0
        for start in range(0, len(keys), REWRAP_BATCH):
            chunk = keys[start : start + REWRAP_BATCH]
            async with self._engine.begin() as conn:
                revision = await repo.lock(conn)
                touched = 0
                for entry in await repo.list_entries(conn, chunk, for_update=True):
                    did_wrap, did_sign = await self._rewrap_one(conn, entry, actor)
                    rewrapped += did_wrap
                    resigned += did_sign
                    touched += did_wrap or did_sign
                if not touched:
                    continue
                batches += 1
                new_revision = await self._rebuild_manifest(conn, revision)
                await audit.write(
                    conn,
                    "settings.rewrap",
                    "settings_store",
                    None,
                    None,
                    None,
                    "success",
                    detail={"revision": new_revision, "keys": touched},
                    **_audit_actor(actor),
                )
        return RewrapResult(rewrapped, resigned, batches)

    async def _rewrap_one(self, conn: AsyncConnection, entry: repo.EntryRow, actor: Actor) -> tuple[int, int]:
        try:
            spec = self.registry.get(entry.key)
        except ValidationError:
            raise SettingsError("unknown_key", entry.key) from None
        blob = entry.blob
        wrapped = 0
        try:
            if blob is not None and self.keys.needs_rewrap(entry.section, blob):
                blob = self.keys.rewrap(entry.section, entry.key, entry.version, blob)
                wrapped = 1
            for old in await repo.list_history(conn, entry.key):
                if old.blob is not None and self.keys.needs_rewrap(old.section, old.blob):
                    await repo.update_history_blob(
                        conn,
                        entry.key,
                        old.version,
                        self.keys.rewrap(old.section, entry.key, old.version, old.blob),
                    )
            candidate = _with_blob(entry, blob)
            sig = self.keys.sign_row(candidate.to_setting_row()).sig
        except SettingsError:
            raise
        except Exception:  # noqa: BLE001 - class only, never the cause
            raise SettingsError("cannot_rewrap", entry.key) from None
        if sig == entry.sig and not wrapped:
            return 0, 0
        await repo.update_blob_sig(conn, entry.key, blob, sig)
        if spec.is_secret and not entry.cleared and blob is not None:
            plain = self.keys.open(entry.section, entry.key, entry.version, blob)
            digest = value_digest(self.keys, spec, entry.key, entry.version, plain)
            await audit.write(
                conn,
                "settings.rewrap_key",
                "setting",
                entry.key,
                None,
                _state(spec, entry, current_digest=digest, present=True),
                "success",
                **_audit_actor(actor),
            )
        return wrapped, 1 if sig != entry.sig else 0

    # ---------------------------------------------------------------- verify

    async def verify(self) -> list[Problem]:
        """Every problem in the store, as ``(key, reason)``; ``*`` is the
        manifest as a whole. Reads secrets in memory only to compare digests."""
        problems: list[Problem] = []
        async with self._engine.connect() as conn:
            entries = await repo.list_entries(conn)
            stored = await repo.get_manifest(conn)
            audited = await repo.latest_audited_versions(conn)
            audited_revision = await repo.max_audited_revision(conn)

        for e in entries:
            if e.key not in self.registry:
                problems.append(Problem(e.key, "unknown_key"))
                continue
            spec = self.registry.get(e.key)
            try:
                if not self.keys.verify_row(e.to_setting_row()):
                    problems.append(Problem(e.key, "bad_signature"))
                    continue
            except Exception:  # noqa: BLE001
                problems.append(Problem(e.key, "bad_signature"))
                continue
            problems.extend(self._cross_check(spec, e, audited.get(e.key)))

        problems.extend(self._check_manifest(entries, stored, audited_revision))
        return problems

    def _cross_check(self, spec: SettingSpec, e: repo.EntryRow, record: Optional[tuple]) -> list[Problem]:
        if record is None:
            return [Problem(e.key, "no_audit_record")]
        version, digest = record
        if version != e.version:
            return [Problem(e.key, "audit_version_mismatch")]
        try:
            if e.cleared:
                material = None
            elif spec.is_secret:
                material = self.keys.open(e.section, e.key, e.version, e.blob or "")
            else:
                material = e.value
            expected = value_digest(self.keys, spec, e.key, e.version, material)
        except Exception:  # noqa: BLE001
            return [Problem(e.key, "cannot_open")]
        if not hmac.compare_digest(expected, digest):
            return [Problem(e.key, "audit_digest_mismatch")]
        return []

    def _check_manifest(self, entries: list, stored: Any, audited_revision: int) -> list[Problem]:
        out: list[Problem] = []
        revision = stored["revision"]
        live = manifest_entries(entries)
        if revision == 0:
            if live:
                out.append(Problem("*", "manifest_missing"))
            return out
        manifest = Manifest(revision, stored["entries"], stored["sig"])
        if not self.keys.verify_manifest(manifest):
            out.append(Problem("*", "manifest_bad_signature"))
        if revision < audited_revision:
            out.append(Problem("*", "manifest_rollback"))
        signed = manifest.entries
        for key in sorted(set(signed) | set(live)):
            if key not in live:
                out.append(Problem(key, "row_missing"))
            elif key not in signed:
                out.append(Problem(key, "manifest_missing_key"))
            elif signed[key] != (live[key][0], live[key][1], live[key][2]):
                out.append(Problem(key, "manifest_mismatch"))
        return out


# ------------------------------------------------------------------- helpers


def _with_sig(e: repo.EntryRow, sig: str) -> repo.EntryRow:
    from dataclasses import replace

    return replace(e, sig=sig)


def _with_blob(e: repo.EntryRow, blob: Optional[str]) -> repo.EntryRow:
    from dataclasses import replace

    return replace(e, blob=blob)


def _state(
    spec: SettingSpec,
    entry: Optional[repo.EntryRow],
    *,
    current_digest: Optional[str],
    present: Optional[bool] = None,
) -> dict:
    """The audit shape of one side of a change (never a secret's value)."""
    if present is None:
        present = entry is not None and not entry.cleared
    if spec.is_secret:
        shown: Any = "x" if present else None  # only whether it is set is recorded
    else:
        shown = entry.value if present and entry is not None else None
    payload = audit.setting_payload(spec.key, shown, secret=spec.is_secret)
    payload["version"] = entry.version if entry is not None else 0
    if current_digest is not None:
        payload["digest"] = current_digest
    return payload


def _audit_actor(actor: Actor) -> dict:
    return {
        "actor_kind": actor.kind,
        "actor_email": actor.email,
        "session_id": actor.session_id,
        "ip": actor.ip,
        "ua": actor.ua,
        "request_id": actor.request_id,
    }
