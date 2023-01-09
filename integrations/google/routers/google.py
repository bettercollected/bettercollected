from http import HTTPStatus

from starlette.requests import Request
from starlette.responses import RedirectResponse

from common.utils.cbv import cbv
from dependencies import Container
from settings.router import CustomAPIRouter

router = CustomAPIRouter(prefix="/google")


@cbv(router=router)
class GoogleRouter:
    def __init__(self):
        """
        This class defines the routes for interacting with the Google forms.
        """

        # Injecting dependencies
        self.oauth_google_service = Container.oauth_google_service()

    @router.get("/authorize", status_code=HTTPStatus.OK)
    async def _authorize_google(self, email: str, request: Request):
        client_referer_url = request.headers.get("referer")
        authorization_url, state = await self.oauth_google_service.authorize(
            email, client_referer_url
        )
        return RedirectResponse(authorization_url)

    @router.get("/oauth2callback", status_code=HTTPStatus.OK)
    async def _oauth2callback(self, request: Request):
        url = str(request.url)
        (
            json_credentials,
            client_referer_url,
        ) = await self.oauth_google_service.oauth2callback(url)
        if client_referer_url is not None:
            return RedirectResponse(client_referer_url)
        return json_credentials
