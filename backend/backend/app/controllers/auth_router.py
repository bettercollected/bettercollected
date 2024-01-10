"""Auth controller implementation."""
import logging
from http import HTTPStatus
from typing import Optional

from classy_fastapi import Routable, get, post, delete
from common.enums.form_provider import FormProvider
from common.models.user import User, UserLoginWithOTP
from fastapi import Depends
from pydantic import EmailStr
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from backend.app.container import container
from backend.app.models.dtos.user_feedback import UserFeedbackDto
from backend.app.models.dtos.user_status_dto import UserStatusDto
from backend.app.router import router
from backend.app.services.auth_cookie_service import (
    delete_token_cookie,
    set_tokens_to_response,
    set_access_token_to_response,
)
from backend.app.services.auth_service import AuthService
from backend.app.services.feedback_service import UserFeedbackService
from backend.app.services.user_service import (
    get_logged_user,
    add_refresh_token_to_blacklist,
    get_access_token,
    get_refresh_token, get_api_key,
)

log = logging.getLogger(__name__)


# TODO Extract out separate interface for oauth and use it
@router(
    prefix="/auth",
    tags=["Auth"],
    responses={
        400: {"description": "Bad request"},
        401: {"message": "Authorization token is missing."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class AuthRoutes(Routable):
    def __init__(self, auth_service=container.auth_service(), user_feedback_service=container.user_feedback_service(),
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_service: AuthService = auth_service
        self.user_feedback_service: UserFeedbackService = user_feedback_service

    @get(
        "/status",
        response_model=UserStatusDto,
    )
    async def status(self, user: User = Depends(get_logged_user)):
        return await self.auth_service.get_user_status(user)

    @post(
        "/creator/otp/send",
        responses={
            503: {"description": "Requested Source not available."},
        },
    )
    async def send_otp_for_creator(self, receiver_email: EmailStr):
        return await self.auth_service.send_otp_for_creator(receiver_email)

    @post(
        "/otp/validate",
        responses={
            503: {"description": "Requested Source not available."},
        },
    )
    async def _validate_otp(
        self,
        login_details: UserLoginWithOTP,
        response: Response,
        prospective_pro_user: bool = False,
    ):
        user = await self.auth_service.validate_otp(
            login_details, prospective_pro_user=prospective_pro_user
        )
        set_tokens_to_response(user, response)
        return "Logged In successfully"

    @post(
        "/refresh",
    )
    async def _refresh_access_token(
        self, response: Response, user=Depends(get_logged_user)
    ):
        user_response = await self.auth_service.get_user_status(user=user)
        user_response["sub"] = user_response.get("email")
        set_access_token_to_response(user=User(**user_response), response=response)
        response.status_code = HTTPStatus.OK
        return response

    @get(
        "/{provider_name}/oauth",
    )
    async def _oauth_provider(
        self,
        provider_name: FormProvider,
        request: Request,
        user=Depends(get_logged_user),
    ):
        client_referer_url = request.headers.get("referer")
        oauth_url = await self.auth_service.get_oauth_url(
            provider_name, client_referer_url, user
        )
        return RedirectResponse(oauth_url)

    @get(
        "/{provider_name}/oauth/callback",
    )
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
            state_data.client_referer_uri + "?modal=true"
        )
        set_tokens_to_response(user, response)
        if state_data.client_referer_uri:
            return response
        return {"message": "Token saved successfully."}

    @get(
        "/{provider}/basic",
        responses={
            503: {"description": "Requested Source not available."},
            200: {
                "description": "Redirect to another URL",
                "content": {"text/html": {}},
            },
        },
    )
    async def _basic_auth(
        self,
        provider: FormProvider,
        request: Request,
        creator: bool = False,
        prospective_pro_user: bool = False,
    ):
        provider_name = ''
        if provider == FormProvider.GOOGLE:
            provider_name = 'google'
        else:
            provider_name = 'typeform'
        client_referer_url = request.headers.get("referer")
        basic_auth_url = await self.auth_service.get_basic_auth_url(
            provider_name,
            client_referer_url,
            creator=creator,
            prospective_pro_user=prospective_pro_user,
        )
        return RedirectResponse(basic_auth_url)

    @get(
        "/{provider}/basic/callback",
        responses={
            503: {"description": "Requested Source not available."},
        },
    )
    async def _basic_auth_callback(
        self,
        provider: FormProvider,
        code: Optional[str] = None,
        state: Optional[str] = None,
    ):
        provider_name = ''
        if provider == FormProvider.GOOGLE:
            provider_name = 'google'
        else:
            provider_name = 'typeform'
        if not state or not code:
            return {"message": "You cancelled the authorization request."}
        user, client_referer_url = await self.auth_service.basic_auth_callback(
            provider_name, code, state
        )
        response = RedirectResponse(client_referer_url)
        if user:
            set_tokens_to_response(User(**user), response)
        return response

    @get(
        "/logout",
    )
    async def logout(self, request: Request, response: Response):
        await add_refresh_token_to_blacklist(request=request)
        delete_token_cookie(response=response)
        return "Logged out successfully!!!"

    @delete(
        "/user",
    )
    async def delete_user(
        self,
        request: Request,
        user: User = Depends(get_logged_user),
        api_key: str = Depends(get_api_key)
    ):
        await self.auth_service.delete_user(user=user)
        await add_refresh_token_to_blacklist(request=request)
        return "User Deleted Successfully"

    @post(
        "/user/delete/workflow",
    )
    async def add_workflow_to_delete_user(
        self,
        response: Response,
        user_feedback: UserFeedbackDto,
        access_token=Depends(get_access_token),
        refresh_token=Depends(get_refresh_token),
        user: User = Depends(get_logged_user),
    ):
        await self.user_feedback_service.save_user_feedback(user_feedback=user_feedback)
        resp = await self.auth_service.add_workflow_to_delete_user(
            access_token=access_token, refresh_token=refresh_token, user=user
        )
        delete_token_cookie(response)
        return resp
