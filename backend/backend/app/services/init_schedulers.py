from datetime import datetime as dt, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from backend.app.container import container
from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.schemas.workspace_form import WorkspaceFormDocument
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.services.auth_cookie_service import get_expiry_epoch_after
from backend.app.utils import AiohttpClient
from backend.config import settings
from common.enums.workspace_invitation_status import InvitationStatus
from common.models.user import User


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
        users_response = await fetch_user_details([workspace_form.user_id])
        if users_response:
            user_response = users_response.get("users_info")[0]
            user = User(
                **user_response,
                id=user_response.get("_id"),
                sub=user_response.get("email"),
            )
            logger.info(
                "Updating schedular for form with provider: "
                + workspace_form.settings.provider
                + " and id: "
                + workspace_form.form_id
            )
            scheduler.add_job(
                container.form_schedular().update_form,
                "interval",
                id=f"{workspace_form.settings.provider}_{workspace_form.form_id}",
                coalesce=True,
                replace_existing=True,
                kwargs={
                    "user": user,
                    "provider": workspace_form.settings.provider,
                    "form_id": workspace_form.form_id,
                    "response_data_owner": workspace_form.settings.response_data_owner_field,
                },
                minutes=settings.schedular_settings.INTERVAL_MINUTES,
            )


async def fetch_user_details(user_ids):
    response = await AiohttpClient.get_aiohttp_client().get(
        f"{settings.auth_settings.BASE_URL}/users",
        params={"user_ids": user_ids},
    )
    return await response.json()


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
    await update_all_scheduled_forms(scheduler=scheduler)
