from datetime import datetime

from backend.app.exceptions import HTTPException
from backend.app.models.minified_form import MinifiedForm
from backend.app.models.response_dtos import StandardFormCamelModel
from backend.app.models.settings_patch import SettingsPatchDto
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.standard_form import FormDocument

from beanie import PydanticObjectId

from backend.config import settings
from common.models.standard_form import StandardForm
from common.models.user import User

from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from common.services.http_client import HttpClient


class FormService:
    def __init__(
        self,
        workspace_user_repo: WorkspaceUserRepository,
        form_repo: FormRepository,
        workspace_form_repo: WorkspaceFormRepository,
        http_client: HttpClient,
    ):
        self._workspace_user_repo = workspace_user_repo
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self._http_client = http_client

    async def get_forms_in_workspace(self, workspace_id, user) -> Page[MinifiedForm]:
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id, not is_admin
        )
        forms_query = self._form_repo.get_forms_in_workspace_query(
            workspace_id=workspace_id,
            form_id_list=workspace_form_ids,
            is_admin=is_admin,
        )
        forms_page = await paginate(forms_query)

        user_ids = [form.imported_by for form in forms_page.items]

        user_details = await self._http_client.get(
            f"{settings.auth_settings.BASE_URL}/users",
            params={"user_ids": user_ids},
        )

        for form in forms_page.items:
            for user in user_details["users_info"]:
                if form.imported_by == user["_id"]:
                    form.importer_details = user
                    break

        return forms_page

    async def search_form_in_workspace(
        self, workspace_id: PydanticObjectId, query: str
    ):
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id, True
        )
        forms = await self._form_repo.search_form_in_workspace(
            workspace_id=workspace_id, form_ids=form_ids, query=query
        )

        user_ids = [form["imported_by"] for form in forms]

        user_details = await self._http_client.get(
            f"{settings.auth_settings.BASE_URL}/users",
            params={"user_ids": user_ids},
        )

        for form in forms:
            for user in user_details["users_info"]:
                if form["imported_by"] == user["_id"]:
                    form["importer_details"] = user
                    break
        return [StandardForm(**form) for form in forms]

    async def get_form_by_id(
        self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        # TODO : Refactor confusing function get but it instead throws inside
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id=workspace_id, query=form_id, is_admin=is_admin
            )
        )
        form = await self._form_repo.get_forms_in_workspace_query(
            workspace_id=workspace_id,
            form_id_list=[workspace_form.form_id],
            is_admin=is_admin,
        ).to_list()

        user_ids = [form[0]["imported_by"]]
        user_details = await self._http_client.get(
            f"{settings.auth_settings.BASE_URL}/users",
            params={"user_ids": user_ids},
        )
        form[0]["importer_details"] = user_details.get("users_info")[0]
        return StandardFormCamelModel(**form[0])

    async def save_form(self, form: StandardForm):
        existing_form = await FormDocument.find_one({"form_id": form.form_id})
        form_document = FormDocument(**form.dict())
        if existing_form:
            form_document.id = existing_form.id
            form_document.created_at = (
                existing_form.created_at
                if existing_form.created_at
                else datetime.utcnow()
            )
        return await self._form_repo.save_form(form_document)

    async def patch_settings_in_workspace_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        settings: SettingsPatchDto,
        user: User,
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_form = (
            await self._workspace_form_repo.get_workspace_form_in_workspace(
                workspace_id=workspace_id, query=form_id, is_admin=is_admin
            )
        )
        if not workspace_form:
            raise HTTPException(404, "Form not found in workspace")
        if settings.private is not None:
            workspace_form.settings.private = settings.private
        if settings.pinned is not None:
            workspace_form.settings.pinned = settings.pinned
        if settings.customUrl is not None:
            workspace_form_with_custom_slug = (
                await self._workspace_form_repo.get_workspace_form_with_custom_slug(
                    workspace_id, settings.customUrl
                )
            )
            if workspace_form_with_custom_slug:
                raise HTTPException(
                    409, "Form with given custom slug already exists in the workspace!!"
                )
            workspace_form.settings.custom_url = settings.customUrl
        if settings.responseDataOwnerField is not None:
            workspace_form.settings.response_data_owner_field = (
                settings.responseDataOwnerField
            )
        return await self._workspace_form_repo.update(workspace_form.id, workspace_form)

    async def delete_form(self, form_id: str):
        return await self._form_repo.delete_form(form_id)
