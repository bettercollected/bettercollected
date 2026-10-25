"""The startup check for single sign-on: SSO_ENABLED=true with a required
setting missing is logged by name (never a value), so an operator sees why the
workspace page says SSO is not fully set up."""

from loguru import logger

from backend.config import settings
from common.settings import sso_requirements


def log_if_sso_incomplete() -> bool:
    """Log a warning when SSO is switched on but incomplete; True otherwise."""
    sso = settings.sso
    if not sso.ENABLED:
        return True
    missing = sso.missing_settings
    if not missing:
        return True
    logger.warning(sso_requirements.startup_message("backend", missing))
    return False
