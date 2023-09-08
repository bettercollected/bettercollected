from datetime import datetime as dt, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from backend.app.container import container
from backend.app.exceptions import HTTPException
from backend.app.models.enum.update_status import UpdateStatus
from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.services.auth_cookie_service import get_expiry_epoch_after
from backend.config import settings
from common.enums.workspace_invitation_status import InvitationStatus


async def remove_expired_tokens_from_db():
    logger.info("Running expired refresh token remover scheduler")
    await BlackListedRefreshTokens.find({"expiry": {"$lt": dt.utcnow()}}).delete()


async def update_expired_invitations_from_db():
    logger.info("Running scheduler to update expired scheduler")
    timestamp_now = get_expiry_epoch_after(time_delta=timedelta())
    await WorkspaceUserInvitesDocument.find({"expiry": {"$lt": timestamp_now}}).update(
        {"$set": {"invitation_status": InvitationStatus.EXPIRED}}
    )


async def update_all_scheduled_forms(scheduler: AsyncIOScheduler):
    workspace_forms = await WorkspaceFormDocument.find().to_list()
    for workspace_form in workspace_forms:
        logger.info(
            "Updating schedular for form with provider: "
            + workspace_form.settings.provider
            + " and id: "
            + workspace_form.form_id
        )
        if workspace_form.settings.provider != "self":
            scheduler.add_job(
                container.form_schedular().update_form,
                "interval",
                id=f"{workspace_form.settings.provider}_{workspace_form.form_id}",
                coalesce=True,
                replace_existing=True,
                kwargs={
                    "form_id": workspace_form.form_id,
                    "workspace_id": workspace_form.workspace_id,
                },
                minutes=settings.schedular_settings.INTERVAL_MINUTES,
            )


async def migrate_schedule_to_temporal():
    temporal_service = container.temporal_service()
    form_response_service = container.form_response_service()
    workspace_forms = await WorkspaceFormDocument.find().to_list()
    expiring_form_responses = await form_response_service.get_all_expiring_forms_responses()
    for workspace_form in workspace_forms:
        if (
                workspace_form.settings.provider
                != "self"
                # and workspace_form.last_update_status != UpdateStatus.NOT_FOUND
                # and workspace_form.last_update_status != UpdateStatus.INVALID_GRANT
        ):
            try:
                await temporal_service.add_scheduled_job_for_importing_form(
                    workspace_id=workspace_form.workspace_id,
                    form_id=workspace_form.form_id,
                )
                logger.info("Add job for form id: " + workspace_form.form_id)
            except HTTPException as e:
                logger.info("Temporal Service Unavailable")
                return

    # for expiring_form_response in expiring_form_responses:
    #     try:
    #         await temporal_service.add_scheduled_job_for_deleting_response(
    #             response=expiring_form_response)
    #         logger.info("Add job for deletion response: " + expiring_form_response.response_id)
    #     except HTTPException as e:
    #         logger.info("Temporal Service Unavailable")
    #         return


async def init_schedulers(scheduler: AsyncIOScheduler):
    scheduler.start()
    scheduler.add_job(
        remove_expired_tokens_from_db,
        "interval",
        id="blacklisted_refresh_token_remover",
        coalesce=True,
        replace_existing=True,
        minutes=1440,
    )
    scheduler.add_job(
        update_expired_invitations_from_db,
        "interval",
        id="invitations_expired_remover",
        coalesce=True,
        replace_existing=True,
        minutes=1440,
    )
    # await update_all_scheduled_forms(scheduler=scheduler)
