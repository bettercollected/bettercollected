import uuid
from http import HTTPStatus
from typing import Dict, Any, List, Optional

from beanie import PydanticObjectId
from common.models.standard_form import (
    StandardForm,
    LayoutType,
    StandardFormFieldType,
    ThankYouPageField,
    WelcomePageField,
    StandardFormField,
)
from common.models.user import User

from backend.app.services.ai.memory import AIMemoryService
from backend.app.services.ai.profile import AIProfileService
from backend.app.services.openai_compatible_provider import OpenAICompatibleFormProvider
from backend.config import settings
from backend.app.services.ai.prompt_builder import compose_generation_prompt
from backend.app.constants.themes import themes
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.request_dtos import CreateFormWithAI, AIProvider
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.services.ai_form_provider import AIFormProvider
from backend.app.services.google_ai_provider import GoogleAIFormProvider
from backend.app.services.openai_provider import OpenAIFormProvider
from backend.app.services.unsplash_service import UnsplashService
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_service import WorkspaceService

_DEFAULT_LAYOUT = LayoutType.SINGLE_COLUMN_NO_BACKGROUND


class OpenAIService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        workspace_form_service: WorkspaceFormService,
    ):
        self.workspace_service: WorkspaceService = workspace_service
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

    async def create_form_with_ai(
        self,
        workspace_id: PydanticObjectId,
        create_form_ai: CreateFormWithAI,
        user: User,
    ):
        workspace = await self.workspace_service.get_workspace_by_id(
            workspace_id=workspace_id
        )
        if not workspace:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Workspace not found"
            )

        try:
            provider = self._get_provider(create_form_ai.provider)
            # Ground the request in the workspace's AI profile (org guidelines /
            # compliance) — plan §2.1/§2.3. Provider-agnostic: prepended to the
            # user turn.
            profile = await AIProfileService.get_profile_for_prompt(workspace_id)
            memory_entries = await AIMemoryService.get_entries_for_prompt(workspace_id, user.id)
            grounded_prompt = compose_generation_prompt(create_form_ai.prompt, profile, memory_entries)
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
            print(e)
            raise HTTPException(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                content="Could not create form using AI",
            )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def convert_openai_form_to_standard_form(self, openai_form: Dict[str, Any]):
        theme_name = openai_form.get("theme_name", "Black")
        chosen_theme = themes.get(theme_name) or themes.get("Black")

        welcome_image_url: Optional[str] = openai_form.get("welcome_image_url")
        cover_image_url: Optional[str] = openai_form.get("cover_image_url")

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
            image_url: Optional[str] = field.get("image_url") or None
            layout_value: Optional[str] = field.get("layout")
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
            fields.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": StandardFormFieldType.SLIDE,
                    "index": index,
                    "image_url": image_url,
                    "properties": {
                        "fields": slide_fields,
                        "layout": layout,
                    },
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
        if type is not None and type == StandardFormFieldType.YES_NO:
            properties["choices"] = [
                {"id": str(uuid.uuid4()), "label": "Yes", "value": "Yes"},
                {"id": str(uuid.uuid4()), "label": "No", "value": "No"},
            ]
        return properties
