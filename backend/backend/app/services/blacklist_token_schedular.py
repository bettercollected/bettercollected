from datetime import datetime as dt, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from backend.app.schemas.workspace_invitation import WorkspaceUserInvitesDocument
from backend.app.services.auth_cookie_service import get_expiry_epoch_after
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


def init_schedulers(scheduler: AsyncIOScheduler):
    scheduler.add_job(
        remove_expired_tokens_from_db,
        "interval",
        id="blacklisted_refresh_token_remover",
        coalesce=True,
        replace_existing=True,
        minutes=1440,
    )
    scheduler.add_job(
        remove_expired_tokens_from_db,
        "interval",
        id="invitations_expired_remover",
        coalesce=True,
        replace_existing=True,
        minutes=1440,
    )
