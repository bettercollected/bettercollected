"""Thin async wrapper around the Unsplash REST API."""

from typing import Optional

import httpx

from backend.config import settings


class UnsplashService:
    """Fetches images from Unsplash.

    Used both by API controllers (if exposed directly) and by AI tool
    callbacks so the generated form can include relevant imagery.
    """

    _BASE = "https://api.unsplash.com"

    def __init__(self) -> None:
        self._access_key = settings.unsplash.ACCESS_KEY

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def search_photos(
        self,
        query: str,
        per_page: int = 5,
        orientation: str = "landscape",
    ) -> list[dict]:
        """Return a list of photo dicts from Unsplash.

        Each item has ``id``, ``url`` (regular size), ``thumb``, ``alt``,
        ``photographer``, and ``download_location`` fields.

        Returns an empty list if the key is missing or the request fails.
        """
        if not self._access_key:
            return []

        params = {
            "query": query,
            "per_page": per_page,
            "orientation": orientation,
        }
        headers = {"Authorization": f"Client-ID {self._access_key}"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._BASE}/search/photos",
                    params=params,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return [
                    {
                        "id": p["id"],
                        "url": p["urls"]["regular"],
                        "thumb": p["urls"]["thumb"],
                        "alt": p.get("alt_description") or query,
                        "photographer": p["user"]["name"],
                        "download_location": p["links"]["download_location"],
                    }
                    for p in data.get("results", [])
                ]
        except Exception:  # noqa: BLE001
            return []

    async def get_first_photo_url(
        self,
        query: str,
        orientation: str = "landscape",
    ) -> Optional[str]:
        """Convenience method – return the URL of the best matching photo."""
        results = await self.search_photos(query, per_page=3, orientation=orientation)
        return results[0]["url"] if results else None
