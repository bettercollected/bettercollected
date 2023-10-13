from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, post, get
from fastapi import Depends
from gunicorn.config import User

from backend.app.container import container
from backend.app.models.minified_form import MinifiedForm
from backend.app.models.template import StandardFormTemplateCamelModel, StandardFormTemplate
from backend.app.router import router
from backend.app.services.template_service import FormTemplateService
from backend.app.services.user_service import get_logged_user
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

    @get("/templates", response_model=List[StandardFormTemplate])
    async def get_templates(self, workspace_id: PydanticObjectId = None, user: User = Depends(get_logged_user)):
        response = await self.form_template_service.get_templates(workspace_id, user)
        return response

    @get('/templates/{template_id}', response_model=StandardFormTemplate)
    async def get_template_by_id(self, template_id: PydanticObjectId, workspace_id: PydanticObjectId = None,
                                 user: User = Depends(get_logged_user)):
        response = await self.form_template_service.get_template_by_id(workspace_id=workspace_id, user=user,
                                                                       template_id=template_id)
        return response

    @post("/workspaces/{workspace_id}/form/{form_id}/template")
    async def create_template_from_form(self, workspace_id: PydanticObjectId,
                                        form_id: PydanticObjectId,
                                        user: User = Depends(get_logged_user)):
        response = await self.workspace_form_service.duplicate_form(
            workspace_id=workspace_id,
            form_id=form_id,
            is_template=True,
            user=user
        )
        return StandardFormTemplateCamelModel(**response.dict())

    @post("/workspaces/{workspace_id}/template")
    async def import_template_to_workspace(self, workspace_id: PydanticObjectId, template_id: PydanticObjectId,
                                           user: User = Depends(get_logged_user)):
        response = await self.form_template_service.import_form_to_workspace(workspace_id, user, template_id)
        return StandardFormTemplateCamelModel(**response.dict())

    @post('/workspaces/{workspace_id}/template/{template_id}', response_model=MinifiedForm)
    async def create_form_from_template(self, workspace_id: PydanticObjectId, template_id: PydanticObjectId,
                                        user: User = Depends(get_logged_user)):
        response = await self.form_template_service.create_form_from_template(workspace_id=workspace_id,
                                                                              template_id=template_id, user=user)
        return response
