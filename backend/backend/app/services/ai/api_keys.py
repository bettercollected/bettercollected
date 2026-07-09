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
from backend.app.schemas.workspace_api_key import WorkspaceAPIKeyDocument
from backend.app.services.workspace_user_service import WorkspaceUserService

# Scopes gate tool/endpoint access. Deliberately coarse in v1.
VALID_SCOPES = {
    "forms:read",
    "forms:write",
    "responses:read",
    "deletion_requests:read",
    "deletion_requests:write",
}

TOKEN_PREFIX = "bc_"


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class CreateAPIKeyDto(_CamelModel):
    name: str = Field(..., min_length=1, max_length=60)
    scopes: List[str] = Field(..., min_length=1)


class APIKeyDto(_CamelModel):
    id: str
    name: str
    prefix: str
    scopes: List[str]
    revoked: bool
    created_by: Optional[str] = None
    last_used_at: Optional[dt.datetime] = None


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
    )


class APIKeyService:
    def __init__(self, workspace_user_service: WorkspaceUserService):
        self._workspace_user_service = workspace_user_service

    async def create_key(
        self, workspace_id: PydanticObjectId, dto: CreateAPIKeyDto, user: User
    ) -> CreatedAPIKeyDto:
        await self._workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        invalid = set(dto.scopes) - VALID_SCOPES
        if invalid:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=f"Unknown scopes: {', '.join(sorted(invalid))}. Valid: {', '.join(sorted(VALID_SCOPES))}",
            )
        token = TOKEN_PREFIX + secrets.token_hex(32)
        document = WorkspaceAPIKeyDocument(
            workspace_id=workspace_id,
            name=dto.name.strip(),
            key_hash=_hash(token),
            prefix=token[: len(TOKEN_PREFIX) + 8],
            scopes=sorted(set(dto.scopes)),
            created_by=user.id,
        )
        await document.save()
        return CreatedAPIKeyDto(**_to_dto(document).model_dump(), token=token)

    async def list_keys(self, workspace_id: PydanticObjectId, user: User) -> List[APIKeyDto]:
        await self._workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        documents = await WorkspaceAPIKeyDocument.find(
            WorkspaceAPIKeyDocument.workspace_id == workspace_id
        ).to_list()
        return [_to_dto(d) for d in documents]

    async def revoke_key(self, workspace_id: PydanticObjectId, key_id: str, user: User) -> List[APIKeyDto]:
        await self._workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        document = await WorkspaceAPIKeyDocument.get(PydanticObjectId(key_id))
        if not document or str(document.workspace_id) != str(workspace_id):
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content="API key not found")
        document.revoked = True
        await document.save()
        return await self.list_keys(workspace_id, user)

    @staticmethod
    async def authenticate(token: str) -> WorkspaceAPIKeyDocument:
        """Resolve a Bearer token to its key document, or 401."""
        if not token or not token.startswith(TOKEN_PREFIX):
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, content="Invalid API key")
        document = await WorkspaceAPIKeyDocument.find_one(
            WorkspaceAPIKeyDocument.key_hash == _hash(token)
        )
        if not document or document.revoked:
            raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, content="Invalid or revoked API key")
        document.last_used_at = dt.datetime.now(dt.timezone.utc)
        await document.save()
        return document

    @staticmethod
    def require_scope(document: WorkspaceAPIKeyDocument, scope: str) -> None:
        if scope not in document.scopes:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                content=f"This API key lacks the '{scope}' scope.",
            )
