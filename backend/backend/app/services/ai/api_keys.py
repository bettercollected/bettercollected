"""Workspace API keys — the auth layer for MCP and the future public API.

Token format: ``bc_<64 hex chars>``. Only the SHA-256 lands in Mongo; the
full token is returned exactly once, at creation. Admin-only management;
authentication resolves a Bearer token to (workspace, scopes, acting user).
"""

import datetime as dt
import hashlib
import secrets
from http import HTTPStatus
from typing import List, Optional

from beanie import PydanticObjectId
from common.models.user import User
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.repositories.workspace_api_key_repository import (
    WorkspaceAPIKeyRepository,
)
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.services.authorization_service import AuthorizationService
from backend.app.models.enum.permission import Permission

# Scopes gate tool/endpoint access. Deliberately coarse in v1.
VALID_SCOPES = {
    "forms:read",
    "forms:write",
    "responses:read",
    "deletion_requests:read",
    "deletion_requests:write",
}

TOKEN_PREFIX = "bc_"
# Scopes that hand respondents' answers, unredacted, to whatever holds the key.
UNREDACTED_RESPONSE_SCOPES = {"responses:read"}


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class CreateAPIKeyDto(_CamelModel):
    name: str = Field(..., min_length=1, max_length=60)
    scopes: List[str] = Field(..., min_length=1)
    # required with responses:read: the admin acknowledges that the key gives
    # an external AI client full, unredacted answers
    acknowledge_unredacted_responses: bool = False


class APIKeyDto(_CamelModel):
    id: str
    name: str
    prefix: str
    scopes: List[str]
    revoked: bool
    created_by: Optional[str] = None
    last_used_at: Optional[dt.datetime] = None
    responses_read_acknowledged_by: Optional[str] = None
    responses_read_acknowledged_at: Optional[dt.datetime] = None


class CreatedAPIKeyDto(APIKeyDto):
    # The one and only time the full token leaves the server.
    token: str


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _to_dto(document: WorkspaceAPIKeyDocument) -> APIKeyDto:
    return APIKeyDto(
        id=str(document.id),
        name=document.name,
        prefix=document.prefix,
        scopes=document.scopes,
        revoked=document.revoked,
        created_by=document.created_by,
        last_used_at=document.last_used_at,
        responses_read_acknowledged_by=document.responses_read_acknowledged_by,
        responses_read_acknowledged_at=document.responses_read_acknowledged_at,
    )


def _c():
    # Resolved at call time: the container imports this module.
    from backend.app.container import container

    return container


class APIKeyService:
    def __init__(
        self,
        authorization_service: AuthorizationService,
        api_key_repo: WorkspaceAPIKeyRepository,
    ):
        self._authorization = authorization_service
        self._api_key_repo = api_key_repo

    async def create_key(
        self, workspace_id: PydanticObjectId, dto: CreateAPIKeyDto, user: User
    ) -> CreatedAPIKeyDto:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )
        invalid = set(dto.scopes) - VALID_SCOPES
        if invalid:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=f"Unknown scopes: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(VALID_SCOPES))}",
            )
        reads_responses = bool(set(dto.scopes) & UNREDACTED_RESPONSE_SCOPES)
        if reads_responses and not dto.acknowledge_unredacted_responses:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=(
                    "A key with responses:read gives the AI client that uses it "
                    "full, unredacted answers. Acknowledge this to create the key."
                ),
            )
        token = TOKEN_PREFIX + secrets.token_hex(32)
        document = WorkspaceAPIKeyDocument(
            workspace_id=workspace_id,
            name=dto.name.strip(),
            key_hash=_hash(token),
            prefix=token[: len(TOKEN_PREFIX) + 8],
            scopes=sorted(set(dto.scopes)),
            created_by=user.id,
            responses_read_acknowledged_by=str(user.id) if reads_responses else None,
            responses_read_acknowledged_at=(
                dt.datetime.now(dt.timezone.utc) if reads_responses else None
            ),
        )
        await self._api_key_repo.save(document)
        return CreatedAPIKeyDto(**_to_dto(document).model_dump(), token=token)

    async def list_keys(
        self, workspace_id: PydanticObjectId, user: User
    ) -> List[APIKeyDto]:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )
        documents = await self._api_key_repo.list_by_workspace(workspace_id)
        return [_to_dto(d) for d in documents]

    async def revoke_key(
        self, workspace_id: PydanticObjectId, key_id: str, user: User
    ) -> List[APIKeyDto]:
        await self._authorization.authorize(
            user, Permission.SECURITY_MANAGE, workspace_id
        )
        document = await self._api_key_repo.get_or_404(PydanticObjectId(key_id))
        if not document or str(document.workspace_id) != str(workspace_id):
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="API key not found"
            )
        document.revoked = True
        await self._api_key_repo.save(document)
        return await self.list_keys(workspace_id, user)

    @staticmethod
    async def authenticate(token: str) -> WorkspaceAPIKeyDocument:
        """Resolve a Bearer token to its key document, or 401."""
        if not token or not token.startswith(TOKEN_PREFIX):
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED, content="Invalid API key"
            )
        document = await _c().workspace_api_key_repo().find_by_key_hash(_hash(token))
        if not document or document.revoked:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                content="Invalid or revoked API key",
            )
        document.last_used_at = dt.datetime.now(dt.timezone.utc)
        await _c().workspace_api_key_repo().save(document)
        return document

    @staticmethod
    def require_scope(document: WorkspaceAPIKeyDocument, scope: str) -> None:
        if scope not in document.scopes:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content=f"This API key lacks the '{scope}' scope.",
            )
