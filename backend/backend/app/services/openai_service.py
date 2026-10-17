import uuid
from http import HTTPStatus
from typing import Dict, Any, List, Optional

from beanie import PydanticObjectId
from loguru import logger
from common.models.standard_form import (
    StandardForm,
    SECTION_TITLE_MAX_LENGTH,
    WHY_WE_ASK_MAX_LENGTH,
    LayoutType,
    StandardFormFieldType,
    ThankYouPageField,
    WelcomePageField,
    StandardFormField,
)
from common.models.user import User

from backend.app.services.ai.consent import AIConsentService, ai_not_enabled
from backend.app.services.ai.memory import AIMemoryService
from backend.app.services.ai.profile import AIProfileService
from backend.app.services.ai.usage import AIUsageGuard, bind_usage
from backend.app.services.openai_compatible_provider import OpenAICompatibleFormProvider
from backend.config import settings
from backend.app.services.ai.prompt_builder import compose_generation_prompt
from backend.app.constants.themes import new_form_theme, themes
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.request_dtos import CreateFormWithAI, AIProvider
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.services.ai_form_provider import AIFormProvider
from backend.app.services.google_ai_provider import GoogleAIFormProvider
from backend.app.services.image_urls import allowed_image_url_or_none
from backend.app.services.openai_provider import OpenAIFormProvider
from backend.app.services.unsplash_service import UnsplashService
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_service import WorkspaceService
from backend.app.models.enum.permission import Permission

_DEFAULT_LAYOUT = LayoutType.SINGLE_COLUMN_NO_BACKGROUND


def _section_title(value: Any) -> Optional[str]:
    """A generated page's section title, as plain one-line text. One that is
    not text or longer than the cap is left out: the page then shows its
    heading or first question, as it would without one."""
    if not isinstance(value, str):
        return None
    title = " ".join(value.split())
    if not title or len(title) > SECTION_TITLE_MAX_LENGTH:
        return None
    return title


