from http import HTTPStatus

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, patch, post, delete
from fastapi import Depends
from fastapi_pagination import Page
from starlette.requests import Request

from backend.app.container import container
from backend.app.decorators.user_tag_decorator import user_tag
from backend.app.exceptions import HTTPException
from backend.app.models.enum.user_tag_enum import UserTagType
from backend.app.models.filter_queries.sort import SortRequest
from backend.app.models.minified_form import MinifiedForm
from backend.app.models.response_dtos import (
    WorkspaceFormPatchResponse,
    StandardFormCamelModel,
    StandardFormResponseCamelModel,
)
from backend.app.models.settings_patch import SettingsPatchDto
from backend.app.router import router
from backend.app.services.form_service import FormService
from backend.app.services.user_service import get_logged_user, get_user_if_logged_in
from backend.app.services.workspace_form_service import WorkspaceFormService
from backend.config import settings
from common.models.form_import import FormImportRequestBody
from common.models.standard_form import StandardForm
from common.models.user import User


@router(prefix="/workspaces/{workspace_id}/forms", tags=["Workspace Forms"])
class WorkspaceFormsRouter(Routable):
    def __init__(
        self,
        form_service: FormService = container.form_service(),
        workspace_form_service: WorkspaceFormService = container.workspace_form_service(),
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._form_service = form_service
        self.workspace_form_service = workspace_form_service

    @get("", response_model=Page[MinifiedForm])
    async def get_workspace_forms(
        self,
        workspace_id: PydanticObjectId,
        sort: SortRequest = Depends(),
        user: User = Depends(get_user_if_logged_in),
    ) -> Page[MinifiedForm]:
        forms = await self._form_service.get_forms_in_workspace(
            workspace_id, sort, user
        )
        return forms

    @post("", response_model=StandardFormCamelModel)
    async def create_form(
        self,
        workspace_id: PydanticObjectId,
        form: StandardFormCamelModel,
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
        # Camel model is converted to basic modal so that camel case is not stored in db
        response = await self.workspace_form_service.create_form(
            workspace_id=workspace_id, form=StandardForm(**form.dict()), user=user
        )
        return StandardFormCamelModel(**response.dict())

    @patch("/{form_id}", response_model=StandardFormCamelModel)
    async def patch_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        form: StandardFormCamelModel,
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
        # Camel model is converted to basic modal so that camel case is not stored in db
        response = await self.workspace_form_service.update_form(
            workspace_id=workspace_id,
            form_id=form_id,
            form=StandardForm(**form.dict()),
            user=user,
        )
        return StandardFormCamelModel(**response.dict())

    @post("/{form_id}/response")
    async def respond_to_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response: StandardFormResponseCamelModel,
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
        return await self.workspace_form_service.submit_response(
            workspace_id=workspace_id, form_id=form_id, response=response, user=user
        )

    @delete("/{form_id}/response/{response_id}")
    async def delete_form_response(
        self,
        workspace_id: PydanticObjectId,
        form_id: PydanticObjectId,
        response_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        if not settings.api_settings.ENABLE_FORM_CREATION:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
        return await self.workspace_form_service.delete_form_response(
            workspace_id=workspace_id,
            form_id=form_id,
            response_id=response_id,
            user=user,
        )

    @post("/search")
    async def search_forms_in_workspace(
        self,
        workspace_id: PydanticObjectId,
        query: str,
        user: User = Depends(get_user_if_logged_in),
    ):
        forms = await self._form_service.search_form_in_workspace(
            workspace_id, query, user
        )
        return forms

    @get("/{form_id}")
    async def _get_form_by_id(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_user_if_logged_in),
    ):
        form = await self._form_service.get_form_by_id(workspace_id, form_id, user)
        return form

    @patch("/{form_id}/settings")
    async def patch_settings_for_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        settings: SettingsPatchDto,
        user: User = Depends(get_logged_user),
    ):
        data = await self._form_service.patch_settings_in_workspace_form(
            workspace_id, form_id, settings, user
        )
        return WorkspaceFormPatchResponse(**data.dict())

    @patch("/{form_id}/groups/add", summary="Add form in group")
    @user_tag(tag=UserTagType.FORM_ADDED_TO_GROUP)
    async def patch_groups_for_form(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        group_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_form_service.add_group_to_form(
            workspace_id, form_id, group_id, user
        )

    @delete("/{form_id}/groups", summary="Delete form from group")
    async def delete_group_from_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        group_id: PydanticObjectId,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_form_service.delete_group_from_form(
            workspace_id=workspace_id, form_id=form_id, group_id=group_id, user=user
        )

    @post("/import/{provider}")
    @user_tag(tag=UserTagType.FORM_IMPORTED)
    async def _import_form_to_workspace(
        self,
        workspace_id: PydanticObjectId,
        provider: str,
        form: FormImportRequestBody,
        request: Request,
        user: User = Depends(get_logged_user),
    ):
        await self.workspace_form_service.import_form_to_workspace(
            workspace_id, provider, form, user, request
        )
        return {"message": "Import successful."}

    @delete("/{form_id}")
    async def _delete_form_from_workspace(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        return await self.workspace_form_service.delete_form_from_workspace(
            workspace_id=workspace_id, form_id=form_id, user=user
        )
