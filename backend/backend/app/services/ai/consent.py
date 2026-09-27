"""Workspace AI consent (#715): nothing goes to an AI provider until a
workspace admin has opted in.

``ai_enabled`` lives on the workspace document (default off, also for
workspaces created before the setting existed) together with who enabled it,
when, and the one provider it was granted for. ``require_enabled`` is the
check every AI path runs through ``OpenAIService.provider_for_workspace``
before anything is sent.
"""

import datetime as dt
from http import HTTPStatus
from typing import List, Optional
from urllib.parse import urlparse

from beanie import PydanticObjectId
from common.models.user import User
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from backend.app.exceptions import HTTPException
from backend.app.repositories.workspace_repository import WorkspaceRepository
from backend.app.schemas.workspace import WorkspaceDocument
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings

AI_NOT_ENABLED = "ai_not_enabled"
PROVIDER_IDS = ("openai", "google", "compatible")


def ai_not_enabled(message: str) -> HTTPException:
    return HTTPException(
        status_code=HTTPStatus.FORBIDDEN,
        content={"code": AI_NOT_ENABLED, "message": message},
    )


def default_provider() -> str:
    """The instance's default provider id (``AI_DEFAULT_PROVIDER``)."""
    provider = (settings.ai.DEFAULT_PROVIDER or "openai").lower()
    return provider if provider in PROVIDER_IDS else "openai"


def provider_name(provider: Optional[str]) -> str:
    """The public name of a provider, for disclosures."""
    if provider == "google":
        return "Google Gemini"
    if provider == "compatible":
        host = urlparse(settings.ai.COMPAT_BASE_URL or "").hostname
        return (
            f"this instance's own AI model ({host})"
            if host
            else "this instance's own AI model"
        )
    return "OpenAI"


def provider_configured(provider: Optional[str]) -> bool:
    if provider == "google":
        return bool(settings.google_ai.API_KEY)
    if provider == "compatible":
        return bool(settings.ai.COMPAT_BASE_URL and settings.ai.COMPAT_MODEL)
    if provider == "openai":
        return bool(settings.open_ai.API_KEY)
    return False


class _CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class AIProviderDto(_CamelModel):
    id: str
    name: str
    configured: bool


class WorkspaceAISettingsDto(_CamelModel):
    enabled: bool
    # the provider consent was granted for (None while off)
    provider: Optional[str] = None
    provider_name: Optional[str] = None
    enabled_by: Optional[str] = None
    enabled_at: Optional[dt.datetime] = None
    default_provider: str
    default_provider_name: str
    providers: List[AIProviderDto] = []
    # whether the caller may change the setting (workspace admins only)
    can_manage: bool = False
    # the caller's own "Learn my preferences" setting in this workspace
    learn_preferences: bool = False


class UpdateWorkspaceAISettingsDto(_CamelModel):
    enabled: bool
    # the provider to grant consent for; the instance default when omitted
    provider: Optional[str] = None


class LearnPreferencesDto(_CamelModel):
    learn_preferences: bool


def workspace_ai_provider(workspace: Optional[WorkspaceDocument]) -> Optional[str]:
    """The provider this workspace consented to, or None when AI is off."""
    if not workspace or not workspace.ai_enabled or workspace.disabled:
        return None
    return workspace.ai_provider or None


class AIConsentService:
    def __init__(
        self,
        workspace_repo: WorkspaceRepository,
        workspace_user_service: WorkspaceUserService,
    ):
        self._workspace_repo = workspace_repo
        self._workspace_user_service = workspace_user_service

    async def consented_provider(self, workspace_id: PydanticObjectId) -> Optional[str]:
        """The consented provider id, or None when the workspace has not
        opted in. Never raises for a missing workspace."""
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        return workspace_ai_provider(workspace)

    async def require_enabled(self, workspace_id: PydanticObjectId) -> str:
        """The consented provider id, or 403 ``ai_not_enabled``."""
        provider = await self.consented_provider(workspace_id)
        if not provider:
            raise ai_not_enabled(
                "AI features are off for this workspace. A workspace admin can "
                "turn them on in the workspace's AI settings."
            )
        return provider

    async def _is_admin(self, workspace_id: PydanticObjectId, user: User) -> bool:
        try:
            await self._workspace_user_service.check_is_admin_in_workspace(
                workspace_id=workspace_id, user=user
            )
            return True
        except HTTPException:
            return False

    async def get_settings(
        self, workspace_id: PydanticObjectId, user: User
    ) -> WorkspaceAISettingsDto:
        await self._workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        from backend.app.services.ai.memory import AIMemoryService

        return self._to_dto(
            workspace,
            can_manage=await self._is_admin(workspace_id, user),
            learn_preferences=await AIMemoryService.learns_preferences(
                workspace_id, user.id
            ),
        )

    async def update_settings(
        self,
        workspace_id: PydanticObjectId,
        dto: UpdateWorkspaceAISettingsDto,
        user: User,
    ) -> WorkspaceAISettingsDto:
        await self._workspace_user_service.check_is_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        now = dt.datetime.now(dt.timezone.utc)
        if dto.enabled:
            provider = (dto.provider or default_provider()).lower()
            if provider not in PROVIDER_IDS:
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    content=f"Unknown AI provider: {provider}",
                )
            if not provider_configured(provider):
                raise HTTPException(
                    status_code=HTTPStatus.BAD_REQUEST,
                    content=f"{provider_name(provider)} is not configured on this instance.",
                )
            fields = {
                "ai_enabled": True,
                "ai_provider": provider,
                "ai_enabled_by": str(user.id),
                "ai_enabled_at": now,
            }
        else:
            fields = {
                "ai_enabled": False,
                "ai_provider": None,
                "ai_enabled_by": None,
                "ai_enabled_at": None,
                "ai_disabled_by": str(user.id),
                "ai_disabled_at": now,
            }
        await self._workspace_repo.set_fields(workspace, fields)
        workspace = await self._workspace_repo.find_by_id(workspace_id)
        from backend.app.services.ai.memory import AIMemoryService

        return self._to_dto(
            workspace,
            can_manage=True,
            learn_preferences=await AIMemoryService.learns_preferences(
                workspace_id, user.id
            ),
        )

    @staticmethod
    def _to_dto(
        workspace: WorkspaceDocument, can_manage: bool, learn_preferences: bool
    ) -> WorkspaceAISettingsDto:
        provider = workspace_ai_provider(workspace)
        default = default_provider()
        return WorkspaceAISettingsDto(
            enabled=provider is not None,
            provider=provider,
            provider_name=provider_name(provider) if provider else None,
            enabled_by=workspace.ai_enabled_by if provider else None,
            enabled_at=workspace.ai_enabled_at if provider else None,
            default_provider=default,
            default_provider_name=provider_name(default),
            providers=[
                AIProviderDto(
                    id=p, name=provider_name(p), configured=provider_configured(p)
                )
                for p in PROVIDER_IDS
                if p != "compatible" or settings.ai.COMPAT_BASE_URL
            ],
            can_manage=can_manage,
            learn_preferences=learn_preferences,
        )
