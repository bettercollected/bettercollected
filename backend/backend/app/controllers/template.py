import json
from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, post, get, patch, delete
from fastapi import Depends, UploadFile, Form
from gunicorn.config import User

from backend.app.container import container
from backend.app.models.minified_form import MinifiedForm
from backend.app.models.template import (
    StandardFormTemplateCamelModel,
    StandardFormTemplateResponse,
    StandardFormTemplateResponseCamelModel,
    StandardTemplateSettingsCamelModel,
)
from backend.app.router import router
from backend.app.services.template_service import FormTemplateService
from backend.app.services.user_service import get_logged_user, get_user_if_logged_in
from backend.app.services.workspace_form_service import WorkspaceFormService


@router(
    prefix="",
    tags=["Form Templates"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Authorization token is missing."},
        403: {"description": "You are not allowed to perform this action."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class FormTemplateRouter(Routable):
    def __init__(
        self,
        workspace_form_service: WorkspaceFormService = container.workspace_form_service(),
        form_template_service: FormTemplateService = container.form_template_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.workspace_form_service = workspace_form_service
        self.form_template_service = form_template_service

    @get("/templates", response_model=List[StandardFormTemplateResponseCamelModel])
    async def get_templates(
        self,
        workspace_id: PydanticObjectId = None,
        user: User = Depends(get_logged_user),
    ):
        response = await self.form_template_service.get_templates(workspace_id, user)
        return response

    @get("/templates/{template_id}", response_model=StandardFormTemplateCamelModel)
    async def get_template_by_id(
        self,
        template_id: PydanticObjectId,
        workspace_id: PydanticObjectId = None,
        user: User = Depends(get_user_if_logged_in),
    ):
        response = await self.form_template_service.get_template_by_id(
            workspace_id=workspace_id, user=user, template_id=template_id
        )
        return StandardFormTemplateCamelModel(**response.dict())

    @post("/workspaces/{workspace_id}/form/{form_id}/template")
    async def create_template_from_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        response = await self.workspace_form_service.duplicate_form(
            workspace_id=workspace_id, form_id=form_id, is_template=True, user=user
        )
        return StandardFormTemplateResponse(**response.dict())

    @post(
        "/workspaces/{workspace_id}/template",
        response_model=StandardFormTemplateResponseCamelModel,
    )
    async def create_new_template(
        self,
        workspace_id: PydanticObjectId,
        template_body: str = Form(),
        logo: UploadFile = None,
        cover_image: UploadFile = None,
        user: User = Depends(get_logged_user),
    ):
        template = json.loads(template_body)
        response = await self.form_template_service.create_new_template(
            workspace_id=workspace_id,
            user=user,
            template_body=StandardFormTemplateCamelModel(**template),
            logo=logo,
            cover_image=cover_image,
        )
        return response

    @post(
        "/workspaces/{workspace_id}/template/{template_id}/import",
        response_model=StandardFormTemplateCamelModel,
    )
    async def import_template_to_workspace(
        self,
        workspace_id: PydanticObjectId,
        template_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        response = await self.form_template_service.import_form_to_workspace(
            workspace_id, user, template_id
        )
        return StandardFormTemplateCamelModel(**response.dict())

    @post(
        "/workspaces/{workspace_id}/template/{template_id}", response_model=MinifiedForm
    )
    async def create_form_from_template(
        self,
        workspace_id: PydanticObjectId,
        template_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        response = await self.form_template_service.create_form_from_template(
            workspace_id=workspace_id, template_id=template_id, user=user
        )
        return response

    @patch(
        "/workspaces/{workspace_id}/template/{template_id}",
        response_model=StandardFormTemplateCamelModel,
    )
    async def update_template(
        self,
        workspace_id: PydanticObjectId,
        template_id: PydanticObjectId,
        logo: UploadFile = None,
        cover_image: UploadFile = None,
        template_body: str = Form(),
        user: User = Depends(get_logged_user),
    ):
        template = json.loads(template_body)
        response = await self.form_template_service.update_template(
            workspace_id=workspace_id,
            template_id=template_id,
            user=user,
            template_body=StandardFormTemplateCamelModel(**template),
            logo=logo,
            cover_image=cover_image,
        )
        return response

    @patch(
        "/workspaces/{workspace_id}/template/{template_id}/settings",
        response_model=StandardFormTemplateCamelModel,
    )
    async def update_template_settings(
        self,
        workspace_id: PydanticObjectId,
        template_id: PydanticObjectId,
        settings: StandardTemplateSettingsCamelModel,
        user: User = Depends(get_logged_user),
    ):
        return await self.form_template_service.update_template_settings(
            workspace_id=workspace_id,
            template_id=template_id,
            settings=settings,
            user=user,
        )

    @delete("/workspaces/{workspace_id}/template/{template_id}")
    async def delete_template(
        self,
        workspace_id: PydanticObjectId,
        template_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        response = await self.form_template_service.delete_template(
            workspace_id=workspace_id, template_id=template_id, user=user
        )
        return response
