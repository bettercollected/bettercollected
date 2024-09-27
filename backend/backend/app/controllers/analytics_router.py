from fastapi import Depends
from http import HTTPStatus
from classy_fastapi import Routable, get
from common.models.user import User
from backend.app.exceptions.http import HTTPException
from backend.app.services.user_service import get_logged_user
from backend.app.router import router
from backend.app.services.umami_client import UmamiClient
from backend.app.models.dtos.stats_model_dto import StatsModel
from backend.app.models.dtos.pageviews_model_dto import PageViewModel
from backend.app.models.dtos.metrics_model_dto import MetricResponseModel
from backend.app.services.analytics_service import AnalyticsService
from backend.app.container import container
from typing import Optional


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
        analytics_services: AnalyticsService = container.analytics_service(),
        umami_client: UmamiClient = container.umami_client(),
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.umami_client = umami_client
        self.analytics_service = analytics_services

    @get(
        "/{workspace_name}/forms/{slug}/stats",
        response_model=StatsModel,
    )
    async def get_form_stats(
        self,
        workspace_name: str,
        slug: str,
        start_at: int,
        end_at: int,
        referrer: Optional[str] = None,
        title: Optional[str] = None,
        query: Optional[str] = None,
        event: Optional[str] = None,
        host: Optional[str] = None,
        os: Optional[str] = None,
        browser: Optional[str] = None,
        device: Optional[str] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        city: Optional[str] = None,
        user: User = Depends(get_logged_user),
    ):
        await self.analytics_service.check_user_can_view_analytics(
            workspace_name=workspace_name, user=user
        )

        form_url = f"/{workspace_name}/forms/{slug}"

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
        params = {k: v for k, v in params.items() if v is not None}

        stats_data = await self.umami_client.fetch_stats(params)
        return StatsModel(**stats_data)

    @get(
        "/{workspace_name}/forms/{slug}/pageviews",
        response_model=PageViewModel,
    )
    async def get_form_pageviews(
        self,
        workspace_name: str,
        slug: str,
        start_at: int,
        end_at: int,
        unit: str,
        timezone: str,
        referrer: Optional[str] = None,
        title: Optional[str] = None,
        host: Optional[str] = None,
        os: Optional[str] = None,
        browser: Optional[str] = None,
        device: Optional[str] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        city: Optional[str] = None,
        user: User = Depends(get_logged_user),
    ):
        await self.analytics_service.check_user_can_view_analytics(
            workspace_name=workspace_name, user=user
        )

        form_url = f"/{workspace_name}/forms/{slug}"

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

        params = {k: v for k, v in params.items() if v is not None}

        pageview_data = await self.umami_client.fetch_pageviews(params)
        return PageViewModel(**pageview_data)

    @get(
        "/{workspace_name}/forms/{slug}/metrics",
        response_model=MetricResponseModel,
    )
    async def get_form_metrics(
        self,
        workspace_name: str,
        slug: str,
        start_at: int,
        end_at: int,
        type: str,
        referrer: Optional[str] = None,
        query: Optional[str] = None,
        title: Optional[str] = None,
        host: Optional[str] = None,
        os: Optional[str] = None,
        browser: Optional[str] = None,
        device: Optional[str] = None,
        country: Optional[str] = None,
        region: Optional[str] = None,
        city: Optional[str] = None,
        language: Optional[str] = None,
        event: Optional[str] = None,
        limit: Optional[int] = 500,
        user: User = Depends(get_logged_user),
    ):
        await self.analytics_service.check_user_can_view_analytics(
            workspace_name=workspace_name, user=user
        )
        form_url = f"/{workspace_name}/forms/{slug}"

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
        params = {k: v for k, v in params.items() if v is not None}

        metrics_data = await self.umami_client.fetch_form_metrics(params)
        return MetricResponseModel(__root__=metrics_data)
