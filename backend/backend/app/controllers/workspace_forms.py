from typing import List

from beanie import PydanticObjectId

from backend.app.models.minified_form import MinifiedForm
from backend.app.services.form_service import FormService
from common.models.user import User
from common.utils.cbv import cbv
from common.utils.router import CustomAPIRouter

router = CustomAPIRouter(
    prefix="/workspaces/{workspace_id}/forms"
)


@cbv(router=router)
class WorkspaceFormsRouter:

    def __int__(self, form_service: FormService):
        self._form_service = form_service

    @router.get("")
    async def get_workspace_forms(self, workspace_id: PydanticObjectId,
                                  user: User = None) -> List[MinifiedForm]:
        return await self._form_service.get_forms_in_workspace(workspace_id, user)

    @router.get("/{form_id}")
    async def _get_form_by_id(self, workspace_id: PydanticObjectId, form_id: str, user: User = None):
        return await self._form_service.get_form_by_id(workspace_id, form_id, user)
