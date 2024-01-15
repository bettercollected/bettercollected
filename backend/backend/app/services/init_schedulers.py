import loguru

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_form import WorkspaceFormDocument


async def migrate_schedule_to_temporal():
    temporal_service = container.temporal_service()
    workspace_forms = await WorkspaceFormDocument.find().to_list()
    for workspace_form in workspace_forms:
        if (
            workspace_form.settings.provider
            != "self"
        ):
            try:
                await temporal_service.add_scheduled_job_for_importing_form(
                    workspace_id=workspace_form.workspace_id,
                    form_id=workspace_form.form_id,
                )
                loguru.logger.info("Add job for form id: " + workspace_form.form_id)
            except HTTPException as e:
                loguru.logger.info("Temporal Service Unavailable")
                return
