from http import HTTPStatus
from typing import Dict, Any, Optional

from beanie import PydanticObjectId
from loguru import logger
from common.models.user import User

from backend.app.services.ai.consent import AIConsentService, ai_not_enabled
from backend.app.services.ai.usage import AIUsageGuard, bind_usage
from backend.app.services.openai_compatible_provider import OpenAICompatibleFormProvider
from backend.config import settings
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.request_dtos import CreateFormWithAI, AIProvider
from backend.app.repositories.create_form_prompt_repository import (
    CreateFormPromptRepository,
)
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.services.ai_form_provider import AIFormProvider
from backend.app.services.google_ai_provider import GoogleAIFormProvider
from backend.app.services.openai_provider import OpenAIFormProvider
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_service import WorkspaceService


class OpenAIService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        workspace_form_service: WorkspaceFormService,
        authorization_service=None,
        ai_consent_service: Optional[AIConsentService] = None,
        ai_usage_guard: Optional[AIUsageGuard] = None,
        create_form_prompt_repo: Optional[CreateFormPromptRepository] = None,
    ):
        self.workspace_service: WorkspaceService = workspace_service
        self.create_form_prompt_repo = create_form_prompt_repo
        self.authorization_service = authorization_service
        self.ai_consent_service = ai_consent_service
        self.ai_usage_guard = ai_usage_guard
        self.workspace_form_service: WorkspaceFormService = workspace_form_service
        self._providers: Dict[AIProvider, AIFormProvider] = {
            AIProvider.OPENAI: OpenAIFormProvider(),
            AIProvider.GOOGLE: GoogleAIFormProvider(),
        }
        # The self-host option: any OpenAI-compatible endpoint (Ollama, vLLM…),
        # registered only when actually configured.
        if settings.ai.COMPAT_BASE_URL:
            self._providers[AIProvider.COMPATIBLE] = OpenAICompatibleFormProvider()

    def _get_provider(self, provider: Optional[AIProvider]) -> AIFormProvider:
        if provider is None:
            # Instance-configurable default (AI_DEFAULT_PROVIDER).
            try:
                provider = AIProvider(settings.ai.DEFAULT_PROVIDER)
            except ValueError:
                provider = AIProvider.OPENAI
        impl = self._providers.get(provider)
        if impl is None:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                content=f"Unknown AI provider: {provider}",
            )
        return impl

    async def provider_for_workspace(
        self,
        workspace_id: PydanticObjectId,
        requested: Optional[str] = None,
        *,
        user_id: Optional[Any] = None,
        admit: bool = True,
    ) -> AIFormProvider:
        """The one way to get an AI provider (#715): 403 ``ai_not_enabled``
        unless the workspace opted in, and always the provider it consented
        to. A client-chosen provider other than that one is ignored.

        Then the AI limits (backend/AGENTS.md "AI limits"): with ``admit``
        this is one AI request of ``user_id`` (429 over the rate limits or
        the daily budget), and the provider calls that follow count their
        tokens against the workspace. An import job passes ``admit=False``:
        its upload was admitted (``admit_import``)."""
        consented = await self.ai_consent_service.require_enabled(workspace_id)
        # ``requested`` is honoured only when it is the consented provider,
        # which is the one returned below either way.
        try:
            provider = AIProvider(consented)
        except ValueError:
            provider = None
        if provider is None or provider not in self._providers:
            raise ai_not_enabled(
                "The AI provider this workspace consented to is not available. "
                "A workspace admin needs to turn AI on again."
            )
        impl = self._get_provider(provider)
        if self.ai_usage_guard is not None:
            if admit:
                await self.ai_usage_guard.admit(workspace_id, user_id)
            bind_usage(self.ai_usage_guard, workspace_id)
        return impl

    async def admit_import(self, workspace_id: PydanticObjectId, user: User) -> None:
        """A document upload that asks for AI structuring is one AI request
        of its uploader, admitted at upload (the import runs later, as a
        job). Nothing is counted while the workspace has AI off: the import
        then never uses it."""
        if self.ai_usage_guard is None or self.ai_consent_service is None:
            return
        if await self.ai_consent_service.consented_provider(workspace_id):
            await self.ai_usage_guard.admit(workspace_id, user.id)

    async def create_form_with_ai(
        self,
        workspace_id: PydanticObjectId,
        create_form_ai: CreateFormWithAI,
        user: User,
    ):
        """A new draft form from a prompt, in one request: the outline-first
        pipeline (services/ai/outline_service.py), outline then build, so
        every AI-built form goes through the ops engine. The membership and
        the workspace's AI opt-in are checked first (#717): nothing is
        loaded into a prompt or sent to a provider before both pass.
        Returns the saved form, as before."""
        from backend.app.container import container

        try:
            form, outline, _ = await container.form_outline_service().generate(
                workspace_id,
                create_form_ai.prompt,
                user,
                requested_provider=create_form_ai.provider,
            )
            await self.create_form_prompt_repo.add(
                CreateFormPrompt(
                    prompt=create_form_ai.prompt,
                    openai_response=outline.dump(),
                    created_form=form.model_dump(mode="json"),
                    form_id=PydanticObjectId(form.form_id),
                )
            )
            return form
        except HTTPException:
            raise
        except Exception as e:
            # the error's type only: its message can quote the prompt or reply
            logger.warning("AI form generation failed ({})", type(e).__name__)
            raise HTTPException(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                content="Could not create form using AI",
            )
