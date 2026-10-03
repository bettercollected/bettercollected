"""Endpoints only this instance's backend may call carry the shared internal
key (``AUTH_INTERNAL_NOTIFY_KEY``) in the ``X-Internal-Key`` header."""

import hmac
from http import HTTPStatus
from typing import Optional

from fastapi import Header

from auth.app.exceptions import HTTPException
from auth.config import settings

INTERNAL_KEY_HEADER = "X-Internal-Key"


def require_internal_key(
    internal_key: Optional[str] = Header(None, alias=INTERNAL_KEY_HEADER),
) -> None:
    """The caller is this instance's backend: 503 while no key is configured
    (fail closed), 403 for a missing or wrong key."""
    expected = settings.AUTH_INTERNAL_NOTIFY_KEY or ""
    if not expected:
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE, "Notifications are not configured."
        )
    if not internal_key or not hmac.compare_digest(
        internal_key.encode(), expected.encode()
    ):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not allowed.")
