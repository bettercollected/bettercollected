from fastapi import HTTPException, Depends, Query
from http import HTTPStatus
from beanie import PydanticObjectId
from classy_fastapi import Routable, get
from common.models.user import User
from backend.app.services.user_service import get_user_if_logged_in
from backend.app.router import router
from backend.app.services.analytics_service import AnalyticsService
from backend.app.models.dtos.stats_model_dto import StatsModel
from backend.app.models.dtos.pageviews_model_dto import PageViewModel, PageDataModel
from backend.app.container import container
from typing import List


@router(
    prefix="",
    tags=["Form Analytics"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Authorization token is missing."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class FormAnalyticsRouter(Routable):
    def __init__(
        self,
        analytics_service: AnalyticsService = container.analytics_service(),
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.analytics_service = analytics_service

    @get(
        "/{workspace_id}/forms/{form_id}/stats",
        response_model=StatsModel,
    )
    async def get_form_stats(
        self,
        workspace_id: str,
        form_id: str,
        start_at: int,
        end_at: int,
        referrer: str | None = None,
        title: str | None = None,
        query: str | None = None,
        event: str | None = None,
        host: str | None = None,
        os: str | None = None,
        browser: str | None = None,
        device: str | None = None,
        country: str | None = None,
        region: str | None = None,
        city: str | None = None,
        user: User = Depends(get_user_if_logged_in),
    ):
        if not user:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, detail="Unauthorized"
            )

        form_url = f"/{workspace_id}/forms/{form_id}"

        if not start_at or not end_at:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Invalid time range"
            )
        params = {
            "startAt": start_at,
            "endAt": end_at,
            "url": form_url,
            "referrer": referrer,
            "title": title,
            "query": query,
            "event": event,
            "host": host,
            "os": os,
            "browser": browser,
            "device": device,
            "country": country,
            "region": region,
            "city": city,
        }

        self.analytics_service.authenticate()
        stats_data = self.analytics_service.fetch_stats(params)
        return StatsModel(**stats_data)

    @get(
        "/{workspace_id}/forms/{form_id}/pageviews",
        response_model=PageViewModel,
    )
    async def get_form_pageviews(
        self,
        workspace_id: str,
        form_id: str,
        start_at: int,
        end_at: int,
        unit: str,
        timezone: str,
        referrer: str | None = None,
        title: str | None = None,
        host: str | None = None,
        os: str | None = None,
        browser: str | None = None,
        device: str | None = None,
        country: str | None = None,
        region: str | None = None,
        city: str | None = None,
        user: User = Depends(get_user_if_logged_in),
    ):
        if not user:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, detail="Unauthorized"
            )

        form_url = f"/{workspace_id}/forms/{form_id}"

        if not start_at or not end_at:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Invalid time range"
            )
        params = {
            "startAt": start_at,
            "endAt": end_at,
            "url": form_url,
            "referrer": referrer,
            "title": title,
            "host": host,
            "os": os,
            "browser": browser,
            "device": device,
            "country": country,
            "region": region,
            "city": city,
            "unit": unit,
            "timezone": timezone,
        }

        self.analytics_service.authenticate()
        pageview_data = self.analytics_service.fetch_pageviews(params)
        return PageViewModel(**pageview_data)

    @get(
        "/{workspace_id}/forms/{form_id}/metrics",
        response_model=List[PageDataModel],
    )
    async def get_form_metrics(
        self,
        workspace_id: str,
        form_id: str,
        start_at: int,
        end_at: int,
        type: str,
        referrer: str | None = None,
        query: str | None = None,
        title: str | None = None,
        host: str | None = None,
        os: str | None = None,
        browser: str | None = None,
        device: str | None = None,
        country: str | None = None,
        region: str | None = None,
        city: str | None = None,
        language: str | None = None,
        event: str | None = None,
        limit: int | None = 500,
        user: User = Depends(get_user_if_logged_in),
    ):
        if not user:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, detail="Unauthorized"
            )

        form_url = f"/{workspace_id}/forms/{form_id}"

        if not start_at or not end_at:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail="Invalid time range"
            )
        params = {
            "startAt": start_at,
            "endAt": end_at,
            "url": form_url,
            "referrer": referrer,
            "title": title,
            "host": host,
            "os": os,
            "browser": browser,
            "device": device,
            "country": country,
            "region": region,
            "city": city,
            "type": type,
            "language": language,
            "event": event,
            "limit": limit,
            "query": query,
        }

        self.analytics_service.authenticate()
        metrics_data = self.analytics_service.fetch_form_metrics(params)
        return metrics_data
