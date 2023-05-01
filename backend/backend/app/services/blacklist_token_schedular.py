import loguru
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.app.schemas.blacklisted_refresh_tokens import BlackListedRefreshTokens
from datetime import datetime as dt


async def remove_expired_tokens_from_db():
    loguru.logger.info("Running expired refresh token remover scheduler")
    await BlackListedRefreshTokens.find({"expiry": {"$lt": dt.utcnow()}}).delete()


def run_blacklisted_token_scheduler(scheduler: AsyncIOScheduler):
    scheduler.add_job(
        remove_expired_tokens_from_db,
        "interval",
        id="blacklisted_refresh_token_remover",
        coalesce=True,
        replace_existing=True,
        minutes=1440,
    )
