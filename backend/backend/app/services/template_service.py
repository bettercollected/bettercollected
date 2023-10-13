from http import HTTPStatus

from beanie import PydanticObjectId
from common.constants import MESSAGE_FORBIDDEN
from common.models.standard_form import StandardForm
from gunicorn.config import User

from backend.app.exceptions import HTTPException
from backend.app.models.minified_form import MinifiedForm
from backend.app.models.template import StandardFormTemplate
from backend.app.repositories.template import FormTemplateRepository
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings


class FormTemplateService:
    def __init__(self, workspace_user_service: WorkspaceUserService, form_template_repo: FormTemplateRepository,
                 workspace_form_service: WorkspaceFormService):
        self.workspace_user_service = workspace_user_service
        self.form_template_repo = form_template_repo
        self.workspace_form_service = workspace_form_service

    async def get_templates(self, workspace_id: PydanticObjectId, user: User):
        if not workspace_id:
            workspace_id = settings.template_settings.PREDEFINED_WORKSPACE_ID
        else:
            await self.workspace_user_service.check_user_has_access_in_workspace(
                workspace_id=workspace_id, user=user
            )
        return await self.form_template_repo.get_templates(workspace_id)

    async def get_template_by_id(self, workspace_id: PydanticObjectId, user: User, template_id: PydanticObjectId):
        if not workspace_id:
            workspace_id = settings.template_settings.PREDEFINED_WORKSPACE_ID
        else:
            await self.workspace_user_service.check_user_has_access_in_workspace(
                workspace_id=workspace_id, user=user
            )
        template = await self.form_template_repo.get_template_by_id(template_id)
        if not template:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Template not found")
        if not template.settings.is_public and (template.workspace_id != workspace_id):
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_FORBIDDEN
            )
        return template

    async def import_form_to_workspace(self, workspace_id: PydanticObjectId, user: User,
                                       template_id: PydanticObjectId):
        await self.get_template_by_id(workspace_id=workspace_id, user=user, template_id=template_id)
        return await self.form_template_repo.import_template_to_workspace(workspace_id, template_id)

    async def create_form_from_template(self, workspace_id: PydanticObjectId, template_id: PydanticObjectId,
                                        user: User):
        await self.workspace_user_service.check_user_has_access_in_workspace(workspace_id=workspace_id, user=user)
        template = await self.form_template_repo.get_template_by_id(template_id)
        minified_form = MinifiedForm(**template.dict())
        return await self.workspace_form_service.create_form(workspace_id=workspace_id,
                                                             form=StandardForm(**minified_form.dict()), user=user)
