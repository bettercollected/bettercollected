"""Append-only audit log with an HMAC hash chain.

``row_hash = HMAC-SHA256(audit_key, prev_hash || canonical_json(row))`` is
computed here, with a key the database never sees, so someone with only
database access can neither forge nor silently edit history. ``audit-verify``
recomputes the chain; the periodic ``audit.checkpoint`` stdout lines let an
operator spot the one thing a chain alone cannot show, deleted tail rows.

``write`` runs on the caller's connection and transaction and never swallows an
error: if the audit row cannot be written, the action it describes rolls back.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection

from backend.admin.repositories import audit as repo
from backend.admin.security.keys import admin_key

# Duplicated as literals in migration 0003 (frozen); a test asserts they agree.
GENESIS_HASH = hashlib.sha256(b"bettercollected/admin/audit/genesis/v1").digest()

# Version of the ``admin/audit`` subkey new rows are signed with. Each row stores
# the version it used (and hashes it), so rotating the master key or this version
# never breaks verification of older rows.
AUDIT_KEY_VERSION = 1

ACTOR_KINDS = frozenset({"admin", "cli", "system", "anonymous"})
OUTCOMES = frozenset({"success", "failure", "denied"})

MAX_PAYLOAD_BYTES = 8 * 1024
MAX_STRING = 256
MAX_ITEMS = 50
MAX_DEPTH = 6
CHECKPOINT_EVERY = 100
REDACTED = "[redacted]"

# The one exception to the deny-list: a field literally named ``secret`` whose
# value is one of these markers says *whether* a secret setting is set, never
# what it is, so it survives masking.
SECRET_MARKERS = ("set", "cleared")

_DENY = re.compile(
    r"secret|token|password|passwd|pass(?!ed|ing|port|age|through)|pwd|key|code|otp|hash"
    r"|authorization|auth(?!or)|cookie|seed|private|dsn|url|credential|bearer|jwt"
    r"|session(?!_?id)|signature|salt",
    re.IGNORECASE,
)
_HASHED_FIELDS = (
    "id",
    "at",
    "actor_kind",
    "actor_email",
    "session_id",
    "ip",
    "ua",
    "action",
    "target_type",
    "target_id",
    "outcome",
    "before",
    "after",
    "detail",
    "request_id",
    "key_version",
)


class AuditError(RuntimeError):
    """The audit row could not be built or written."""


class UnmaskableValue(AuditError):
    """A payload holds a value of a type ``mask()`` does not know. Refused rather
    than stringified: an object's ``str()`` (a model with a password field, an
    exception with a DSN) can carry exactly what masking exists to remove."""


class AuditPayloadTooLarge(AuditError):
    """before/after/detail is 8 KB or more after masking."""


# -- masking and canonical form -------------------------------------------------
def clean_text(value: str) -> str:
    """Text Postgres will accept: no NULs, no lone surrogates (they become ``?``)."""
    return value.replace("\x00", "").encode("utf-8", "replace").decode("utf-8")


def mask(value: Any, _depth: int = 0) -> Any:
    """A JSON-safe, size-bounded copy of ``value`` with every value under a
    deny-listed key name replaced. Floats, UUIDs and datetimes become strings so
    the stored JSON round-trips byte for byte; any other type raises
    :class:`UnmaskableValue`."""
    if _depth > MAX_DEPTH:
        return "[max-depth]"
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, str):
        value = clean_text(value)
        if len(value) > MAX_STRING:
            return f"{value[:MAX_STRING]}...[truncated {len(value) - MAX_STRING}]"
        return value
    if isinstance(value, (float, uuid.UUID, datetime)):
        return mask(
            value.isoformat() if isinstance(value, datetime) else str(value), _depth
        )
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= MAX_ITEMS:
                out["[truncated]"] = len(value) - MAX_ITEMS
                break
            if not isinstance(k, (str, int)):
                raise UnmaskableValue(f"unsupported key type {type(k).__name__}")
            name = mask(str(k), MAX_DEPTH)
            keep_marker = k == "secret" and v in SECRET_MARKERS
            denied = _DENY.search(str(k)) and not keep_marker
            out[name] = REDACTED if denied else mask(v, _depth + 1)
        return out
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        masked = [mask(v, _depth + 1) for v in items[:MAX_ITEMS]]
        if len(items) > MAX_ITEMS:
            masked.append(f"[truncated {len(items) - MAX_ITEMS}]")
        return masked
    raise UnmaskableValue(f"unsupported value type {type(value).__name__}")


def setting_payload(setting: str, value: Any, *, secret: bool) -> dict[str, Any]:
    """The audit shape for a setting change (use it for ``before`` and ``after``).

    ``{"setting": name, "value": v}`` for an ordinary setting; for one the
    registry flags as secret, ``{"setting": name, "secret": "set" | "cleared"}``
    and the value is never part of the payload. Callers pass values that are
    already safe: ``mask()`` only looks at field names, so a planted secret
    inside the *string* of a ``value`` field would be stored. Never put a secret
    setting's value in ``value``; this helper makes that the default path.
    """
    if secret:
        present = value is not None and value != ""
        return {"setting": setting, "secret": "set" if present else "cleared"}
    return {"setting": setting, "value": value}


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _bounded(name: str, value: Any) -> Any:
    masked = mask(value)
    if masked is not None and len(canonical_json(masked)) >= MAX_PAYLOAD_BYTES:
        raise AuditPayloadTooLarge(f"audit {name} is {MAX_PAYLOAD_BYTES} bytes or more")
    return masked


def _at_text(at: datetime) -> str:
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    """The hashed form of a row (what ``write`` computed, what ``verify`` rebuilds)."""
    out: dict[str, Any] = {}
    for field in _HASHED_FIELDS:
        v = row[field]
        if field == "at":
            v = _at_text(v)
        elif field in ("id", "session_id", "ip") and v is not None:
            v = str(v)
        out[field] = v
    return out


def compute_row_hash(key: bytes, prev_hash: bytes, row: Mapping[str, Any]) -> bytes:
    return hmac.new(
        key, prev_hash + canonical_json(_payload(row)), hashlib.sha256
    ).digest()


# -- writing ---------------------------------------------------------------------
@dataclass(frozen=True)
class AuditEntry:
    seq: int
    id: uuid.UUID
    row_hash: bytes


def _clip(value: Optional[str], limit: int) -> Optional[str]:
    return None if value is None else clean_text(str(value))[:limit]


def _uuid_or_none(value: Any) -> Optional[uuid.UUID]:
    """Hostile or malformed input must not suppress the audit row: ``None``."""
    if value is None or isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _ip_or_none(value: Optional[str]) -> Optional[str]:
    """A canonical address, without an IPv6 scope id (``%eth0``); ``None`` for
    anything that is not an address, so attacker input cannot fail the insert."""
    if not value:
        return None
    try:
        return str(
            ipaddress.ip_address(clean_text(str(value)).split("%", 1)[0].strip())
        )
    except ValueError:
        return None


_PENDING = "admin_audit_checkpoints"


def _emit_checkpoints(sync_conn) -> None:
    pending = sync_conn.info.get(_PENDING, [])
    lines = list(pending)
    pending.clear()
    for seq, row_hash in lines:
        print(f"audit.checkpoint seq={seq} row_hash={row_hash.hex()}", flush=True)


def _drop_checkpoints(sync_conn) -> None:
    sync_conn.info.get(_PENDING, []).clear()


def _queue_checkpoint(conn: AsyncConnection, seq: int, row_hash: bytes) -> None:
    """Print the checkpoint when (and only if) the caller's transaction commits.

    ``info`` belongs to the pooled DBAPI connection and outlives checkouts, while
    listeners attach to the per-checkout ``Connection``: check each separately.
    """
    sync_conn = conn.sync_connection
    sync_conn.info.setdefault(_PENDING, [])
    if not event.contains(sync_conn, "commit", _emit_checkpoints):
        event.listen(sync_conn, "commit", _emit_checkpoints)
    if not event.contains(sync_conn, "rollback", _drop_checkpoints):
        event.listen(sync_conn, "rollback", _drop_checkpoints)
    sync_conn.info[_PENDING].append((seq, row_hash))


async def _build(
    conn: AsyncConnection,
    action: str,
    target_type: Optional[str],
    target_id: Optional[str],
    before: Any,
    after: Any,
    outcome: str,
    *,
    actor_kind: str,
    actor_email: Optional[str],
    session_id: Any,
    ip: Optional[str],
    ua: Optional[str],
    request_id: Optional[str],
    detail: Any,
    key: Optional[bytes],
    runner: bool,
    settings_lock: bool,
) -> tuple[dict, Optional[int]]:
    """The row with its chain link and hash, chain lock taken; ``(values, head_seq)``.

    ``runner`` is the task runner's path: it has no access to the log itself, so
    the lock, the chain head and the clock come from ``tasks.begin_audit`` (a
    definer function; ``settings_lock`` also takes the settings writer's lock
    first, the order the portal uses) and the row is appended by
    ``tasks.audit_append`` or ``settings.task_write_keyset``."""
    if actor_kind not in ACTOR_KINDS:
        raise AuditError("unknown actor_kind")
    if outcome not in OUTCOMES:
        raise AuditError("unknown outcome")
    if not action or len(action) > 128:
        raise AuditError("action must be 1-128 characters")
    if runner and (actor_kind != "system" or actor_email or session_id or ip or ua):
        raise AuditError("the task runner writes system rows with no admin identity")
    ip_text = _ip_or_none(ip)
    session = _uuid_or_none(session_id)

    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "actor_kind": actor_kind,
        "actor_email": _clip(actor_email, 320),
        "session_id": session,
        "ip": ip_text,
        "ua": _clip(ua, 256),
        "action": action,
        "target_type": _clip(target_type, 64),
        "target_id": _clip(None if target_id is None else str(target_id), 128),
        "outcome": outcome,
        "before": _bounded("before", before),
        "after": _bounded("after", after),
        "detail": _bounded("detail", detail),
        "request_id": _clip(request_id, 64),
        "key_version": AUDIT_KEY_VERSION,
    }

    audit_key = key if key is not None else admin_key("audit", AUDIT_KEY_VERSION)
    if runner:
        head, head_seq, now = await repo.runner_begin(conn, settings_lock)
    else:
        await repo.lock_chain(conn)
        head, head_seq, now = await repo.head_and_now(conn)
    prev_hash = head if head is not None else GENESIS_HASH
    values["at"] = now
    values["prev_hash"] = prev_hash
    values["row_hash"] = compute_row_hash(audit_key, prev_hash, values)
    return values, head_seq


def _checkpoint(conn: AsyncConnection, seq: int, row_hash: bytes, head_seq: Optional[int]) -> None:
    # a multiple of 100 can be skipped by a rolled-back write: checkpoint on crossing
    if seq // CHECKPOINT_EVERY > (head_seq or 0) // CHECKPOINT_EVERY:
        _queue_checkpoint(conn, seq, row_hash)


async def write(
    conn: AsyncConnection,
    action: str,
    target_type: Optional[str],
    target_id: Optional[str],
    before: Any,
    after: Any,
    outcome: str,
    *,
    actor_kind: str,
    actor_email: Optional[str] = None,
    session_id: Any = None,
    ip: Optional[str] = None,
    ua: Optional[str] = None,
    request_id: Optional[str] = None,
    detail: Any = None,
    key: Optional[bytes] = None,
    runner: bool = False,
) -> AuditEntry:
    """Append one audit row inside the caller's transaction (fail closed).

    Raises :class:`AuditError` / :class:`AuditPayloadTooLarge` on bad input and
    lets any database error propagate; the caller's transaction then rolls back.
    ``before``/``after``/``detail`` are masked and bounded here, so callers pass
    plain dicts. ``key`` defaults to the ``admin/audit`` subkey at ``AUDIT_KEY_VERSION``.
    ``runner=True`` is the task runner's path (see :func:`_build`).
    """
    values, head_seq = await _build(
        conn, action, target_type, target_id, before, after, outcome,
        actor_kind=actor_kind, actor_email=actor_email, session_id=session_id,
        ip=ip, ua=ua, request_id=request_id, detail=detail, key=key,
        runner=runner, settings_lock=False,
    )
    if runner:
        seq = await repo.runner_append(conn, values)
    else:
        seq = await repo.insert(conn, values)
    _checkpoint(conn, seq, values["row_hash"], head_seq)
    return AuditEntry(seq=seq, id=values["id"], row_hash=values["row_hash"])


async def prepare_runner_row(
    conn: AsyncConnection,
    action: str,
    target_type: Optional[str],
    target_id: Optional[str],
    before: Any,
    after: Any,
    outcome: str,
    *,
    detail: Any = None,
    request_id: Optional[str] = None,
    key: Optional[bytes] = None,
) -> dict:
    """A runner audit row built and hashed, not inserted: for
    ``settings.task_write_keyset``, which writes the row itself. Takes the settings
    writer's lock and the chain's lock; the caller's transaction must call the
    function before it ends."""
    values, _ = await _build(
        conn, action, target_type, target_id, before, after, outcome,
        actor_kind="system", actor_email=None, session_id=None, ip=None, ua=None,
        request_id=request_id, detail=detail, key=key, runner=True, settings_lock=True,
    )
    return values


# -- verifying -------------------------------------------------------------------
MAX_REPORTED_BREAKS = 20


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    rows: int  # rows scanned
    head_seq: Optional[int]
    # (seq, reason) per break, first MAX_REPORTED_BREAKS only; reasons:
    # prev_hash_mismatch | row_hash_mismatch | checkpoint_mismatch | checkpoint_missing
    breaks: tuple = ()
    total_breaks: int = 0

    @property
    def break_seq(self) -> Optional[int]:
        return self.breaks[0][0] if self.breaks else None

    @property
    def reason(self) -> Optional[str]:
        return self.breaks[0][1] if self.breaks else None

    def summary(self) -> str:
        if self.ok:
            return f"audit chain OK: {self.rows} rows, head seq {self.head_seq}"
        listed = ", ".join(f"seq {seq} ({why})" for seq, why in self.breaks)
        more = self.total_breaks - len(self.breaks)
        tail = f", and {more} more" if more > 0 else ""
        return (
            f"audit chain BROKEN: {self.total_breaks} break(s) in {self.rows} rows: "
            f"{listed}{tail}"
        )


VERIFY_BATCH = 5000


@dataclass(frozen=True)
class ChainStep:
    """One bounded pass of the automatic verification (see :func:`verify_step`)."""

    ok: bool
    scanned: int
    verified_seq: int  # the checkpoint after this pass
    breaks: tuple = ()  # (seq, reason), at most MAX_REPORTED_BREAKS

    @property
    def reasons(self) -> frozenset:
        return frozenset(why for _, why in self.breaks)


async def verify_step(
    conn: AsyncConnection, key: Optional[bytes] = None, batch: int = VERIFY_BATCH
) -> ChainStep:
    """Verify the next ``batch`` rows of the chain from the stored checkpoint and
    move the checkpoint forward when they are clean.

    The checkpoint (``admin.audit_verify_state``: the last verified seq and that
    row's hash) is first compared with the log: a missing row or a different hash
    is reported (``checkpoint_missing`` / ``checkpoint_mismatch``) and the
    checkpoint stays, so the alarm repeats on every pass. Rows after it are judged
    on their link and their HMAC like :func:`verify_chain` does; a break is
    reported and the checkpoint stays in front of it. Runs in the caller's
    transaction (the integrity loop's)."""
    state = await repo.get_verify_state(conn)
    seq, expected_prev = (0, GENESIS_HASH) if state is None else (state[0], state[1])
    if state is not None:
        stored = await repo.row_hash_at(conn, seq)
        if stored is None:
            return ChainStep(False, 0, seq, ((seq, "checkpoint_missing"),))
        if not hmac.compare_digest(stored, expected_prev):
            return ChainStep(False, 0, seq, ((seq, "checkpoint_mismatch"),))
    derived: dict[int, Optional[bytes]] = {}

    def key_for(version: int) -> Optional[bytes]:
        if key is not None:
            return key
        if version not in derived:
            try:
                derived[version] = admin_key("audit", version)
            except ValueError:
                derived[version] = None  # a tampered version number
        return derived[version]

    breaks: list[tuple[int, str]] = []
    last_seq, last_hash, scanned = seq, expected_prev, 0
    for row in await repo.rows_after(conn, seq, batch):
        m = row._mapping
        stored_prev, stored_hash = bytes(m["prev_hash"]), bytes(m["row_hash"])
        row_key = key_for(m["key_version"])
        recomputed = compute_row_hash(row_key, stored_prev, m) if row_key is not None else b""
        if stored_prev != last_hash:
            breaks.append((m["seq"], "prev_hash_mismatch"))
        elif not hmac.compare_digest(recomputed, stored_hash):
            breaks.append((m["seq"], "row_hash_mismatch"))
        if breaks:
            break  # the checkpoint stays in front of the first break
        last_seq, last_hash, scanned = m["seq"], stored_hash, scanned + 1
    if breaks:
        return ChainStep(False, scanned, seq, tuple(breaks[:MAX_REPORTED_BREAKS]))
    if scanned:
        await repo.save_verify_state(conn, last_seq, last_hash, scanned)
    return ChainStep(True, scanned, last_seq)


async def verify_chain(
    conn: AsyncConnection,
    key: Optional[bytes] = None,
    checkpoint: Optional[tuple[int, bytes]] = None,
) -> VerifyResult:
    """Recompute the whole chain and report every break (seq and reason only; the
    list is capped, the count is not). Each row is judged on its own link and its
    own hash, and the scan continues from the row's stored hash, so one
    tampered row yields one break. ``checkpoint`` (seq, row_hash from an
    ``audit.checkpoint`` line) also proves that row is still there, which
    catches deleted tail rows."""
    derived: dict[int, bytes] = {}

    def key_for(version: int) -> Optional[bytes]:
        if key is not None:
            return key
        if version not in derived:
            try:
                derived[version] = admin_key("audit", version)
            except ValueError:
                return None  # a tampered version number
        return derived[version]

    breaks: list[tuple[int, str]] = []
    total = 0

    def note(seq: int, why: str) -> None:
        nonlocal total
        total += 1
        if len(breaks) < MAX_REPORTED_BREAKS:
            breaks.append((seq, why))

    expected_prev = GENESIS_HASH
    count = 0
    head_seq: Optional[int] = None
    seen_checkpoint = False
    async for row in repo.stream_rows(conn):
        m = row._mapping
        stored_prev, stored_hash = bytes(m["prev_hash"]), bytes(m["row_hash"])
        row_key = key_for(m["key_version"])
        recomputed = (
            compute_row_hash(row_key, stored_prev, m) if row_key is not None else b""
        )
        if stored_prev != expected_prev:
            note(m["seq"], "prev_hash_mismatch")
        elif not hmac.compare_digest(recomputed, stored_hash):
            note(m["seq"], "row_hash_mismatch")
        expected_prev = stored_hash
        head_seq = m["seq"]
        count += 1
        if checkpoint is not None and m["seq"] == checkpoint[0]:
            if not hmac.compare_digest(stored_hash, checkpoint[1]):
                note(m["seq"], "checkpoint_mismatch")
            seen_checkpoint = True
    if checkpoint is not None and not seen_checkpoint:
        note(checkpoint[0], "checkpoint_missing")
    return VerifyResult(not total, count, head_seq, tuple(breaks), total)
