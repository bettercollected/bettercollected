import json
import uuid
from http import HTTPStatus
from typing import Dict, Any, List

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
from openai import AsyncOpenAI
from openai.types.shared_params import ResponseFormatJSONObject

from backend.app.constants.themes import themes
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.request_dtos import CreateFormWithAI
from backend.app.schemas.create_form_prompts import CreateFormPrompt
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_service import WorkspaceService
from backend.config import settings

client = AsyncOpenAI(api_key=settings.open_ai.API_KEY)

system_prompt = """
Generate a json for a form with the following schema:

interface Field {
        title: string;
        description: string;
        type: 'short_text' | 'email' | 'phone_number' | 'date' | 'multiple_choice' | 'file_upload' | 'rating' | 'dropdown' | 'yes_no' | 'linear_scale' | 'number' | 'link' | 'group';
        properties?: {
            placeholder?: string;
            required?: boolean;
            allowOther?: boolean;
            fields?: Array<Field>
            choices: Array<string>;
            allowMultiple?: boolean;
            steps?: number;
            startFrom?: number;
        };
    }

interface Form {
    title: string;
    description: string;
    fields: Array<Field>;
}

Group the fields whenever the fields fall under same category.

Note: steps is the no of stars to be shown.
"""


class OpenAIService:
    def __init__(
        self,
        workspace_service: WorkspaceService,
        workspace_form_service: WorkspaceFormService,
    ):
        self.workspace_service: WorkspaceService = workspace_service
        self.workspace_form_service: WorkspaceFormService = workspace_form_service

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
            response = await client.chat.completions.create(
                model=settings.open_ai.MODAL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": create_form_ai.prompt},
                ],
                response_format=ResponseFormatJSONObject(type="json_object"),
            )
            openai_form = json.loads(response.choices[0].message.content)
            form = await self.workspace_form_service.create_form(
                workspace_id=workspace_id,
                form=self.convert_openai_form_to_standard_form(openai_form=openai_form),
                user=user,
            )
            create_form_prompt = CreateFormPrompt(
                prompt=create_form_ai.prompt,
                openai_response=openai_form,
                created_form=form.dict(),
                form_id=PydanticObjectId(form.form_id),
            )
            await create_form_prompt.save()
            return form
        except Exception as e:
            print(e)
            raise HTTPException(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                content="Could not create form using AI",
            )

    def convert_openai_form_to_standard_form(self, openai_form: Dict[str, Any]):
        standard_form = StandardForm()
        standard_form.builder_version = "v2"
        standard_form.title = openai_form.get("title")
        standard_form.theme = themes.get("Black")
        standard_form.welcome_page = WelcomePageField(
            title=openai_form.get("title"),
            description=openai_form.get("description"),
            layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND,
        )
        standard_form.fields = [
            StandardFormField(**field)
            for field in self.convert_fields(openai_form.get("fields"))
        ]
        standard_form.thankyou_page = [
            ThankYouPageField(layout=LayoutType.SINGLE_COLUMN_NO_BACKGROUND)
        ]
        return standard_form

    def convert_fields(self, openai_fields: List[Dict[str, Any]]):
        fields = []
        for index, field in enumerate(openai_fields):
            slide_fields = []
            if not field.get("type") == "group":
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
                for fieldIndex, openai_group_field in enumerate(
                    field.get("properties", {}).get("fields", [])
                ):
                    slide_fields.append(
                        self.convert_single_field(
                            openai_group_field,
                            fieldIndex + 1
                            if field.get("title") is not None
                            else fieldIndex,
                        )
                    )
            fields.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": StandardFormFieldType.SLIDE,
                    "index": index,
                    "properties": {
                        "fields": slide_fields,
                        "layout": LayoutType.SINGLE_COLUMN_NO_BACKGROUND,
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

    def convert_properties(self, openai_properties: Dict[str, Any], type: str = None):
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
