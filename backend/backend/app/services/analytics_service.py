from itertools import count
import requests
from loguru import logger
from fastapi import HTTPException
from http import HTTPStatus
from backend.config import settings


class AnalyticsService:
    def __init__(self):
        self.token = None
        self.authenticate()

    def authenticate(self):
        auth_url = f"{settings.umami_settings.URL}/api/auth/login"
        response = requests.post(
            auth_url,
            json={
                "username": settings.umami_settings.USERNAME,
                "password": settings.umami_settings.PASSWORD,
            },
        )

        if response.status_code != 200:
            logger.error(f"Failed to authenticate: {response.text}")
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, detail="Failed to authenticate"
            )

        data = response.json()
        self.token = data.get("token")
        if not self.token:
            logger.error("Authentication failed, token not found in response.")
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                detail="Authentication token not found",
            )

    def fetch_stats(self, params):
        headers = {"Authorization": f"Bearer {self.token}"}
        page_url = f"{settings.umami_settings.URL}/api/websites/{settings.umami_settings.WEBSITE_ID}/stats"
        params = params
        response = requests.get(page_url, headers=headers, params=params, timeout=5)
        if response.status_code != 200:
            logger.error(f"Failed to fetch stats data: {response.text}")
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to fetch stats data",
            )
        return response.json()

    def fetch_pageviews(self, params):
        headers = {"Authorization": f"Bearer {self.token}"}
        page_url = f"{settings.umami_settings.URL}/api/websites/{settings.umami_settings.WEBSITE_ID}/pageviews"
        params = params
        response = requests.get(page_url, headers=headers, params=params, timeout=5)
        if response.status_code != 200:
            logger.error(f"Failed to fetch pageview data: {response.text}")
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to fetch pageview data",
            )
        return response.json()

    def fetch_form_metrics(self, params):
        headers = {"Authorization": f"Bearer {self.token}"}
        page_url = f"{settings.umami_settings.URL}/api/websites/{settings.umami_settings.WEBSITE_ID}/metrics"
        params = params
        response = requests.get(page_url, headers=headers, params=params, timeout=5)
        if response.status_code != 200:
            logger.error(f"Failed to fetch metrics data: {response.text}")
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail="Failed to fetch metrics data",
            )
        return response.json()
