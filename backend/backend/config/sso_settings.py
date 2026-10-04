"""Enterprise single sign-on through Ory Polis (docs/sso.md).

Off unless ``SSO_ENABLED=true``. The same ``SSO_*`` variables are read by the
auth service (which runs the OAuth code exchange with Polis); the backend
also needs the Polis admin API key, which only it holds.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class SSOSettings(BaseSettings):
    ENABLED: bool = False
    # Polis as the browser and the identity providers reach it: the service
    # provider values shown to admins (ACS URL, OIDC redirect URI) are on it.
    POLIS_URL: str = ""
    # Polis as this service reaches it (admin API); POLIS_URL when unset.
    POLIS_INTERNAL_URL: str = ""
    # One of Polis's JACKSON_API_KEYS. Server-side only: never sent to the
    # browser, never logged.
    POLIS_API_KEY: str = ""
    # Polis "product"; the "tenant" is the workspace id.
    POLIS_PRODUCT: str = "bettercollected"
    # Polis's SAML_AUDIENCE: the entity ID (audience) identity providers see.
    SAML_AUDIENCE: str = ""
    # The backend's /api/v1/auth/sso/callback, registered on every connection
    # as its only redirect URL (Polis matches it exactly).
    REDIRECT_URI: str = ""
    HTTP_TIMEOUT_SECONDS: float = 15.0
    # at most this many connections per workspace (only one is enabled)
    MAX_CONNECTIONS_PER_WORKSPACE: int = 5

    model_config = SettingsConfigDict(env_prefix="SSO_")

    @property
    def polis_url(self) -> str:
        return (self.POLIS_URL or "").rstrip("/")

    @property
    def polis_internal_url(self) -> str:
        return (self.POLIS_INTERNAL_URL or self.POLIS_URL or "").rstrip("/")

    @property
    def is_configured(self) -> bool:
        """Switched on with everything the backend needs to talk to Polis."""
        return bool(
            self.ENABLED
            and self.polis_url
            and self.polis_internal_url
            and self.POLIS_API_KEY
            and self.REDIRECT_URI
        )

    @property
    def acs_url(self) -> str:
        return f"{self.polis_url}/api/oauth/saml"

    @property
    def oidc_redirect_uri(self) -> str:
        return f"{self.polis_url}/api/oauth/oidc"

    @property
    def sp_metadata_url(self) -> str:
        return f"{self.polis_url}/.well-known/sp-metadata"
