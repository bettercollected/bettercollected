"""Auth controller implementation."""
import logging

from classy_fastapi import Routable, get
from starlette.requests import Request

from typeform.app.router import router
from typeform.app.services import auth_service

log = logging.getLogger(__name__)


@router(prefix="/auth")
class AuthRoutes(Routable):

    # @inject
    # def __init__(self, auth_service: Provide[AppContainer.auth_service], *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     self.auth_service = auth_service

    @get(
        "/oauth"
    )
    async def _get_oauth(self, request: Request) -> str:
        client_referer_url = request.headers.get('referer')
        authorization_url = await auth_service.typeform_auth(client_referer_url)
        return authorization_url
