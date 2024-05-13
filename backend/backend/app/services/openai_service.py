import json
from http import HTTPStatus

from beanie import PydanticObjectId
from openai import AsyncOpenAI

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.request_dtos import CreateFormWithAI
from backend.app.services.workspace_service import WorkspaceService
from backend.config import settings

client = AsyncOpenAI(api_key=settings.open_ai.API_KEY)


system_prompt = ""


class OpenAIService:
    def __init__(self, workspace_service: WorkspaceService):
        self.workspace_service: WorkspaceService = workspace_service

    async def create_form_with_ai(
        self, workspace_id: PydanticObjectId, create_form_ai: CreateFormWithAI
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
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": create_form_ai.prompt},
                ],
            )
            return json.loads(response.choices[0].message.content)

        except Exception as e:
            print(e)
            pass
