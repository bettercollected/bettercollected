from typing import List, Any

from beanie import PydanticObjectId
from classy_fastapi import Routable, get, post, patch
from fastapi import Depends
from starlette.requests import Request

from backend.app.container import container
from backend.app.models.settings_patch import SettingsPatchDto
from backend.app.router import router
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.services.form_service import FormService
from backend.app.services.user_service import get_logged_user, get_user_if_logged_in
from backend.app.services.workspace_form_service import WorkspaceFormService
from common.models.form_import import FormImportRequestBody
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

    @get("")
    async def get_workspace_forms(
            self,
            workspace_id: PydanticObjectId,
            form_id: str = None,
            user: User = Depends(get_user_if_logged_in),
    ):
        # TODO : Refactor this to below endpoint after fixes in frontend
        if form_id:
            form = await self._form_service.get_form_by_id(workspace_id, form_id, user)
            return form
        forms = await self._form_service.get_forms_in_workspace(workspace_id, user)
        return forms

    @post("/search")
    async def search_forms_in_workspace(
            self,
            workspace_id: PydanticObjectId,
            query: str,
    ):
        forms = await self._form_service.search_form_in_workspace(workspace_id, query)
        return forms

    @get("/{form_id}")
    async def _get_form_by_id(
            self,
            workspace_id: PydanticObjectId,
            form_id: str,
            user: User = Depends(get_user_if_logged_in),
    ):
        form = await self._form_service.get_form_by_id(workspace_id, form_id, user)
        return form(
            data=form)

    @patch('/{form_id}/settings')
    async def patch_settings_for_workspace(self, workspace_id: PydanticObjectId, form_id: str,
                                           settings: SettingsPatchDto,
                                           user: User = Depends(get_logged_user)):
        data = await self._form_service.patch_settings_in_workspace_form(workspace_id, form_id, settings, user)
        return data

    @post("/import/{provider}")
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
