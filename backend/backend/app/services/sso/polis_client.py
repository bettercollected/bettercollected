"""The Ory Polis admin API (``/api/v1/sso``), server-side only.

Authenticated with one of Polis's ``JACKSON_API_KEYS`` (``SSO_POLIS_API_KEY``),
which never leaves the backend: the browser talks to our API only. Request
bodies carry IdP metadata and OIDC client secrets, so nothing here logs a
body, a header or a Polis reply; only status codes and fixed messages.
"""

import json
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from backend.config.sso_settings import SSOSettings

# Polis answers these fixed strings (npm/src/controller/connection/*.ts); a
# short, known message is shown to the admin, anything else becomes generic.
_KNOWN_MESSAGES = (
    "Please provide a metadata with IDPSSODescriptor",
    "Couldn't parse EntityID from SAML metadata",
    "Couldn't find SAML bindings for POST/REDIRECT",
    "Couldn't fetch XML data",
    "EntityID already exists for different tenant",
    "Metadata URL not valid",
    "Description should not exceed 100 characters",
)


class PolisError(Exception):
    """Polis refused or failed a request. ``message`` is safe to show."""

    def __init__(self, status: int, message: str, code: str = "polis_error"):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code


class PolisUnavailable(PolisError):
    def __init__(self):
        super().__init__(503, "The single sign-on service is not reachable.")


def _safe_message(body: Any) -> str:
    text = ""
    if isinstance(body, dict):
        error = body.get("error")
        text = error.get("message", "") if isinstance(error, dict) else str(error or "")
        text = text or str(body.get("message") or "")
    for known in _KNOWN_MESSAGES:
        if known.lower() in text.lower():
            return known
    if "invalid" in text.lower() and "metadata" in text.lower():
        return "The identity provider's metadata could not be read."
    return "The single sign-on service refused the connection."


class PolisAdminClient:
    def __init__(
        self,
        settings: SSOSettings,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._settings = settings
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._settings.polis_internal_url,
            transport=self._transport,
            timeout=self._settings.HTTP_TIMEOUT_SECONDS,
            headers={"Authorization": f"Api-Key {self._settings.POLIS_API_KEY}"},
        )

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            async with self._client() as client:
                response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            logger.error("Polis admin API unreachable: {}", type(error).__name__)
            raise PolisUnavailable()
        if response.status_code in (401, 403):
            # a wrong SSO_POLIS_API_KEY: an operator problem, not the admin's
            logger.error(
                "Polis admin API refused the API key (HTTP {}): check "
                "SSO_POLIS_API_KEY against Polis's JACKSON_API_KEYS",
                response.status_code,
            )
            raise PolisUnavailable()
        if response.status_code >= 500:
            logger.error("Polis admin API failed: HTTP {}", response.status_code)
            raise PolisUnavailable()
        try:
            body = response.json() if response.content else None
        except ValueError:
            body = None
        if response.status_code >= 400:
            message = _safe_message(body)
            code = (
                "idp_already_connected"
                if message.startswith("EntityID already exists")
                else "invalid_connection"
            )
            raise PolisError(response.status_code, message, code)
        return body

    def _base(self, tenant: str, name: str) -> Dict[str, Any]:
        redirect = self._settings.REDIRECT_URI
        return {
            "tenant": tenant,
            "product": self._settings.POLIS_PRODUCT,
            "name": name[:100],
            "description": "BetterCollected workspace single sign-on",
            "defaultRedirectUrl": redirect,
            # the only redirect URL, matched exactly (OPENID_REDIRECT_EXACT_MATCH)
            "redirectUrl": json.dumps([redirect]),
        }

    async def create_saml(
        self,
        tenant: str,
        name: str,
        raw_metadata: Optional[str] = None,
        metadata_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = self._base(tenant, name)
        if metadata_url:
            body["metadataUrl"] = metadata_url
        else:
            body["rawMetadata"] = raw_metadata
        return await self._request("POST", "/api/v1/sso", json=body)

    async def create_oidc(
        self,
        tenant: str,
        name: str,
        metadata: Dict[str, str],
        client_id: str,
        client_secret: str,
    ) -> Dict[str, Any]:
        """``metadata``: the checked endpoints of the IdP's discovery
        document (issuer, authorization, token, userinfo, JWKS), so Polis
        never fetches the discovery URL itself."""
        body = self._base(tenant, name)
        body.update(
            {
                "oidcMetadata": metadata,
                "oidcClientId": client_id,
                "oidcClientSecret": client_secret,
            }
        )
        return await self._request("POST", "/api/v1/sso", json=body)

    async def list_connections(self, tenant: str) -> List[Dict[str, Any]]:
        body = await self._request(
            "GET",
            "/api/v1/sso",
            params={"tenant": tenant, "product": self._settings.POLIS_PRODUCT},
        )
        return body if isinstance(body, list) else []

    async def get_connection(self, client_id: str) -> Optional[Dict[str, Any]]:
        body = await self._request("GET", "/api/v1/sso", params={"clientID": client_id})
        if isinstance(body, list):
            return body[0] if body else None
        return body or None

    async def delete_connection(self, client_id: str) -> None:
        """Delete one connection. Polis wants the connection's own client
        secret for that, and its DELETE only takes it as a query parameter,
        so it is read from Polis and sent back at once over the internal
        network (SSO_POLIS_INTERNAL_URL), never kept or logged. We never use
        that secret otherwise (sign-ins use PKCE)."""
        connection = await self.get_connection(client_id)
        if not connection:
            return
        await self._request(
            "DELETE",
            "/api/v1/sso",
            params={
                "clientID": client_id,
                "clientSecret": connection.get("clientSecret", ""),
            },
        )

    async def delete_tenant(self, tenant: str) -> None:
        """Every connection of a tenant (a deleted workspace)."""
        await self._request(
            "DELETE",
            "/api/v1/sso",
            params={"tenant": tenant, "product": self._settings.POLIS_PRODUCT},
        )
