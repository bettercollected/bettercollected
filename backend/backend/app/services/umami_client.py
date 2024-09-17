import httpx
from http import HTTPStatus
from backend.app.exceptions.http import HTTPException
from backend.config import settings
from loguru import logger
from typing import Dict, Any, Callable
import functools


class UmamiClient:
    def __init__(self):
        self.token = None
        self.client = httpx.AsyncClient()

    async def authenticate(self):
        auth_url = f"{settings.umami_settings.URL}/api/auth/login"
        try:
            response = await self.client.post(
                auth_url,
                json={
                    "username": settings.umami_settings.USERNAME,
                    "password": settings.umami_settings.PASSWORD,
                },
                timeout=180,
            )
            response.raise_for_status()
            self.token = response.json().get("token")

            if not self.token:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    detail="Authentication token not found",
                )

            logger.info("Authenticated successfully with token.")
        except (httpx.HTTPStatusError, KeyError) as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Failed to authenticate",
            )

    def make_request(endpoint: str):

        def decorator(func: Callable):
            @functools.wraps(func)
            async def wrapper(self, *args, **kwargs):
                if not self.token:
                    await self.authenticate()

                headers = {"Authorization": f"Bearer {self.token}"}
                url = f"{settings.umami_settings.URL}/api/websites/{settings.umami_settings.WEBSITE_ID}/{endpoint}"

                params = await func(self, *args, **kwargs)

                try:
                    response = await self.client.get(
                        url, headers=headers, params=params, timeout=180
                    )
                    response.raise_for_status()
                    return response.json()

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 401:
                        logger.info("Token expired, re-authenticating...")
                        await self.authenticate()
                        return await self.client.get(
                            url,
                            headers={"Authorization": f"Bearer {self.token}"},
                            params=params,
                            timeout=180,
                        ).json()
                    logger.error(f"Request failed for {endpoint}: {e.response.text}")
                    raise HTTPException(
                        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                        detail=f"Failed to fetch data from {endpoint}",
                    )
                except Exception as e:
                    logger.error(f"Unexpected error for {endpoint}: {e}")
                    raise HTTPException(
                        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                        detail=f"Unexpected error fetching data from {endpoint}",
                    )

            return wrapper

        return decorator

    @make_request("stats")
    async def fetch_stats(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return params

    @make_request("pageviews")
    async def fetch_pageviews(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return params

    @make_request("metrics")
    async def fetch_form_metrics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return params
