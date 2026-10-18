"""Signed run requests.

The admin service writes a row into ``tasks.runs``; the runner executes it only
if ``request_sig`` verifies. The signature is an HMAC-SHA256 under the
``tasks/request/v<n>`` subkey derived from ``SETTINGS_MASTER_KEY``. The admin
service's own database role can insert rows but a compromised backend (which
shares the database server, not that key) cannot produce a row the runner will
accept.

Canonical encoding: a domain tag, then every field as ``len(4, big endian) ||
bytes``, in the fixed order of :data:`FIELDS`. Length prefixes make the
encoding injective (``"a|b", "c"`` and ``"a", "b|c"`` cannot collide).

``resumes_run_id`` is signed as well (it is not in the minimal field list the
design names): otherwise whoever can insert a row could graft a resume onto an
unrelated, already-finished run.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.admin.security.keys import derive_key

DOMAIN_TAG = b"bettercollected/tasks/request/v1"
SIG_VERSION = 1
FIELDS = (
    "id",
    "task",
    "version",
    "params_hash",
    "dry_run",
    "requested_by",
    "requested_at",
    "nonce",
    "resumes_run_id",
)


def canonical_params(params: Mapping[str, Any]) -> bytes:
    return json.dumps(
        params, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def params_hash(params: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_params(params)).hexdigest()


def _at_text(at: datetime) -> str:
    if at.tzinfo is None:
        raise ValueError("requested_at must be timezone-aware")
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def encode(
    *,
    id: Any,
    task: str,
    version: int,
    params_hash: str,
    dry_run: bool,
    requested_by: str,
    requested_at: datetime,
    nonce: str,
    resumes_run_id: Any = None,
) -> bytes:
    values = {
        "id": str(id),
        "task": task,
        "version": str(int(version)),
        "params_hash": params_hash,
        "dry_run": "1" if dry_run else "0",
        "requested_by": requested_by,
        "requested_at": _at_text(requested_at),
        "nonce": nonce,
        "resumes_run_id": "" if resumes_run_id is None else str(resumes_run_id),
    }
    out = [DOMAIN_TAG]
    for name in FIELDS:
        raw = values[name].encode("utf-8")
        out.append(len(raw).to_bytes(4, "big"))
        out.append(raw)
    return b"".join(out)


def sign(key: bytes, **fields: Any) -> bytes:
    return hmac.new(key, encode(**fields), hashlib.sha256).digest()


def request_key(version: int = SIG_VERSION) -> bytes:
    return derive_key("tasks", "request", version)


@dataclass(frozen=True)
class RunRequest:
    """A request as the admin side creates it (and the row the runner reads)."""

    id: uuid.UUID
    task: str
    version: int
    params: dict
    params_hash: str
    dry_run: bool
    requested_by: str
    requested_at: datetime
    nonce: str
    request_sig: bytes
    sig_version: int = SIG_VERSION
    resumes_run_id: Optional[uuid.UUID] = None

    @classmethod
    def create(
        cls,
        *,
        task: str,
        version: int,
        params: Mapping[str, Any],
        dry_run: bool,
        requested_by: str,
        requested_at: datetime,
        resumes_run_id: Optional[uuid.UUID] = None,
        key: Optional[bytes] = None,
        run_id: Optional[uuid.UUID] = None,
    ) -> "RunRequest":
        """Build and sign a request. ``params`` must already be validated against
        the task's ``Params`` (``model_dump(mode="json")``)."""
        rid = run_id or uuid.uuid4()
        nonce = secrets.token_hex(16)
        p = dict(params)
        ph = params_hash(p)
        sig = sign(
            key if key is not None else request_key(),
            id=rid,
            task=task,
            version=version,
            params_hash=ph,
            dry_run=dry_run,
            requested_by=requested_by,
            requested_at=requested_at,
            nonce=nonce,
            resumes_run_id=resumes_run_id,
        )
        return cls(
            id=rid,
            task=task,
            version=version,
            params=p,
            params_hash=ph,
            dry_run=dry_run,
            requested_by=requested_by,
            requested_at=requested_at,
            nonce=nonce,
            request_sig=sig,
            resumes_run_id=resumes_run_id,
        )


def verify_request(row: Mapping[str, Any], key: Optional[bytes] = None) -> bool:
    """Constant-time check of a ``tasks.runs`` row (mapping with the signed
    columns plus ``params``). Also recomputes ``params_hash`` from the stored
    ``params``, so params edited after signing fail too. Never raises on a
    malformed row: it is simply not verified."""
    try:
        if params_hash(row["params"]) != row["params_hash"]:
            return False
        expected = sign(
            key if key is not None else request_key(int(row["sig_version"])),
            id=row["id"],
            task=row["task"],
            version=row["version"],
            params_hash=row["params_hash"],
            dry_run=bool(row["dry_run"]),
            requested_by=row["requested_by"],
            requested_at=row["requested_at"],
            nonce=row["nonce"],
            resumes_run_id=row.get("resumes_run_id"),
        )
        return hmac.compare_digest(expected, bytes(row["request_sig"]))
    except Exception:  # noqa: BLE001 - any malformed field means "not verified"
        return False
