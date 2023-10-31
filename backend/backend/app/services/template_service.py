import os
from http import HTTPStatus

from beanie import PydanticObjectId
from common.constants import MESSAGE_NOT_FOUND
from common.models.standard_form import StandardForm
from fastapi import UploadFile
from gunicorn.config import User

from backend.app.exceptions import HTTPException
from backend.app.models.minified_form import MinifiedForm
from backend.app.models.template import StandardFormTemplate, StandardTemplateSetting
from backend.app.repositories.template import FormTemplateRepository
from backend.app.services.aws_service import AWSS3Service
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.app.services.workspace_user_service import WorkspaceUserService
from backend.config import settings


class FormTemplateService:
    def __init__(
        self,
        workspace_user_service: WorkspaceUserService,
        form_template_repo: FormTemplateRepository,
        aws_service: AWSS3Service,
        workspace_form_service: WorkspaceFormService,
    ):
        self.workspace_user_service = workspace_user_service
        self.form_template_repo = form_template_repo
        self.workspace_form_service = workspace_form_service
        self._aws_service = aws_service

    async def get_templates(self, workspace_id: PydanticObjectId, user: User):
        predefined_workspace = False
        if not workspace_id:
            workspace_id = settings.template_settings.PREDEFINED_WORKSPACE_ID
            predefined_workspace = True
        else:
            await self.workspace_user_service.check_user_has_access_in_workspace(
                workspace_id=workspace_id, user=user
            )
        return await self.form_template_repo.get_templates_with_creator(
            workspace_id=workspace_id, predefined_workspace=predefined_workspace
        )

    async def get_template_by_id(
        self, user: User, template_id: PydanticObjectId, workspace_id: PydanticObjectId = None
    ):
        if template_id and workspace_id:
            template = await self.form_template_repo.get_template_by_workspace_id_n_template_id(
                workspace_id=workspace_id, template_id=template_id)
        else:
            template = await self.form_template_repo.get_template_by_id(template_id)

        if template is None:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, content=MESSAGE_NOT_FOUND)
        if not template.settings.is_public:
            await self.workspace_user_service.check_user_has_access_in_workspace(
                workspace_id=workspace_id if workspace_id else template.workspace_id, user=user
            )
        return template

    async def import_form_to_workspace(
        self, workspace_id: PydanticObjectId, user: User, template_id: PydanticObjectId
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(workspace_id=workspace_id, user=user)
        await self.get_template_by_id(
            user=user, template_id=template_id
        )
        return await self.form_template_repo.import_template_to_workspace(
            workspace_id, template_id
        )

    async def create_form_from_template(
        self, workspace_id: PydanticObjectId, template_id: PydanticObjectId, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        template = await self.form_template_repo.get_template_by_id(template_id)
        minified_form = MinifiedForm(**template.dict())
        return await self.workspace_form_service.create_form(
            workspace_id=workspace_id,
            form=StandardForm(**minified_form.dict()),
            user=user,
        )

    async def create_new_template(
        self,
        workspace_id: PydanticObjectId,
        logo: UploadFile,
        cover_image: UploadFile,
        user: User,
        template_body: StandardFormTemplate,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        template_body.id = PydanticObjectId()
        if logo:
            logo_url = await self._aws_service.upload_file_to_s3(
                file=logo.file,
                key=f"{template_body.id}_logo{os.path.splitext(logo.filename)[1]}",
            )
            template_body.logo = logo_url
        if cover_image:
            cover_image_url = await self._aws_service.upload_file_to_s3(
                file=cover_image.file,
                key=f"{template_body.id}_cover{os.path.splitext(cover_image.filename)[1]}",
            )
            template_body.cover_image = cover_image_url
        return await self.form_template_repo.create_new_template(
            workspace_id=workspace_id, template_body=template_body, user=user
        )

    async def update_template(
        self,
        workspace_id: PydanticObjectId,
        template_id: PydanticObjectId,
        user: User,
        template_body: StandardFormTemplate,
        logo: UploadFile,
        cover_image: UploadFile,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        template = await self.form_template_repo.get_template_by_id(template_id)
        if template.workspace_id != workspace_id:
            raise HTTPException(
                HTTPStatus.FORBIDDEN, "You are not allowed to update this template."
            )
        if logo:
            logo_url = await self._aws_service.upload_file_to_s3(
                file=logo.file,
                key=str(template_id) + f"_logo{os.path.splitext(logo.filename)[1]}",
                previous_image=template.logo,
            )
            template_body.logo = logo_url
        else:
            template_body.logo = (
                template_body.logo if template_body.logo is not None else template.logo
            )
        if cover_image:
            cover_image_url = await self._aws_service.upload_file_to_s3(
                file=cover_image.file,
                key=str(template_id)
                + f"_cover{os.path.splitext(cover_image.filename)[1]}",
                previous_image=template.cover_image,
            )
            template_body.cover_image = cover_image_url
        else:
            template_body.cover_image = (
                template_body.cover_image
                if template_body.cover_image is not None
                else template.cover_image
            )
        return await self.form_template_repo.update_template(
            template_id=template_id, template_body=template_body
        )

    async def update_template_settings(
        self,
        workspace_id: PydanticObjectId,
        template_id: PydanticObjectId,
        user: User,
        settings: StandardTemplateSetting,
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        template = await self.form_template_repo.get_template_by_id(template_id)
        if template.workspace_id != workspace_id:
            raise HTTPException(
                HTTPStatus.FORBIDDEN, "You are not allowed to update this template."
            )
        if settings is not None:
            template.settings.is_public = settings.is_public
        template = await template.save()
        return template

    async def delete_template(
        self, workspace_id: PydanticObjectId, template_id: PydanticObjectId, user: User
    ):
        await self.workspace_user_service.check_user_has_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        template = await self.form_template_repo.get_template_by_id(template_id)
        if not template:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Template not found.")
        if template.workspace_id != workspace_id:
            raise HTTPException(
                HTTPStatus.FORBIDDEN, "You are not allowed to perform this action."
            )
        return await self.form_template_repo.delete_template(template_id)

    async def update_template_preview(self, template_id: PydanticObjectId,
                                      preview_image: UploadFile):
        template = await self.form_template_repo.get_template_by_id(template_id=template_id)
        preview_image = await self._aws_service.upload_file_to_s3(file=preview_image.file, key=template_id,
                                                                  previous_image=template.preview_image)
        template.preview_image = preview_image
        return await template.save()