class OpenAIService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        workspace_form_service: WorkspaceFormService,
        authorization_service=None,
        ai_consent_service: Optional[AIConsentService] = None,
        ai_usage_guard: Optional[AIUsageGuard] = None,
    ):
        self.workspace_service: WorkspaceService = workspace_service
        self.authorization_service = authorization_service
        self.ai_consent_service = ai_consent_service
        self.ai_usage_guard = ai_usage_guard
        self.workspace_form_service: WorkspaceFormService = workspace_form_service
        self._unsplash = UnsplashService()
        self._providers: Dict[AIProvider, AIFormProvider] = {
            AIProvider.OPENAI: OpenAIFormProvider(self._unsplash),
            AIProvider.GOOGLE: GoogleAIFormProvider(self._unsplash),
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
        # Membership and the workspace's AI opt-in first (#717): nothing is
        # loaded into a prompt or sent to a provider before both pass.
        await self.authorization_service.authorize(
            user, Permission.FORM_CREATE, workspace_id
        )
        provider = await self.provider_for_workspace(
            workspace_id, create_form_ai.provider, user_id=user.id
        )

        try:
            # Ground the request in the workspace's AI profile (org guidelines /
            # compliance) — plan §2.1/§2.3. Provider-agnostic: prepended to the
            # user turn.
            profile = await AIProfileService.get_profile_for_prompt(workspace_id)
            memory_entries = await AIMemoryService.get_entries_for_prompt(
                workspace_id, user.id
            )
            grounded_prompt = compose_generation_prompt(
                create_form_ai.prompt, profile, memory_entries
            )
            openai_form = await provider.generate_form(grounded_prompt)

            form = await self.workspace_form_service.create_form(
                workspace_id=workspace_id,
                form=self.convert_openai_form_to_standard_form(openai_form=openai_form),
                user=user,
            )
            create_form_prompt = CreateFormPrompt(
                prompt=create_form_ai.prompt,
                openai_response=openai_form,
                created_form=form.model_dump(mode="json"),
                form_id=PydanticObjectId(form.form_id),
            )
            await create_form_prompt.save()
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

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def convert_openai_form_to_standard_form(self, openai_form: Dict[str, Any]):
        # New forms start with Leaflet; another preset only when the model
        # picked one by name (the prompt asks it to, when the request wants
        # other colours). Anything else falls back to Leaflet.
        theme_name = openai_form.get("theme_name")
        chosen_theme = (
            themes[theme_name].model_copy(deep=True)
            if isinstance(theme_name, str) and theme_name in themes
            else new_form_theme()
        )

        # Only images from our storage or Unsplash (services/image_urls.py):
        # respondents' browsers load them directly.
        welcome_image_url: Optional[str] = allowed_image_url_or_none(
            openai_form.get("welcome_image_url")
        )
        cover_image_url: Optional[str] = allowed_image_url_or_none(
            openai_form.get("cover_image_url")
        )

        # Auto-select welcome layout: use image-side layout when image present
        welcome_layout = (
            LayoutType.TWO_COLUMN_IMAGE_LEFT
            if welcome_image_url
            else LayoutType.SINGLE_COLUMN_NO_BACKGROUND
        )

        standard_form = StandardForm()
        standard_form.builder_version = "v2"
        standard_form.title = openai_form.get("title")
        standard_form.theme = chosen_theme
        standard_form.cover_image = cover_image_url
        standard_form.welcome_page = WelcomePageField(
            title=openai_form.get("title"),
            description=openai_form.get("description"),
            layout=welcome_layout,
            imageUrl=welcome_image_url,
        )
        standard_form.fields = [
            StandardFormField(**field)
            for field in self.convert_fields(openai_form.get("fields", []))
        ]
        standard_form.thankyou_page = [
            ThankYouPageField(layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND)
        ]
        return standard_form

    def convert_fields(
        self,
        openai_fields: List[Dict[str, Any]],
    ):
        fields = []
        for index, field in enumerate(openai_fields):
            # Per-field layout: read directly from the AI-generated field dict.
            # Fall back to image-aware default: if image_url present use TWO_COLUMN_IMAGE_LEFT.
            image_url: Optional[str] = allowed_image_url_or_none(field.get("image_url"))
            layout_value: Optional[str] = field.get("layout")
            if field.get("image_url") and not image_url:
                # A refused image takes its image layout with it.
                layout_value = None
            if not layout_value:
                layout_value = (
                    LayoutType.TWO_COLUMN_IMAGE_LEFT.value
                    if image_url
                    else _DEFAULT_LAYOUT.value
                )
            try:
                layout = LayoutType(layout_value)
            except ValueError:
                layout = (
                    LayoutType.TWO_COLUMN_IMAGE_LEFT if image_url else _DEFAULT_LAYOUT
                )

            slide_fields = []
            if field.get("type") != "group":
                slide_fields.append(self.convert_single_field(field, 0))
            else:
                if field.get("title") is not None:
                    slide_fields.append(
                        {
                            "id": str(uuid.uuid4()),
                            "type": StandardFormFieldType.TEXT,
                            "index": 0,
                            "title": {
                                "type": "doc",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {
                                                "text": field.get("title"),
                                                "marks": [
                                                    {"type": "bold"},
                                                    {
                                                        "type": "textStyle",
                                                        "attrs": {
                                                            "fontSize": "32",
                                                            "color": None,
                                                        },
                                                    },
                                                ],
                                                "type": "text",
                                            }
                                        ],
                                    }
                                ],
                            },
                        }
                    )
                for field_index, group_field in enumerate(
                    field.get("properties", {}).get("fields", [])
                ):
                    slide_fields.append(
                        self.convert_single_field(
                            group_field,
                            (
                                field_index + 1
                                if field.get("title") is not None
                                else field_index
                            ),
                        )
                    )
            properties = {"fields": slide_fields, "layout": layout}
            section_title = _section_title(field.get("sectionTitle"))
            if section_title:
                properties["section_title"] = section_title
            fields.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": StandardFormFieldType.SLIDE,
                    "index": index,
                    "image_url": image_url,
                    "properties": properties,
                }
            )
        return fields

    def convert_single_field(self, openai_field: Dict[str, Any], index: int):
        return {
            "type": openai_field.get("type"),
            "title": openai_field.get("title"),
            "id": str(uuid.uuid4()),
            "index": index,
            "description": openai_field.get("description"),
            "properties": self.convert_properties(
                openai_properties=openai_field.get("properties", {}),
                type=openai_field.get("type"),
            ),
            "validations": {
                "required": openai_field.get("properties", {}).get("required", False)
            },
        }

    def convert_properties(
        self, openai_properties: Dict[str, Any], type: Optional[str] = None
    ):
        properties = {}
        if openai_properties.get("placeholder") is not None:
            properties["placeholder"] = openai_properties.get("placeholder")
        if openai_properties.get("allowOther"):
            properties["allow_other_choice"] = True
        if openai_properties.get("allowMultiple"):
            properties["allow_multiple_selection"] = True
        if openai_properties.get("steps") is not None:
            properties["steps"] = openai_properties.get("steps")
        if openai_properties.get("startFrom") is not None:
            properties["start_from"] = openai_properties.get("startFrom")
        if openai_properties.get("choices") is not None:
            properties["choices"] = [
                {"id": str(uuid.uuid4()), "label": choice, "value": choice}
                for choice in openai_properties.get("choices")
            ]
        why_we_ask = openai_properties.get("whyWeAsk")
        if isinstance(why_we_ask, str) and why_we_ask.strip():
            properties["why_we_ask"] = why_we_ask.strip()[:WHY_WE_ASK_MAX_LENGTH]
        if type is not None and type == StandardFormFieldType.YES_NO:
            # Stored the way the builder and the chat ops store them: "Yes" and
            # "No" are fixed values (answers and logic map them to true and
            # false) without a label, so the respondent form shows them in
            # the respondent's language rather than in English.
            properties["choices"] = [
                {"id": str(uuid.uuid4()), "value": "Yes"},
                {"id": str(uuid.uuid4()), "value": "No"},
            ]
        return properties
