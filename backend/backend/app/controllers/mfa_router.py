"""The authenticator-app second factor of the signed-in account (docs/totp.md).

Everything answers 422 ``totp_off`` while ``TOTP_ENABLED`` is off, except the
status. A response that carries a secret or recovery codes is ``no-store``."""

from typing import Optional

from classy_fastapi import Routable, get, post
from common.models.user import User
from fastapi import Depends
from fastapi_camelcase import CamelModel
from pydantic import Field
from starlette.requests import Request
from starlette.responses import Response

from backend.app.container import container
from backend.app.router import router
from backend.app.services.auth_cookie_service import set_access_token_to_response
from backend.app.services.mfa.service import (
    EnrolDto,
    MfaStatusDto,
    RecoveryCodesDto,
)
from backend.app.services.user_service import get_full_user
from backend.app.utils.client_ip import request_client_ip

# a code is six digits or a recovery code of 16 letters and digits with dashes
CODE_MAX = 40


class CodeBody(CamelModel):
    code: Optional[str] = Field(None, max_length=CODE_MAX)


class EnrolBody(CamelModel):
    # the account's current code, when it already has a factor (replacing it)
    code: Optional[str] = Field(None, max_length=CODE_MAX)


class ConfirmBody(CamelModel):
    factor_id: str = Field(max_length=64)
    code: str = Field(max_length=CODE_MAX)


class ChallengeDto(CamelModel):
    logged_in: bool = True
    recovery_left: Optional[int] = None


def _promoted(user: User, response: Response) -> None:
    """The session now holds a second factor: its access token says so at once
    (the claim comes from the session's record, set just before)."""
    set_access_token_to_response(user.model_copy(update={"mfa": True}), response)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router(
    prefix="/auth/mfa",
    tags=["Second factor"],
    responses={
        401: {"description": "Authorization token is missing."},
        403: {"description": "recent_proof_required"},
        409: {"description": "no_factor"},
        422: {"description": "totp_off or invalid_code"},
        429: {"description": "too_many_attempts or mfa_locked (Retry-After)"},
    },
)
class MfaRouter(Routable):
    @get("/status")
    async def status(self, user: User = Depends(get_full_user)) -> MfaStatusDto:
        return await container.mfa_service().status(user)

    @post("/totp/enrol")
    async def enrol(
        self,
        body: EnrolBody,
        request: Request,
        response: Response,
        user: User = Depends(get_full_user),
    ) -> EnrolDto:
        """Start setting up an authenticator app. The secret and the QR code
        are in this response only."""
        _no_store(response)
        return await container.mfa_service().begin_enrolment(
            user, body.code, request_client_ip(request)
        )

    @post("/totp/confirm")
    async def confirm(
        self,
        body: ConfirmBody,
        request: Request,
        response: Response,
        user: User = Depends(get_full_user),
    ) -> RecoveryCodesDto:
        """Finish the setup with the first code. The recovery codes are in this
        response only."""
        _no_store(response)
        codes = await container.mfa_service().confirm_enrolment(
            user, body.factor_id, body.code, request_client_ip(request)
        )
        _promoted(user, response)
        return codes

    @post("/verify")
    async def verify(
        self,
        body: CodeBody,
        request: Request,
        response: Response,
        user: User = Depends(get_full_user),
    ) -> MfaStatusDto:
        """Present the second factor in this session."""
        _no_store(response)
        status = await container.mfa_service().step_up(
            user, body.code, request_client_ip(request)
        )
        _promoted(user, response)
        return status

    @post("/challenge")
    async def challenge(
        self, body: CodeBody, request: Request, response: Response
    ) -> ChallengeDto:
        """The second step of a sign-in: the challenge cookie and a code (or a
        recovery code) make the session. No session is needed, and none exists
        before this succeeds."""
        _no_store(response)
        signed = await container.mfa_signin_service().complete(
            request, response, body.code, request_client_ip(request)
        )
        return ChallengeDto(recovery_left=signed.recovery_left)

    @post("/recovery-codes")
    async def regenerate_recovery_codes(
        self,
        body: CodeBody,
        request: Request,
        response: Response,
        user: User = Depends(get_full_user),
    ) -> RecoveryCodesDto:
        """New recovery codes (a current code in the same request); the old
        ones stop working."""
        _no_store(response)
        return await container.mfa_service().regenerate_recovery_codes(
            user, body.code, request_client_ip(request)
        )

    @post("/totp/disable")
    async def disable(
        self,
        body: CodeBody,
        request: Request,
        response: Response,
        user: User = Depends(get_full_user),
    ) -> MfaStatusDto:
        """Turn the factor off (a current code in the same request)."""
        _no_store(response)
        return await container.mfa_service().disable(
            user, body.code, request_client_ip(request)
        )
