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
from openai.types.chat.completion_create_params import ResponseFormat

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.request_dtos import CreateFormWithAI
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_service import WorkspaceService
from backend.config import settings

client = AsyncOpenAI(api_key=settings.open_ai.API_KEY)

system_prompt = """
Generate a json for a form with the following schema:

{
    title: string;
    description: string;
    fields: Array<{
        title: string;
        description: string;
        type: 'short_text' | 'email' | 'phone_number' | 'date' | 'matrix' | 'multiple_choice' | 'file_upload' | 'rating' | 'dropdown' | 'yes_no' | 'linear_scale' | 'number' | 'link' | 'group';
        properties?: {
            placeholder?: string;
            required?: boolean;
            allowOther?: boolean;
            choices: Array<string>;
            allowMultiple?: boolean;
            steps?: number;
            startFrom?: number;
        };
    }>;
}

Group the fields whenever the fields fall under same category.
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
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": create_form_ai.prompt},
                ],
                response_format=ResponseFormat(type="json_object"),
            )
            openai_form = json.loads(response.choices[0].message.content)
            return await self.workspace_form_service.create_form(
                workspace_id=workspace_id,
                form=self.convert_openai_form_to_standard_form(openai_form=openai_form),
                user=user,
            )
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
                for fieldIndex, openai_group_field in enumerate(
                    field.get("properties", {}).get("fields", [])
                ):
                    slide_fields.append(
                        self.convert_single_field(openai_group_field, fieldIndex)
                    )
            fields.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": StandardFormFieldType.SLIDE,
                    "index": index,
                    "properties": {"fields": slide_fields},
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
            "properties": {
                "placeholder": openai_field.get("properties", {}).get(
                    "placeholder", ""
                ),
            },
            "validations": {
                "required": openai_field.get("properties", {}).get("required", False)
            },
        }
