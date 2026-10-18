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
    r"secret|token|password|passwd|key|code|otp|hash|authorization|cookie|seed|private",
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


class AuditPayloadTooLarge(AuditError):
    """before/after/detail is 8 KB or more after masking."""


# -- masking and canonical form -------------------------------------------------
def mask(value: Any, _depth: int = 0) -> Any:
    """A JSON-safe, size-bounded copy of ``value`` with every value under a
    deny-listed key name replaced. Floats and unknown types become strings so
    the stored JSON round-trips byte for byte."""
    if _depth > MAX_DEPTH:
        return "[max-depth]"
    if value is None or isinstance(value, bool) or isinstance(value, int):
        return value
    if isinstance(value, str):
        value = value.replace("\x00", "")
        if len(value) > MAX_STRING:
            return f"{value[:MAX_STRING]}...[truncated {len(value) - MAX_STRING}]"
        return value
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= MAX_ITEMS:
                out["[truncated]"] = len(value) - MAX_ITEMS
                break
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
    return mask(str(value), _depth)


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
    return None if value is None else str(value).replace("\x00", "")[:limit]


def _uuid_or_none(value: Any) -> Optional[uuid.UUID]:
    if value is None or isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _emit_checkpoints(sync_conn) -> None:
    pending = sync_conn.info.get("admin_audit_checkpoints", [])
    lines = list(pending)
    pending.clear()
    for seq, row_hash in lines:
        print(f"audit.checkpoint seq={seq} row_hash={row_hash.hex()}", flush=True)


def _drop_checkpoints(sync_conn) -> None:
    sync_conn.info.get("admin_audit_checkpoints", []).clear()


def _queue_checkpoint(conn: AsyncConnection, seq: int, row_hash: bytes) -> None:
    """Print the checkpoint when (and only if) the caller's transaction commits."""
    sync_conn = conn.sync_connection
    if "admin_audit_checkpoints" not in sync_conn.info:
        sync_conn.info["admin_audit_checkpoints"] = []
        event.listen(sync_conn, "commit", _emit_checkpoints)
        event.listen(sync_conn, "rollback", _drop_checkpoints)
    sync_conn.info["admin_audit_checkpoints"].append((seq, row_hash))


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
) -> AuditEntry:
    """Append one audit row inside the caller's transaction (fail closed).

    Raises :class:`AuditError` / :class:`AuditPayloadTooLarge` on bad input and
    lets any database error propagate; the caller's transaction then rolls back.
    ``before``/``after``/``detail`` are masked and bounded here, so callers pass
    plain dicts. ``key`` defaults to the ``admin/audit`` subkey at ``AUDIT_KEY_VERSION``.
    """
    if actor_kind not in ACTOR_KINDS:
        raise AuditError("unknown actor_kind")
    if outcome not in OUTCOMES:
        raise AuditError("unknown outcome")
    if not action or len(action) > 128:
        raise AuditError("action must be 1-128 characters")
    try:
        ip_text = str(ipaddress.ip_address(ip)) if ip else None
        session = _uuid_or_none(session_id)
    except ValueError:
        raise AuditError("ip or session_id is not valid") from None

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
    await repo.lock_chain(conn)
    head, now = await repo.head_and_now(conn)
    prev_hash = head if head is not None else GENESIS_HASH
    values["at"] = now
    values["prev_hash"] = prev_hash
    values["row_hash"] = compute_row_hash(audit_key, prev_hash, values)
    seq = await repo.insert(conn, values)
    if seq % CHECKPOINT_EVERY == 0:
        _queue_checkpoint(conn, seq, values["row_hash"])
    return AuditEntry(seq=seq, id=values["id"], row_hash=values["row_hash"])


# -- verifying -------------------------------------------------------------------
@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    rows: int
    head_seq: Optional[int]
    break_seq: Optional[int] = None
    reason: Optional[str] = (
        None  # prev_hash_mismatch | row_hash_mismatch | checkpoint_*
    )

    def summary(self) -> str:
        if self.ok:
            return f"audit chain OK: {self.rows} rows, head seq {self.head_seq}"
        return (
            f"audit chain BROKEN at seq {self.break_seq} ({self.reason}); "
            f"{self.rows} rows checked before the break"
        )


async def verify_chain(
    conn: AsyncConnection,
    key: Optional[bytes] = None,
    checkpoint: Optional[tuple[int, bytes]] = None,
) -> VerifyResult:
    """Recompute the whole chain; report the first break by seq and reason only.
    ``checkpoint`` (seq, row_hash from an ``audit.checkpoint`` line) also proves
    that row is still there, which catches deleted tail rows."""
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

    expected_prev = GENESIS_HASH
    count = 0
    head_seq: Optional[int] = None
    seen_checkpoint = False
    async for row in repo.stream_rows(conn):
        m = row._mapping
        if bytes(m["prev_hash"]) != expected_prev:
            return VerifyResult(False, count, head_seq, m["seq"], "prev_hash_mismatch")
        row_key = key_for(m["key_version"])
        recomputed = (
            compute_row_hash(row_key, expected_prev, m) if row_key is not None else b""
        )
        if not hmac.compare_digest(recomputed, bytes(m["row_hash"])):
            return VerifyResult(False, count, head_seq, m["seq"], "row_hash_mismatch")
        expected_prev = recomputed
        head_seq = m["seq"]
        count += 1
        if checkpoint is not None and m["seq"] == checkpoint[0]:
            if not hmac.compare_digest(recomputed, checkpoint[1]):
                return VerifyResult(
                    False, count, head_seq, m["seq"], "checkpoint_mismatch"
                )
            seen_checkpoint = True
    if checkpoint is not None and not seen_checkpoint:
        return VerifyResult(False, count, head_seq, checkpoint[0], "checkpoint_missing")
    return VerifyResult(True, count, head_seq)
