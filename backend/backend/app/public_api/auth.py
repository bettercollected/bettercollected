"""Who is calling: a workspace API key as a Bearer token, nothing else.

No cookie is ever read here, so a browser's session can't be used against
this API (no CSRF surface). Per request: the key is resolved (401), counted
against its rate limit (429 with Retry-After), and checked for the
endpoint's scope with the creator's current permissions (403), exactly as
the MCP server checks it (services/api_access.py). Every call is audited by
the wrapper in ``app.py``.
"""

from dataclasses import dataclass
from http import HTTPStatus

from beanie import PydanticObjectId
from common.models.user import User
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.services.ai.api_keys import APIKeyService
from backend.app.services.api_access import acting_user, require_key_scope
from backend.config import settings  # noqa: F401  (builds the settings and the live() groups)
from common.settings.loader import live

# where the wrapper in app.py finds what to audit: (key, operation)
AUDIT_STATE = "public_api_audit"
RATE_LIMIT_SCOPE = "public-api"
WORKSPACE_RATE_LIMIT_SCOPE = "public-api-workspace"

bearer = HTTPBearer(
    auto_error=False,
    scheme_name="apiKey",
    bearerFormat="bc_<64 hex characters>",
    description="A workspace API key, created by a workspace admin under "
    "Settings > API keys: `Authorization: Bearer bc_...`.",
)


@dataclass(frozen=True)
class ApiCaller:
    key: WorkspaceAPIKeyDocument
    user: User

    @property
    def workspace_id(self) -> PydanticObjectId:
        return self.key.workspace_id

    @property
    def key_id(self) -> str:
        return str(self.key.id)


def _c():
    from backend.app.container import container

    return container


async def _hit(scope: str, client: str, limit: int, who: str) -> None:
    if limit <= 0:
        return
    verdict = (
        await _c()
        .rate_limiter()
        .hit(scope, client, limit, live().api.PUBLIC_API_WINDOW_SECONDS)
    )
    if not verdict.allowed:
        raise HTTPException(
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            content={
                "code": "rate_limited",
                "message": f"Too many requests {who}. Retry after "
                f"{verdict.retry_after} seconds.",
            },
            headers={"Retry-After": str(verdict.retry_after)},
        )


async def _rate_limit(key: WorkspaceAPIKeyDocument) -> None:
    """Per API key, and a ceiling for all the workspace's keys together
    (more keys never buy more requests). 0 turns either off."""
    api = live().api
    await _hit(
        RATE_LIMIT_SCOPE,
        str(key.id),
        api.PUBLIC_API_REQUESTS_PER_WINDOW,
        "with this API key",
    )
    await _hit(
        WORKSPACE_RATE_LIMIT_SCOPE,
        str(key.workspace_id),
        api.PUBLIC_API_WORKSPACE_REQUESTS_PER_WINDOW,
        "from this workspace's API keys",
    )


def api_key(scope: str, operation: str):
    """The dependency of an endpoint that needs ``scope``; ``operation``
    names the call in the audit log."""

    async def dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(bearer),
    ) -> ApiCaller:
        token = credentials.credentials if credentials else ""
        try:
            key = await APIKeyService.authenticate(token)
        except HTTPException:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                content={
                    "code": "unauthorized",
                    "message": "Provide a valid workspace API key as a Bearer "
                    "token.",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )
        setattr(request.state, AUDIT_STATE, (key, operation))
        await _rate_limit(key)
        await require_key_scope(key, scope)
        return ApiCaller(key=key, user=acting_user(key))

    return dependency
