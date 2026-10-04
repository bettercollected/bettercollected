"""The key the background workers send to this backend's internal job routes.

The Temporal worker and the actions-executor call a few routes (imports,
expired-response deletion, account deletion, action secrets, template
previews) with a shared key in the ``api-key`` header: ``TEMPORAL_API_KEY``
here, ``API_KEY`` on the workers, the same value on all of them.
``get_api_key`` in ``user_service`` checks it.

An unset or empty key, or the placeholder that older versions shipped as the
default, counts as not configured: those routes then answer 503 (fail closed)
and the backend logs an error at startup.
"""

from http import HTTPStatus

from loguru import logger

from backend.app.exceptions import HTTPException
from backend.config import settings

# Published defaults of earlier versions: never accepted as a key.
PLACEHOLDER_KEYS = frozenset({"random_api_key"})


def configured_job_api_key() -> str:
    """The configured key, or "" when it is unset or a published placeholder."""
    key = (settings.temporal_settings.api_key or "").strip()
    return "" if key in PLACEHOLDER_KEYS else key


def require_job_api_key() -> str:
    """The configured key; 503 while there is none."""
    key = configured_job_api_key()
    if not key:
        logger.error("Refused an internal job request: TEMPORAL_API_KEY is not set.")
        raise HTTPException(
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            content="The internal job key (TEMPORAL_API_KEY) is not configured.",
        )
    return key


def log_if_job_api_key_missing() -> bool:
    """Log an error at startup when the key is not configured (True when it
    is). The service still starts; the internal job routes answer 503."""
    if configured_job_api_key():
        return True
    logger.error(
        "TEMPORAL_API_KEY is not set (or is the old public default): the "
        "internal job routes answer 503, so imports, scheduled response "
        "deletion, account deletion and form actions fail. Set the same value "
        "as TEMPORAL_API_KEY on the backend and API_KEY on the Temporal worker "
        "and the actions-executor."
    )
    return False
