from typing import Optional

import loguru

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.config import settings
from datetime import timedelta


async def migrate_schedule_to_temporal():
    temporal_service = container.temporal_service()
    workspace_forms = await WorkspaceFormDocument.find().to_list()
    for workspace_form in workspace_forms:
        if workspace_form.settings.provider != "self":
            try:
                await temporal_service.add_scheduled_job_for_importing_form(
                    workspace_id=workspace_form.workspace_id,
                    form_id=workspace_form.form_id,
                )
                await temporal_service.update_interval_of_schedule(
                    workspace_form.workspace_id, workspace_form.form_id
                )
                loguru.logger.info("Add job for form id: " + workspace_form.form_id)
            except HTTPException as e:
                loguru.logger.info("Temporal Service Unavailable")
                return


async def update_schedule_intervals(interval_in_minutes: Optional[int]):
    temporal_service = container.temporal_service()
    workspace_forms = await WorkspaceFormDocument.find().to_list()
    for workspace_form in workspace_forms:
        if workspace_form.settings.provider != "self":
            try:
                await temporal_service.update_interval_of_schedule(
                    workspace_form.workspace_id,
                    workspace_form.form_id,
                    interval=timedelta(minutes=interval_in_minutes)
                    if interval_in_minutes
                    else settings.schedular_settings.INTERVAL_MINUTES,
                )
                loguru.logger.info(
                    "Updated schedule according to new env for  "
                    + workspace_form.form_id
                )
            except HTTPException as e:
                loguru.logger.info("Error updating Schedule Interval")
                return
