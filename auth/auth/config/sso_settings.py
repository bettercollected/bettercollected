"""Enterprise SSO through Ory Polis (formerly BoxyHQ SAML Jackson).

Spike configuration, see docs/sso-spike.md. Off unless ``SSO_ENABLED=true``.
"""

from typing import Dict, FrozenSet, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class SSOSettings(BaseSettings):
    ENABLED: bool = False
    # Polis as the browser reaches it (the authorize redirect).
    POLIS_URL: Optional[str] = ""
    # Polis as this service reaches it (token + userinfo); POLIS_URL when unset.
    POLIS_INTERNAL_URL: Optional[str] = ""
    # Polis "product"; the "tenant" is the BetterCollected workspace id.
    POLIS_PRODUCT: Optional[str] = "bettercollected"
    # Polis's CLIENT_SECRET_VERIFIER. Sent on the token call; with PKCE (always
    # used here) Polis checks the code_verifier instead, see docs/sso-spike.md.
    POLIS_CLIENT_SECRET: Optional[str] = ""
    # The backend's /api/v1/auth/sso/callback, registered on the Polis connection.
    REDIRECT_URI: Optional[str] = ""
    # Spike tenant resolution: "example.com:<workspace_id>,acme.io:<workspace_id>".
    # The real design resolves verified domains owned by a workspace.
    DOMAIN_TENANTS: Optional[str] = ""
    # How long a started sign-in may take before its state is refused.
    STATE_MAX_AGE_SECONDS: int = 600
    HTTP_TIMEOUT_SECONDS: float = 15.0

    model_config = SettingsConfigDict(env_prefix="SSO_")

    @property
    def polis_internal_url(self) -> str:
        return (self.POLIS_INTERNAL_URL or self.POLIS_URL or "").rstrip("/")

    @property
    def polis_url(self) -> str:
        return (self.POLIS_URL or "").rstrip("/")

    def domain_tenants(self) -> Dict[str, str]:
        """Email domain (lower case) -> tenant (workspace id)."""
        mapping = {}
        for entry in (self.DOMAIN_TENANTS or "").split(","):
            domain, _, tenant = entry.strip().partition(":")
            domain, tenant = domain.strip().lower(), tenant.strip()
            if domain and tenant:
                mapping[domain] = tenant
        return mapping

    def tenant_for_domain(self, domain: str) -> Optional[str]:
        return self.domain_tenants().get((domain or "").strip().lower())

    def domains_for_tenant(self, tenant: str) -> FrozenSet[str]:
        return frozenset(d for d, t in self.domain_tenants().items() if t == tenant)
