"""Enterprise single sign-on through Ory Polis (formerly BoxyHQ SAML Jackson).

See docs/sso.md. Off unless ``SSO_ENABLED=true``. The backend decides which
workspace (Polis tenant) and connection a sign-in may use; this service runs
the OAuth code flow with Polis and owns the accounts. The same ``SSO_*``
variables configure the backend.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class SSOSettings(BaseSettings):
    ENABLED: bool = False
    # Polis as the browser reaches it (the authorize redirect).
    POLIS_URL: Optional[str] = ""
    # Polis as this service reaches it (token + userinfo); POLIS_URL when unset.
    POLIS_INTERNAL_URL: Optional[str] = ""
    # Polis "product"; the "tenant" is the BetterCollected workspace id.
    POLIS_PRODUCT: Optional[str] = "bettercollected"
    # Polis's CLIENT_SECRET_VERIFIER. Optional: every sign-in uses PKCE, and
    # with PKCE Polis checks the code_verifier instead (docs/sso.md). Sent on
    # the token call when set.
    POLIS_CLIENT_SECRET: Optional[str] = ""
    # The backend's /api/v1/auth/sso/callback, registered on every connection.
    REDIRECT_URI: Optional[str] = ""
    # How long a started sign-in may take before its state is refused.
    STATE_MAX_AGE_SECONDS: int = 600
    # How long the backend has to turn a checked sign-in into an account.
    ASSERTION_MAX_AGE_SECONDS: int = 120
    HTTP_TIMEOUT_SECONDS: float = 15.0

    model_config = SettingsConfigDict(env_prefix="SSO_")

    @property
    def polis_internal_url(self) -> str:
        return (self.POLIS_INTERNAL_URL or self.POLIS_URL or "").rstrip("/")

    @property
    def polis_url(self) -> str:
        return (self.POLIS_URL or "").rstrip("/")
