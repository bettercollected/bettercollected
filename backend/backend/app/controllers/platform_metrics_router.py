"""Platform-wide metrics for platform admins (``ADMIN`` in the token's roles,
not workspace admins): counts of organizations, users, form creators and
responders, forms and responses, with a 12-week series. Aggregates only."""

from classy_fastapi import Routable, get
from fastapi import Depends
from starlette.requests import Request

from backend.app.container import container
from backend.app.models.dtos.platform_metrics_dto import PlatformMetricsDto
from backend.app.router import router
from backend.app.services.platform_metrics_service import PlatformMetricsService
from backend.app.services.user_service import get_access_token, get_logged_admin
from common.models.user import User


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
        self, request: Request, user: User = Depends(get_logged_admin)
    ):
        return await self.platform_metrics_service.get_metrics(
            get_access_token(request)
        )
