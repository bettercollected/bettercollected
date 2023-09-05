from datetime import datetime
from http import HTTPStatus
from typing import List

from beanie import PydanticObjectId
from fastapi_pagination import Page
from fastapi_pagination.ext.beanie import paginate

from backend.app.constants.consents import default_consents
from backend.app.exceptions import HTTPException
from backend.app.models.dtos.workspace_member_dto import (
    FormImporterDetails,
)
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.minified_form import MinifiedForm
from backend.app.models.settings_patch import SettingsPatchDto
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from backend.app.schemas.standard_form import FormDocument
from backend.app.services.user_tags_service import UserTagsService
from backend.app.utils import AiohttpClient
from backend.config import settings
from common.models.consent import Consent, ConsentType, ConsentCategory
from common.models.standard_form import StandardForm
from common.models.user import User


class FormService:
    def __init__(
            self,
            workspace_user_repo: WorkspaceUserRepository,
            form_repo: FormRepository,
            workspace_form_repo: WorkspaceFormRepository,
            user_tags_service: UserTagsService,
    ):
        self._workspace_user_repo = workspace_user_repo
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo
        self.user_tags_service = user_tags_service

    async def get_forms_in_workspace(
            self, workspace_id, sort, user
    ) -> Page[MinifiedForm]:
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id, not is_admin, user
        )
        forms_query = self._form_repo.get_forms_in_workspace_query(
            workspace_id=workspace_id,
            form_id_list=workspace_form_ids,
            is_admin=is_admin,
            sort=sort,
        )

        forms_page = await paginate(forms_query)

        user_ids = [form.imported_by for form in forms_page.items]

        user_details = (
            {"users_info": []}
            if not user_ids
            else await self.fetch_user_details(user_ids=user_ids)
        )

        for form in forms_page.items:
            for user_info in user_details.get("users_info", []):
                if form.imported_by == user_info["_id"]:
                    form.importer_details = FormImporterDetails(
                        **user_info, id=form.imported_by
                    )
                    break

        return forms_page

    async def fetch_user_details(self, user_ids):
        response = await AiohttpClient.get_aiohttp_client().get(
            f"{settings.auth_settings.BASE_URL}/users",
            params={"user_ids": user_ids},
        )
        return await response.json()

    async def search_form_in_workspace(
            self, workspace_id: PydanticObjectId, query: str, user: User
    ):
        form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id=workspace_id, is_not_admin=True, user=user
        )
        forms = await self._form_repo.search_form_in_workspace(
            workspace_id=workspace_id, form_ids=form_ids, query=query
        )

        user_ids = [form["imported_by"] for form in forms]

        user_details = (
            {"users_info": []}
            if not user_ids
            else await self.fetch_user_details(user_ids=user_ids)
        )

        for form in forms:
            for user_info in user_details["users_info"]:
                if form["imported_by"] == user.id:
                    form["importer_details"] = FormImporterDetails(
                        **user_info, id=form["imported_by"]
                    )
                    break
        return [MinifiedForm(**form) for form in forms]

    async def get_form_by_id(
            self, workspace_id: PydanticObjectId, form_id: str, user: User
    ):
        is_admin = await self._workspace_user_repo.has_user_access_in_workspace(
            workspace_id=workspace_id, user=user
        )
        if not user:
            workspace_form = await self._workspace_form_repo.get_workspace_form_with_custom_slug_form_id(
                workspace_id=workspace_id, custom_url=form_id
            )
            if workspace_form.settings.private:
                raise HTTPException(
                    status_code=HTTPStatus.UNAUTHORIZED,
                    content="Private Form Login to continue",
                )

        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(
            workspace_id=workspace_id,
            is_not_admin=not is_admin,
            user=user,
            match_query={
                "$or": [{"form_id": form_id}, {"settings.custom_url": form_id}]
            },
        )
        form = await self._form_repo.get_forms_in_workspace_query(
            workspace_id=workspace_id,
            form_id_list=workspace_form_ids,
            is_admin=is_admin,
        ).to_list()

        if not form:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND, content="Form Not Found"
            )

        user_ids = [form[0]["imported_by"]] if form else []
        user_details = (
            {"users_info": []}
            if not user_ids
            else await self.fetch_user_details(user_ids=user_ids)
        )
        user_info = user_details.get("users_info")[0]
        form[0]["importer_details"] = FormImporterDetails(
            **user_info, id=user_info.get("_id")
        )
        minified_form = MinifiedForm(**form[0])
        if minified_form.consent is None:
            minified_form.consent = default_consents
        return minified_form

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
            await self.user_tags_service.add_user_tag(
                user_id=user.id, tag=UserTagType.CUSTOM_SLUG
            )
            workspace_form_with_custom_slug = await self._workspace_form_repo.get_workspace_form_with_custom_slug_form_id(
                workspace_id, settings.customUrl
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

    async def delete_forms(self, form_ids: List[str]):
        return await self._form_repo.delete_forms(form_ids=form_ids)

    async def create_form(self, form: StandardForm) -> FormDocument:
        return await self._form_repo.create_form(form=form)

    async def update_form(self, form_id: PydanticObjectId, form: StandardForm):
        return await self._form_repo.update_form(form_id=form_id, form=form)

    async def get_form_document_by_id(self, form_id: str):
        return await self._form_repo.get_form_document_by_id(form_id)
