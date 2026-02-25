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

    def _get_provider(self, provider: AIProvider) -> AIFormProvider:
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
            openai_form = await provider.generate_form(create_form_ai.prompt)

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

        standard_form = StandardForm()
        standard_form.builder_version = "v2"
        standard_form.title = openai_form.get("title")
        standard_form.theme = chosen_theme
        standard_form.cover_image = cover_image_url
        standard_form.welcome_page = WelcomePageField(
            title=openai_form.get("title"),
            description=openai_form.get("description"),
            layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND,
            imageUrl=welcome_image_url,
        )
        slide_layouts: List[str] = openai_form.get("slide_layouts") or []
        standard_form.fields = [
            StandardFormField(**field)
            for field in self.convert_fields(
                openai_form.get("fields", []), slide_layouts
            )
        ]
        standard_form.thankyou_page = [
            ThankYouPageField(layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND)
        ]
        return standard_form

    def convert_fields(
        self,
        openai_fields: List[Dict[str, Any]],
        slide_layouts: Optional[List[str]] = None,
    ):
        if slide_layouts is None:
            slide_layouts = []
        fields = []
        for index, field in enumerate(openai_fields):
            layout_value = slide_layouts[index] if index < len(slide_layouts) else None
            try:
                layout = LayoutType(layout_value) if layout_value else _DEFAULT_LAYOUT
            except ValueError:
                layout = _DEFAULT_LAYOUT

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
