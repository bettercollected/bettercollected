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
            logger.info("Attempting to authenticate with Umami API.")
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
                logger.error("Authentication failed: Token not found in response.")
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    detail="Authentication token not found",
                )

            logger.info("Authenticated successfully, token acquired.")
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
                    logger.info("Token missing, initiating authentication.")
                    await self.authenticate()

                headers = {"Authorization": f"Bearer {self.token}"}
                url = f"{settings.umami_settings.URL}/api/websites/{settings.umami_settings.WEBSITE_ID}/{endpoint}"

                params = await func(self, *args, **kwargs)

                logger.info(f"Sending request to {url} with params: {params}")
                try:
                    response = await self.client.get(
                        url, headers=headers, params=params, timeout=180
                    )
                    response.raise_for_status()
                    logger.info(
                        f"Request to {endpoint} successful. Response: {response.json()}"
                    )
                    return response.json()

                except httpx.HTTPStatusError as e:
                    logger.error(
                        f"Request to {endpoint} failed with status {e.response.status_code}: {e.response.text}"
                    )
                    if e.response.status_code == 401:
                        logger.info(
                            "Token expired, re-authenticating and retrying request."
                        )
                        await self.authenticate()
                        retry_response = await self.client.get(
                            url,
                            headers={"Authorization": f"Bearer {self.token}"},
                            params=params,
                            timeout=180,
                        )
                        logger.info(
                            f"Retry response for {endpoint}: {retry_response.json()}"
                        )
                        return retry_response.json()
                    raise HTTPException(
                        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                        detail=f"Failed to fetch data from {endpoint}",
                    )
                except Exception as e:
                    logger.error(f"Unexpected error while accessing {endpoint}: {e}")
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
