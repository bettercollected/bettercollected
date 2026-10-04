"""Polis's directory sync admin API (``/api/v1/dsync``), server-side only.

Same API key and the same rules as the SSO admin client: nothing here logs a
body or a header (a created directory's reply carries the SCIM bearer token
and the webhook secret), only status codes. The webhook URL handed to Polis
is built from ``SCIM_WEBHOOK_URL`` and our own directory id, never from a
request.
"""

from typing import Any, Dict, List, Optional
from urllib.parse import quote

from backend.app.services.sso.polis_client import PolisAdminClient, PolisError


def _data(body: Any) -> Any:
    """Polis answers ``{"data": ..., "error": ...}``."""
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


class PolisDirectoryClient(PolisAdminClient):
    async def create_directory(
        self,
        tenant: str,
        name: str,
        directory_type: str,
        webhook_url: str,
        webhook_secret: str,
    ) -> Dict[str, Any]:
        """The new directory: ``id``, ``scim.endpoint`` (the SCIM base URL)
        and ``scim.secret`` (the bearer token the IdP uses; shown once)."""
        body = await self._request(
            "POST",
            "/api/v1/dsync",
            json={
                "tenant": tenant,
                "product": self._settings.POLIS_PRODUCT,
                "name": name[:100],
                "type": directory_type,
                "webhook_url": webhook_url,
                "webhook_secret": webhook_secret,
            },
        )
        directory = _data(body)
        if not isinstance(directory, dict) or not directory.get("id"):
            raise PolisError(503, "The directory sync service did not answer.")
        return directory

    async def delete_directory(self, directory_id: str) -> None:
        try:
            await self._request(
                "DELETE", f"/api/v1/dsync/{quote(directory_id, safe='')}"
            )
        except PolisError as error:
            if error.status != 404:  # already gone
                raise

    async def _pages(
        self, path: str, params: Dict[str, str], page_size: int
    ) -> List[Dict[str, Any]]:
        found: List[Dict[str, Any]] = []
        offset = 0
        while True:
            body = await self._request(
                "GET",
                path,
                params={**params, "pageOffset": offset, "pageLimit": page_size},
            )
            page = _data(body)
            page = page if isinstance(page, list) else []
            found.extend(item for item in page if isinstance(item, dict))
            if len(page) < page_size or offset > 1_000_000:
                return found
            offset += page_size

    def _scope(self, tenant: str, directory_id: str) -> Dict[str, str]:
        return {
            "tenant": tenant,
            "product": self._settings.POLIS_PRODUCT,
            "directoryId": directory_id,
        }

    async def list_users(
        self, tenant: str, directory_id: str, page_size: int = 100
    ) -> List[Dict[str, Any]]:
        return await self._pages(
            "/api/v1/dsync/users", self._scope(tenant, directory_id), page_size
        )

    async def list_groups(
        self, tenant: str, directory_id: str, page_size: int = 100
    ) -> List[Dict[str, Any]]:
        return await self._pages(
            "/api/v1/dsync/groups", self._scope(tenant, directory_id), page_size
        )

    async def list_group_members(
        self,
        tenant: str,
        directory_id: str,
        group_id: str,
        page_size: int = 100,
    ) -> List[str]:
        members = await self._pages(
            f"/api/v1/dsync/groups/{quote(group_id, safe='')}/members",
            self._scope(tenant, directory_id),
            page_size,
        )
        return [str(m["user_id"]) for m in members if m.get("user_id")]


def scim_endpoint(directory: Optional[Dict[str, Any]]) -> str:
    scim = (directory or {}).get("scim") or {}
    return str(scim.get("endpoint") or "")


def scim_secret(directory: Optional[Dict[str, Any]]) -> str:
    scim = (directory or {}).get("scim") or {}
    return str(scim.get("secret") or "")
