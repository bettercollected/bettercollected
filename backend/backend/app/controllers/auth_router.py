"""Auth controller implementation."""
import logging
from http import HTTPStatus
from typing import Optional

from classy_fastapi import Routable, get, post, delete
from fastapi import Depends
from pydantic import EmailStr
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.user_status_dto import UserStatusDto
from backend.app.router import router
from backend.app.services.auth_cookie_service import (
    delete_token_cookie,
    set_tokens_to_response,
    set_access_token_to_response,
)
from backend.app.services.user_service import (
    get_logged_user,
    add_refresh_token_to_blacklist,
    get_access_token,
    get_refresh_token,
)
from backend.config import settings
from common.models.user import User, UserLoginWithOTP

log = logging.getLogger(__name__)


# TODO Extract out separate interface for oauth and use it
@router(prefix="/auth", tags=["Auth"])
class AuthRoutes(Routable):
    def __init__(self, auth_service=container.auth_service(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_service = auth_service

    @get("/status", response_model=UserStatusDto)
    async def status(self, user: User = Depends(get_logged_user)):
        return await self.auth_service.get_user_status(user)

    @post("/creator/otp/send")
    async def send_otp_for_creator(self, receiver_email: EmailStr):
        return await self.auth_service.send_otp_for_creator(receiver_email)

    @post("/otp/validate")
    async def _validate_otp(self, login_details: UserLoginWithOTP, response: Response):
        user = await self.auth_service.validate_otp(login_details)
        set_tokens_to_response(user, response)
        return "Logged In successfully"

    @post("/refresh")
    async def _refresh_access_token(
        self, response: Response, user=Depends(get_logged_user)
    ):
        user_response = await self.auth_service.get_user_status(user=user)
        user_response["sub"] = user_response.get("email")
        set_access_token_to_response(user=User(**user_response), response=response)
        return response

    @get("/{provider_name}/oauth")
    async def _oauth_provider(
        self,
        provider_name: str,
        request: Request,
        user=Depends(get_logged_user),
    ):
        client_referer_url = request.headers.get("referer")
        oauth_url = await self.auth_service.get_oauth_url(
            provider_name, client_referer_url, user
        )
        return RedirectResponse(oauth_url)

    @get("/{provider_name}/oauth/callback")
    async def _auth_callback(
        self,
        request: Request,
        provider_name: str = None,
        state: str = None,
        code: str = None,
        user=Depends(get_logged_user),
    ):
        if not state or not code:
            return {"message": "You cancelled the authorization request."}
        user, state_data = await self.auth_service.handle_backend_auth_callback(
            provider_name=provider_name, state=state, request=request, user=user
        )
        response = RedirectResponse(
            state_data.client_referer_uri + "?modal=" + provider_name
        )
        set_tokens_to_response(user, response)
        if state_data.client_referer_uri:
            return response
        return {"message": "Token saved successfully."}

    @get("/{provider}/basic")
    async def _basic_auth(self, provider: str, request: Request, creator: bool = False):
        client_referer_url = request.headers.get("referer")
        basic_auth_url = await self.auth_service.get_basic_auth_url(
            provider, client_referer_url, creator=creator
        )
        return RedirectResponse(basic_auth_url)

    @get("/{provider}/basic/callback")
    async def _basic_auth_callback(
        self, provider: str, code: Optional[str] = None, state: Optional[str] = None
    ):
        if not state or not code:
            return {"message": "You cancelled the authorization request."}
        user, client_referer_url = await self.auth_service.basic_auth_callback(
            provider, code, state
        )
        response = RedirectResponse(client_referer_url)
        if user:
            set_tokens_to_response(User(**user), response)
        return response

    @get("/logout")
    async def logout(self, request: Request, response: Response):
        await add_refresh_token_to_blacklist(request=request)
        delete_token_cookie(response=response)
        return "Logged out successfully!!!"

    @delete("/user")
    async def delete_user(
        self,
        request: Request,
        user: User = Depends(get_logged_user),
    ):
        if request.headers.get("api_key") != settings.temporal_settings.api_key:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content="You are not allowed to perform this action.",
            )
        await self.auth_service.delete_user(user=user)
        await add_refresh_token_to_blacklist(request=request)
        return "User Deleted Successfully"

    @post("/user/delete/workflow")
    async def add_workflow_to_delete_user(
        self,
        response: Response,
        access_token=Depends(get_access_token),
        refresh_token=Depends(get_refresh_token),
        user: User = Depends(get_logged_user),
    ):
        resp = await self.auth_service.add_workflow_to_delete_user(
            access_token=access_token, refresh_token=refresh_token, user=user
        )
        delete_token_cookie(response)
        return resp
