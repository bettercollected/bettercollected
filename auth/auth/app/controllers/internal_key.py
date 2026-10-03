"""The auth service's API is internal: only this instance's backend (and the
google integration) may call it, with the shared key
(``AUTH_INTERNAL_NOTIFY_KEY``) in the ``X-Internal-Key`` header.

Every route requires it except ``/ready`` (health checks) and
``POST /stripe/webhooks`` (verified by its Stripe signature). The setting is
named after the first route it guarded (notification mails) and kept for
compatibility. Routers take it as a router-level dependency
(``INTERNAL_ONLY``)."""

import hmac
from http import HTTPStatus
from typing import Optional

from fastapi import Depends, Header
from loguru import logger

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
        logger.error("Refused a request: AUTH_INTERNAL_NOTIFY_KEY is not set.")
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "The internal service key (AUTH_INTERNAL_NOTIFY_KEY) is not configured.",
        )
    if not internal_key or not hmac.compare_digest(
        internal_key.encode(), expected.encode()
    ):
        raise HTTPException(HTTPStatus.FORBIDDEN, "Not allowed.")


# For ``@router(..., dependencies=INTERNAL_ONLY)``: every route of the router.
INTERNAL_ONLY = [Depends(require_internal_key)]


def log_if_internal_key_missing() -> bool:
    """Log an error at startup when the key is unset (True when set). The
    service still starts; its guarded routes answer 503 until it is set."""
    if settings.AUTH_INTERNAL_NOTIFY_KEY:
        return True
    logger.error(
        "AUTH_INTERNAL_NOTIFY_KEY is not set: every route except /ready and "
        "POST /stripe/webhooks answers 503, so sign-in, session refresh, "
        "invitations and member lists fail. Set the same value on the backend, "
        "auth and google services."
    )
    return False
