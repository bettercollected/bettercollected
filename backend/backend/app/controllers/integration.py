from classy_fastapi import Routable, get, post
from fastapi import Depends
from starlette.requests import Request

from backend.app.container import container
from backend.app.models.dtos.integration_dto import IntegrationCallBackDto
from backend.app.models.enum.form_integration import FormIntegrationType
from backend.app.router import router
from backend.app.services.integration_service import IntegrationService
from backend.app.services.user_service import get_logged_user


@router(
    prefix="/integration",
    tags=["Integration"],
    responses={
        400: {"description": "Bad request"},
        401: {"message": "Authorization token is missing."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class IntegrationRouter(Routable):
    def __init__(self, integration_service: IntegrationService = container.integration_service(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.integration_service = integration_service

    @get(
        "/{integration_type}/oauth",
    )
    async def oauth_provider(
            self,
            integration_type: FormIntegrationType,
            request: Request,
            user=Depends(get_logged_user),
    ):
        client_referer_url = request.headers.get("referer")
        oauth_url = await self.integration_service.get_oauth_url(
            integration_type, client_referer_url, user
        )
        return oauth_url

    @post("/{integration_type}/oauth/callback")
    async def handle_oauth_callback(self, integration_type: FormIntegrationType, callback_data: IntegrationCallBackDto,
                                    user=Depends(get_logged_user)):
        state = callback_data.state
        code = callback_data.code
        form_id = callback_data.form_id
        action_id = callback_data.action_id
        if not code:
            return {"message": "You cancelled the authorization request."}
        response = await self.integration_service.handle_oauth_callback(integration_type, state, code, user, form_id,
                                                                        action_id)
        return response
