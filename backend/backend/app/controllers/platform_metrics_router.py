"""Platform-wide metrics for platform admins (``ADMIN`` in the token's roles,
not workspace admins): counts of organizations, users, form creators and
responders, forms and responses, with a 12-week series. Aggregates only."""

import http.cookies
from typing import Optional

from classy_fastapi import Routable, get
from fastapi import Depends
from starlette.requests import Request
from starlette.responses import Response

from backend.app.container import container
from backend.app.models.dtos.platform_metrics_dto import PlatformMetricsDto
from backend.app.router import router
from backend.app.services.platform_metrics_service import PlatformMetricsService
from backend.app.services.user_service import get_access_token, get_logged_admin
from common.models.user import User


def forwarded_access_token(request: Request, response: Response) -> Optional[str]:
    """The access token to forward to auth: the one ``get_logged_user`` just
    issued on this response when the request's had expired, else the request's."""
    for header in response.headers.getlist("set-cookie"):
        cookie = http.cookies.SimpleCookie(header)
        if "Authorization" in cookie:
            return cookie["Authorization"].value
    return get_access_token(request)


# Plain Routable, not CustomRoutable: ``users: null`` (auth unreachable) must
# stay in the body rather than be dropped as a None field.
@router(prefix="/admin", tags=["Platform admin"])
class PlatformMetricsRouter(Routable):
    def __init__(
        self,
        platform_metrics_service=container.platform_metrics_service(),
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.platform_metrics_service: PlatformMetricsService = platform_metrics_service

    @get(
        "/metrics",
        response_model=PlatformMetricsDto,
        responses={
            401: {"description": "Authorization token is missing."},
            403: {"description": "Platform admins only."},
        },
    )
    async def get_platform_metrics(
        self,
        request: Request,
        response: Response,
        user: User = Depends(get_logged_admin),
    ):
        return await self.platform_metrics_service.get_metrics(
            forwarded_access_token(request, response)
        )
