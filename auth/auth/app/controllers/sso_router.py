"""Single sign-on through Ory Polis (docs/sso.md). Internal-only, like every
route here: only the backend calls these, after it decided which workspace
and connection a sign-in may use."""

from typing import Optional

from classy_fastapi import Routable, get, post
from pydantic import BaseModel, Field

from auth.app.container import container
from auth.app.controllers.internal_key import INTERNAL_ONLY
from auth.app.router import router
from auth.app.services.sso_service import SsoService
from common.models.user import User


class SsoAccountRequest(BaseModel):
    assertion: str = Field(..., min_length=1, max_length=4096)


class DirectoryAccountRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    # False: only look the account up (deprovisioning never creates one)
    create: bool = False
    first_name: Optional[str] = Field(None, max_length=200)
    last_name: Optional[str] = Field(None, max_length=200)


@router(prefix="/auth/sso", tags=["Single sign-on"], dependencies=INTERNAL_ONLY)
class SsoRoutes(Routable):
    def __init__(
        self, sso_service: SsoService = container.sso_service(), *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.sso_service = sso_service

    @get("/authorize")
    async def _authorize(
        self,
        tenant: str,
        client_id: str,
        context: Optional[str] = None,
        login_hint: Optional[str] = None,
    ):
        """The Polis authorize URL for the workspace (tenant) and connection
        (Polis clientID) the backend resolved."""
        return {
            "auth_url": self.sso_service.authorize_url(
                tenant, client_id, context=context, login_hint=login_hint
            )
        }

    @get("/callback")
    async def _callback(
        self,
        state: str,
        code: Optional[str] = None,
        idp_error: bool = False,
    ):
        """Exchange the code and check it belongs to the sign-in's tenant and
        connection. Returns the asserted email; creates no account."""
        return await self.sso_service.callback(code, state, idp_error=idp_error)

    @post("/account")
    async def _account(self, request: SsoAccountRequest) -> User:
        """Find or create the account for a checked sign-in."""
        return await self.sso_service.account(request.assertion)

    @post("/directory-account")
    async def _directory_account(self, request: DirectoryAccountRequest):
        """Find (or, with ``create``, create) the account of a user the
        workspace's SCIM directory provisions. The backend checked the domain
        and the seat cap first."""
        return await self.sso_service.directory_account(
            request.email,
            request.create,
            first_name=request.first_name,
            last_name=request.last_name,
        )
