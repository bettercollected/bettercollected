"""Requests from this backend to the auth service.

The auth service's API is internal: every route except its health check and
the Stripe webhook refuses requests without the shared key
(``AUTH_INTERNAL_NOTIFY_KEY``, the same value on both services) in the
``X-Internal-Key`` header. Every call to ``settings.auth_settings.BASE_URL`` or
``CALLBACK_URI`` passes ``headers=auth_service_headers(...)``;
``tests/app/services/test_auth_call_sites.py`` fails the build otherwise.

The key goes on each auth call, never on a shared client: those also call
third parties.
"""

from typing import Dict

from loguru import logger

from backend.config import settings

INTERNAL_KEY_HEADER = "X-Internal-Key"


def auth_service_headers(**extra: str) -> Dict[str, str]:
    """Headers for a request to the auth service: ``extra`` (e.g.
    ``Authorization``) plus the internal key when one is configured."""
    headers = dict(extra)
    key = settings.auth_settings.INTERNAL_NOTIFY_KEY
    if key:
        headers[INTERNAL_KEY_HEADER] = key
    return headers


def log_if_internal_key_missing() -> bool:
    """Log an error at startup when the key is unset; True when it is set.

    The service still starts: the auth service answers 503/403 to every call
    without the key, so sign-in, sessions, invitations and member lists fail
    until it is configured."""
    if settings.auth_settings.INTERNAL_NOTIFY_KEY:
        return True
    logger.error(
        "AUTH_INTERNAL_NOTIFY_KEY is not set: the auth service refuses requests "
        "without it, so sign-in, session refresh, invitations and member lists "
        "will fail. Set the same value on the backend, auth and google services."
    )
    return False
