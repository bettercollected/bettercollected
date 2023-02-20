from typing import Tuple

from starlette.requests import Request

from backend.config import settings
from common.models.user import User, OAuthState
from common.services.http_client import HttpClient


class AuthService:

    def __init__(self,
                 http_client: HttpClient
                 ):
        self.http_client = http_client

    async def handle_backend_auth_callback(self, request: Request) -> Tuple[User, OAuthState]:
        self.http_client.get(settings.auth_settings.AUTH_CALLBACK_URI
                             )
        # jwt_response = jwt.decode(jwt_token,
        #                           key=settings.auth_settings.JWT_SECRET,
        #                           algorithms=["HS256"]
        #                           )
        # user = User(**jwt_response.get("user"))
        # await workspace_service.create_workspace(user)
        # state = OAuthState(**jwt_response.get("oauth_state"))
        # return user, state
