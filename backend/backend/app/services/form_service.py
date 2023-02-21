from typing import List

from beanie import PydanticObjectId

from backend.app.models.minified_form import MinifiedForm
from backend.app.repositories.form_repository import FormRepository
from backend.app.repositories.workspace_form_repository import WorkspaceFormRepository
from backend.app.repositories.workspace_user_repository import WorkspaceUserRepository
from common.models.user import User


class FormService:

    def __int__(self, workspace_user_repo: WorkspaceUserRepository, form_repo: FormRepository,
                workspace_form_repo: WorkspaceFormRepository):
        self._workspace_user_repo = workspace_user_repo
        self._form_repo = form_repo
        self._workspace_form_repo = workspace_form_repo

    async def get_forms_in_workspace(self, workspace_id, user) -> List[MinifiedForm]:
        is_admin = await self._workspace_user_repo.check_user_is_admin_in_workspace(workspace_id=workspace_id,
                                                                                    user=user)
        query = {
            "workspaceId": workspace_id,
        }
        if not is_admin:
            query["settings.private"] = False

        workspace_form_ids = await self._workspace_form_repo.get_form_ids_in_workspace(workspace_id)
        forms = await self._form_repo.get_forms_in_workspace(workspace_id=workspace_id, form_id_list=workspace_form_ids)
        return [MinifiedForm(**form) for form in forms]

    async def get_form_by_id(self, workspace_id: PydanticObjectId, form_id: str, user: User):
        is_admin = await self._workspace_user_repo.check_user_is_admin_in_workspace(workspace_id=workspace_id,
                                                                                    user=user)
        await self._workspace_form_repo.get_workspace_form_in_workspace(workspace_id=workspace_id,
                                                                        query=form_id,
                                                                        is_admin=is_admin)
        form = await self._form_repo.get_forms_in_workspace(workspace_id=workspace_id, form_id_list=[form_id])
        return form[0]
