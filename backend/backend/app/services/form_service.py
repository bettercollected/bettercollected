from typing import List

from beanie import PydanticObjectId

from backend.app.exceptions import HTTPException
from backend.app.models.minified_form import MinifiedForm
from backend.app.models.settings_patch import SettingsPatchDto
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.standard_form import FormDocument
from common.models.standard_form import StandardFormDto
from common.models.user import User


class FormService:
    def __init__(
        self,
        workspace_user_repo: WorkspaceUserRepository,
        form_repo: FormRepository,
        workspace_form_repo: WorkspaceFormRepository,
    ):
        self._workspace_user_repo = workspace_user_repo
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo

    async def get_forms_in_workspace(self, workspace_id, user) -> List[MinifiedForm]:
        is_admin = await self._workspace_user_repo.is_user_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        query = {
            "workspace_id": workspace_id,
        }
        if not is_admin:
            query["settings.private"] = False

        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id
        )
        forms = await self._form_repo.get_forms_in_workspace(
            workspace_id=workspace_id, form_id_list=workspace_form_ids
        )
        return [MinifiedForm(**form) for form in forms]

    async def search_form_in_workspace(
        self, workspace_id: PydanticObjectId, query: str
    ):
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id, True
        )
        forms = await self._form_repo.search_form_in_workspace(
            workspace_id=workspace_id, form_ids=form_ids, query=query
        )
        return [StandardFormDto(**form) for form in forms]

    async def patch_settings_in_workspace_form(self, workspace_id: PydanticObjectId, form_id: str,
                                               settings: SettingsPatchDto, user: User):
        is_admin = await self._workspace_user_repo.is_user_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_form = await self._workspace_form_repo.get_workspace_form_in_workspace(
            workspace_id=workspace_id, query=form_id, is_admin=is_admin
        )
        if not workspace_form:
            raise HTTPException(404, "Form not found in workspace")
        if settings.private is not None:
            workspace_form.settings.private = settings.private
        if settings.pinned is not None:
            workspace_form.settings.pinned = settings.pinned
        if settings.customUrl is not None:
            workspace_form_with_custom_slug = await self._workspace_form_repo.get_workspace_form_with_custom_slug(
                workspace_id,
                settings.customUrl)
            if workspace_form_with_custom_slug:
                raise HTTPException(409, "Form with given custom slug already exists in the workspace!!")
            workspace_form.settings.custom_url = settings.customUrl
        if settings.responseDataOwnerField is not None:
            workspace_form.settings.response_data_owner_field = settings.responseDataOwnerField
        return await self._workspace_form_repo.update(workspace_form.id, workspace_form)

    async def get_form_by_id(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        is_admin = await self._workspace_user_repo.is_user_admin_in_workspace(
            workspace_id=workspace_id, user=user
        )
        # TODO : Refactor confusing function get but it instead throws inside
        workspace_form = await self._workspace_form_repo.get_workspace_form_in_workspace(
            workspace_id=workspace_id, query=form_id, is_admin=is_admin
        )
        form = await self._form_repo.get_forms_in_workspace(
            workspace_id=workspace_id, form_id_list=[workspace_form.form_id]
        )
        return StandardFormDto(**form[0])

    async def save_form(self, form: StandardFormDto):
        existing_form = await FormDocument.find_one({"formId": form.formId})
        form_document = FormDocument(**form.dict())
        if existing_form:
            form_document.id = existing_form.id
        return await self._form_repo.save_form(form_document)
