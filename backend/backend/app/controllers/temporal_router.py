from beanie import PydanticObjectId
from classy_fastapi import Routable, post
from fastapi import Depends

from backend.app.container import container
from backend.app.router import router
from backend.app.services.init_schedulers import migrate_schedule_to_temporal
from backend.app.services.user_service import get_api_key, get_logged_admin


@router(
    prefix="/temporal",
    tags=["Temporal Router"],
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Authorization token is missing."},
        403: {"description": "You are not allowed to perform this action."},
        404: {"description": "Not Found"},
        405: {"description": "Method not allowed"},
    },
)
class TemporalRouter(Routable):
    def __init__(self, form_schedular=container.form_schedular(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_schedular = form_schedular

    @post("/import/{workspace_id}/form/{form_id}")
    async def import_form_to_workspace(
        self, workspace_id: PydanticObjectId, form_id: str, api_key=Depends(get_api_key)
    ):
        await self.form_schedular.update_form(
            workspace_id=workspace_id, form_id=form_id
        )

    @post("/delete/submissions/{submission_id}")
    async def delete_expired_submissions(
        self, submission_id: str, api_key=Depends(get_api_key)
    ):
        return await self.form_schedular.delete_response(submission_id=submission_id)

    @post("/import/reinitialize")
    async def reinit_temporal_form_import_schedules(self, api_key=Depends(get_api_key), user=Depends(get_logged_admin)):
        await migrate_schedule_to_temporal()
        return "Ok"
