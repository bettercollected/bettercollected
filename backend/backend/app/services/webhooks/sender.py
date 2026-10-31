"""One signed POST to a webhook's address.

Goes through ``registration.client.request``, which applies the destination
rules at *this* connection: the host is resolved now and every answer must be
public (so a name that turned private since the webhook was saved, or rebinds
between lookups, is refused), the connection goes to the address checked (TLS
still uses the host name for SNI and the certificate), a redirect is a
permanent failure, no cookies or proxies, no compression, a fixed User-Agent,
and the reply is read up to a few KB and dropped: only the status code and our
timing leave this function.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl, urlsplit

from backend.app.services.registration import client
from backend.app.services.webhooks import payload

MAX_REPLY_BYTES = 4096
TIMEOUTS = {"connect": 5.0, "read": 10.0, "write": 10.0, "pool": 5.0}
TOTAL_TIMEOUT_S = 20.0


@dataclass(frozen=True)
class Sent:
    http_status: int
    duration_ms: int


async def post(
    url: str,
    secret: str,
    body: bytes,
    *,
    delivery_id: str,
    event: str,
    timestamp: int,
) -> Sent:
    """Returns the 2xx status and the time taken, or raises
    :class:`client.SendFailed` (with ``duration_ms`` set on it)."""
    if len(body) > payload.MAX_BODY_BYTES:
        raise client.SendFailed("too_large", permanent=True)
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}{parts.path}"
    query = parse_qsl(parts.query, keep_blank_values=True) if parts.query else None
    headers = [
        (payload.SIGNATURE_HEADER, payload.sign(secret, timestamp, body).encode()),
        (payload.TIMESTAMP_HEADER, str(timestamp).encode()),
        (payload.DELIVERY_HEADER, delivery_id.encode("ascii")),
        (payload.EVENT_HEADER, event.encode("ascii")),
    ]
    started = time.monotonic()
    try:
        reply = await client.request(
            client.Target(base_url=base),
            "POST",
            body=body,
            query=query,
            extra_headers=headers,
            max_reply=MAX_REPLY_BYTES,
            user_agent=payload.USER_AGENT,
            timeouts=TIMEOUTS,
            total_timeout=TOTAL_TIMEOUT_S,
        )
    except client.SendFailed as failed:
        failed.duration_ms = _ms(started)  # type: ignore[attr-defined]
        raise
    return Sent(reply.status, _ms(started))


def _ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))


def duration_of(failed: client.SendFailed) -> Optional[int]:
    return getattr(failed, "duration_ms", None)
