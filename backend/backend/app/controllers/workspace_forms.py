from typing import List

from beanie import PydanticObjectId
from classy_fastapi import Routable, get
from fastapi import Depends

from backend.app.container import container
from backend.app.models.minified_form import MinifiedForm
from backend.app.router import router
from backend.app.services.form_service import FormService
from backend.app.services.user_service import get_logged_user
from common.models.user import User


@router(prefix="/workspaces/{workspace_id}/forms", tags=["Workspace Forms"])
class WorkspaceFormsRouter(Routable):
    def __init__(
        self, form_service: FormService = container.form_service(), *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._form_service = form_service

    @get("")
    async def get_workspace_forms(
        self, workspace_id: PydanticObjectId, user: User = Depends(get_logged_user)
    ) -> List[MinifiedForm]:
        return await self._form_service.get_forms_in_workspace(workspace_id, user)

    @get("/{form_id}")
    async def _get_form_by_id(
        self,
        workspace_id: PydanticObjectId,
        form_id: str,
        user: User = Depends(get_logged_user),
    ):
        return await self._form_service.get_form_by_id(workspace_id, form_id, user)
