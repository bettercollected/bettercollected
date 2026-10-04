"""Polis's webhook signature (npm/src/event/webhook.ts, 26.2.0):

    BoxyHQ-Signature: t=<unix ms>,s=<hex HMAC-SHA256(secret, f"{t}.{body}")>

where ``body`` is the JSON Polis posts, exactly as sent (it signs
``JSON.stringify(payload)`` and axios posts the same string), so the check
runs on the raw request bytes, never on re-serialised JSON. Polis sends the
same value as ``Ory-Polis-Signature`` too; only ``BoxyHQ-Signature`` is read.
"""

import hashlib
import hmac
import time
from typing import Optional

# The only header read: Polis 26.2.0 always sends it (and the same value as
# Ory-Polis-Signature, which is ignored, so one request has one signature).
SIGNATURE_HEADER = "BoxyHQ-Signature"


class BadSignature(Exception):
    """Missing, malformed, wrong or outside the time window. ``code`` says
    which (for logs and metrics only; the caller answers the same 401)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def parse_signature(header: Optional[str]):
    """(timestamp in ms, hex signature) from ``t=<ms>,s=<hex>``."""
    if not header or len(header) > 512:
        raise BadSignature("missing")
    parts = {}
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        if key in ("t", "s") and value and key not in parts:
            parts[key] = value
    try:
        timestamp = int(parts["t"])
        signature = parts["s"]
    except (KeyError, ValueError):
        raise BadSignature("malformed")
    if len(signature) != 64:
        raise BadSignature("malformed")
    return timestamp, signature


def sign(secret: str, body: bytes, timestamp_ms: int) -> str:
    """The header Polis would send (tests and local tools)."""
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp_ms}.".encode("ascii") + body,
        hashlib.sha256,
    ).hexdigest()
    return f"t={timestamp_ms},s={digest}"


def verify(
    header: Optional[str],
    body: bytes,
    secret: str,
    tolerance_seconds: int,
    now: Optional[float] = None,
) -> int:
    """The signed timestamp (ms) when ``header`` signs ``body`` with
    ``secret`` within ``tolerance_seconds`` of now; else BadSignature.
    Constant-time comparison."""
    timestamp, signature = parse_signature(header)
    now_ms = (time.time() if now is None else now) * 1000
    if abs(now_ms - timestamp) > tolerance_seconds * 1000:
        raise BadSignature("expired")
    if not secret:
        raise BadSignature("no_secret")
    expected = hmac.new(
        secret.encode("utf-8"), f"{timestamp}.".encode("ascii") + body, hashlib.sha256
    ).hexdigest()
    try:
        matches = hmac.compare_digest(expected, signature.lower())
    except TypeError:  # not ASCII
        raise BadSignature("malformed")
    if not matches:
        raise BadSignature("mismatch")
    return timestamp
