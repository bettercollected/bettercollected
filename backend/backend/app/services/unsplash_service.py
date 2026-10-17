"""Thin async wrapper around the Unsplash REST API."""

from typing import Optional

import httpx
from loguru import logger

from backend.config import settings


class UnsplashService:
    """Fetches images from Unsplash.

    Used both by API controllers (if exposed directly) and by AI tool
    callbacks so the generated form can include relevant imagery.
    """

    _BASE = "https://api.unsplash.com"

    def __init__(self) -> None:
        raw_key = settings.unsplash.ACCESS_KEY or ""
        self._access_key = raw_key.strip()

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
                results = data.get("results", [])

                return [
                    {
                        "id": p["id"],
                        "url": p["urls"]["regular"],
                        "thumb": p["urls"]["thumb"],
                        "alt": p.get("alt_description") or query,
                        "photographer": p["user"]["name"],
                        "download_location": p["links"]["download_location"],
                    }
                    for p in results
                ]
        except httpx.HTTPStatusError as exc:
            # status only: the query comes from an AI prompt
            logger.warning(
                "Unsplash search failed (HTTP {})", exc.response.status_code
            )
            return []
        except Exception as exc:  # noqa: BLE001
            # the error's type only: its message can carry the request URL
            logger.warning("Unsplash search failed ({})", type(exc).__name__)
            return []

    async def get_first_photo_url(
        self,
        query: str,
        orientation: str = "landscape",
    ) -> Optional[str]:
        """Convenience method – return the URL of the best matching photo."""
        results = await self.search_photos(query, per_page=3, orientation=orientation)
        url = results[0]["url"] if results else None
        return url
