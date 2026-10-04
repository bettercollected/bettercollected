"""Auth controller implementation."""

import logging
from http import HTTPStatus
from typing import List, Optional

from classy_fastapi import Routable, get, post, delete
from common.enums.form_provider import FormProvider
from common.models.user import User, UserLoginWithOTP
from fastapi import Depends
from pydantic import EmailStr
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.user_feedback import UserFeedbackDto
from backend.app.models.dtos.user_status_dto import UserStatusDto
from backend.app.router import router
from backend.app.models.dtos.session_dto import SessionDto
from backend.app.services.auth_cookie_service import (
    delete_token_cookie,
    set_access_token_to_response,
)
from backend.app.services.auth_service import AuthService
from backend.app.services.feedback_service import UserFeedbackService
from backend.app.services.session_service import (
    OTP_METHOD,
    AuthServiceUnavailable,
    RevokeReason,
    SessionService,
)
from backend.app.services.sso.login_service import (
    NONCE_COOKIE,
    SsoLoginService,
    SsoRefused,
    SsoSignIn,
    clear_nonce_cookie,
    set_nonce_cookie,
)
from backend.app.services.user_service import (
    get_full_user,
    get_logged_user,
    get_user_if_logged_in,
    get_user_to_delete,
)
from backend.config import settings
from backend.app.models.enum.form_integration import FormIntegrationType

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
    def __init__(
        self,
        auth_service=container.auth_service(),
        user_feedback_service=container.user_feedback_service(),
        session_service=container.session_service(),
        sso_login_service=container.sso_login_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.auth_service: AuthService = auth_service
        self.session_service: SessionService = session_service
        self.user_feedback_service: UserFeedbackService = user_feedback_service
        self.sso_login_service: SsoLoginService = sso_login_service

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
        request: Request,
        response: Response,
        prospective_pro_user: Optional[bool] = False,
        workspace_id: Optional[str] = None,
    ):
        """``workspace_id``: the workspace whose forms the code was asked for
        (respondent sign-in); see docs/sso.md for what it changes."""
        user = await self.auth_service.validate_otp(
            login_details,
            prospective_pro_user=prospective_pro_user,
            workspace_id=workspace_id,
        )
        await self.session_service.start(
            user,
            response,
            request,
            method=OTP_METHOD,
            scope=user.session_scope,
            scope_workspace_id=user.scope_workspace_id,
        )
        return "Logged In successfully"

    @post(
        "/refresh",
    )
    async def _refresh_access_token(self, request: Request, response: Response):
        """Always goes through the session (never just re-mints a live access
        token) and rotates the refresh token."""
        try:
            await self.session_service.refresh(request, response, rotate=True)
        except HTTPException:  # incl. SessionEnded: 401, cookies cleared
            raise
        except AuthServiceUnavailable as e:
            log.error(
                f"Session refresh: the auth service answered {e.status_code}; "
                "check AUTH_INTERNAL_NOTIFY_KEY on the backend and auth services"
            )
            raise HTTPException(
                HTTPStatus.SERVICE_UNAVAILABLE, "Sign-in is temporarily unavailable."
            )
        except Exception as e:
            log.error(e)
            raise HTTPException(HTTPStatus.UNAUTHORIZED, "No user logged in.")
        response.status_code = HTTPStatus.OK
        return response

    @get("/sessions", response_model=List[SessionDto])
    async def _list_sessions(self, user: User = Depends(get_logged_user)):
        """The signed-in user's live sessions (this one marked ``current``)."""
        sessions = await self.session_service.list_for_user(user.id)
        return [SessionDto.of(s, current_sid=user.sid) for s in sessions]

    @delete("/sessions/{session_id}")
    async def _revoke_session(
        self,
        session_id: str,
        response: Response,
        user: User = Depends(get_logged_user),
    ):
        reason = (
            RevokeReason.LOGOUT
            if session_id == user.sid
            else RevokeReason.SIGNED_OUT_ELSEWHERE
        )
        if not await self.session_service.revoke(session_id, user.id, reason):
            raise HTTPException(HTTPStatus.NOT_FOUND, "Session not found.")
        if session_id == user.sid:
            delete_token_cookie(response)
        return {"revoked": 1}

    @delete("/sessions")
    async def _revoke_other_sessions(self, user: User = Depends(get_logged_user)):
        """Sign out everywhere else: every session but this one."""
        revoked = await self.session_service.revoke_all_for_user(
            user.id, RevokeReason.LOGOUT_EVERYWHERE, except_sid=user.sid
        )
        return {"revoked": revoked}

    @get("/sso/login")
    async def _sso_login(self, request: Request, email: str = ""):
        """Single sign-on (docs/sso.md): send the browser to the identity
        provider of the workspace that verified the work email's domain, or
        back to the login page with ``sso_error=<code>``."""
        try:
            url, nonce = await self.sso_login_service.login_url(
                email[:320], request.headers.get("referer")
            )
        except SsoRefused as refused:
            return RedirectResponse(refused.redirect)
        redirect = RedirectResponse(url)
        # ties the callback to this browser (login CSRF)
        set_nonce_cookie(redirect, nonce)
        return redirect

    @get("/sso/callback")
    async def _sso_callback(
        self,
        request: Request,
        response: Response,
        code: Optional[str] = None,
        state: Optional[str] = None,
        error: Optional[str] = None,
    ):
        """Where Polis returns the browser (the connections' only redirect
        URL). Signs in with a session like every other provider, or records
        a connection test; refusals carry a fixed code only."""
        signed_in = await get_user_if_logged_in(request, response)
        try:
            result = await self.sso_login_service.complete(
                code,
                state,
                idp_error=bool(error),
                signed_in=signed_in,
                nonce=request.cookies.get(NONCE_COOKIE),
            )
        except SsoRefused as refused:
            redirect = RedirectResponse(refused.redirect)
            clear_nonce_cookie(redirect)
            return redirect
        redirect = RedirectResponse(result.redirect)
        clear_nonce_cookie(redirect)
        if isinstance(result, SsoSignIn):
            # the browser's previous session (if any) is replaced: end it
            await self.session_service.end_current(request, RevokeReason.REPLACED)
            await self.session_service.start(
                result.user, redirect, request, method=result.user.auth_method
            )
        return redirect

    @get(
        "/{provider_name}/oauth",
    )
    async def _oauth_provider(
        self,
        provider_name: FormProvider,
        request: Request,
        user=Depends(get_full_user),
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
        user=Depends(get_full_user),
    ):
        if not state or not code:
            return {"message": "You cancelled the authorization request."}
        user, state_data = await self.auth_service.handle_backend_auth_callback(
            provider_name=provider_name, state=state, request=request, user=user
        )

        redirect_uri = state_data.client_referer_uri

        if settings.api_settings.ENABLE_GOOGLE_PICKER_API:
            redirect_uri = redirect_uri + "?modal=true"
        response = RedirectResponse(redirect_uri)
        # same session (sid and email_verified carried over): new access token
        set_access_token_to_response(user, response)
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
        provider_name = ""
        if provider == FormProvider.GOOGLE:
            provider_name = "google"
        else:
            provider_name = "typeform"
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
        request: Request,
        code: Optional[str] = None,
        state: Optional[str] = None,
    ):
        provider_name = ""
        if provider == FormProvider.GOOGLE:
            provider_name = "google"
        else:
            provider_name = "typeform"
        if not state or not code:
            return {"message": "You cancelled the authorization request."}
        user, client_referer_url = await self.auth_service.basic_auth_callback(
            provider_name, code, state
        )
        response = RedirectResponse(client_referer_url)
        if user:
            await self.session_service.start(
                User(**user), response, request, method=provider_name
            )
        return response

    @get(
        "/logout",
    )
    async def logout(self, request: Request, response: Response):
        await self.session_service.end_current(request, RevokeReason.LOGOUT)
        delete_token_cookie(response=response)
        return "Logged out successfully!!!"

    @delete(
        "/user",
    )
    async def delete_user(
        self,
        user: User = Depends(get_user_to_delete),
    ):
        # called by the deletion workflow: the API key and the encrypted
        # deletion request it was started with; deleting the account also
        # deletes all of its sessions
        await self.auth_service.delete_user(user=user)
        return "User Deleted Successfully"

    @post(
        "/user/delete/workflow",
    )
    async def add_workflow_to_delete_user(
        self,
        response: Response,
        user_feedback: UserFeedbackDto,
        user: User = Depends(get_logged_user),
    ):
        await self.user_feedback_service.save_user_feedback(user_feedback=user_feedback)
        resp = await self.auth_service.add_workflow_to_delete_user(user=user)
        delete_token_cookie(response)
        return resp
