from typing import Dict

from apscheduler.executors.pool import ProcessPoolExecutor, ThreadPoolExecutor
from apscheduler.jobstores.mongodb import MongoDBJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger
from pymongo import MongoClient
from pytz import utc

from settings import MongoSettings
from common.constants import (
    MESSAGE_SCHEDULER_ADD_JOB_FAILURE,
    MESSAGE_SCHEDULER_REMOVE_ALL_JOBS_FAILURE,
    MESSAGE_SCHEDULER_REMOVE_ALL_JOBS_SUCCESS,
    MESSAGE_SCHEDULER_REMOVE_JOB_FAILURE,
    MESSAGE_SCHEDULER_START_FAILURE,
    MESSAGE_SCHEDULER_START_SUCCESS,
    MESSAGE_SCHEDULER_STOP_FAILURE,
    MESSAGE_SCHEDULER_STOP_SUCCESS,
)


class SchedulerSettings:
    # Faced some issues with pickling when inheriting BaseSettings

    def __init__(self):
        self._scheduler: AsyncIOScheduler | None = None
        self.jobstores: Dict[str, MongoDBJobStore] | None = None
        self.executors: Dict[
            str, ProcessPoolExecutor | ThreadPoolExecutor
        ] | None = None
        self.mongo_settings: MongoSettings = MongoSettings()

    @property
    def scheduler(self):
        return self._scheduler

    def load_schedule_or_create_blank(self):
        try:
            self.jobstores = {
                "default": MongoDBJobStore(
                    database=self.mongo_settings.db,
                    client=MongoClient(self.mongo_settings.uri),
                    collection="schedulers",
                ),
            }
            self.executors = {
                "default": ThreadPoolExecutor(20000),
                "processpool": ProcessPoolExecutor(20000),
            }
            job_defaults = {"coalesce": True, "max_instances": 20000}

            self._scheduler = AsyncIOScheduler(
                jobstores=self.jobstores,
                executors=self.executors,
                job_defaults=job_defaults,
                timezone=utc,
            )

            self._scheduler.start()
            logger.info(MESSAGE_SCHEDULER_START_SUCCESS)
            return self._scheduler
        except (RuntimeError, LookupError) as error:
            logger.error(MESSAGE_SCHEDULER_START_FAILURE)
            logger.error(error)

    def add_job(
        self,
        callback,
        trigger,
        job_id,
        job_name=None,
        replace_existing=True,
        misfire_grace_time=None,
        args=None,
    ):
        try:
            self.scheduler.add_job(
                callback,
                trigger=trigger,
                id=job_id,
                name=job_name,
                replace_existing=replace_existing,
                misfire_grace_time=misfire_grace_time,
                args=args,
            )
            logger.info(f"Added a job with the id={job_id}")
        except (RuntimeError, LookupError) as error:
            logger.error(MESSAGE_SCHEDULER_ADD_JOB_FAILURE)
            logger.error(error)

    def remove_job(self, job_id):
        try:
            self.scheduler.remove_job(job_id=job_id)
            logger.info(f"Removed a job with the id={job_id}")
        except (RuntimeError, LookupError) as error:
            logger.error(MESSAGE_SCHEDULER_REMOVE_JOB_FAILURE)
            logger.error(error)

    def remove_all_jobs(self):
        try:
            self.scheduler.remove_all_jobs()
            logger.info(MESSAGE_SCHEDULER_REMOVE_ALL_JOBS_SUCCESS)
        except (RuntimeError, LookupError) as error:
            logger.error(MESSAGE_SCHEDULER_REMOVE_ALL_JOBS_FAILURE)
            logger.error(error)

    def shutdown_scheduler(self):
        try:
            self.scheduler.pause()
            self.scheduler.shutdown(wait=True)
            logger.info(MESSAGE_SCHEDULER_STOP_SUCCESS)
        except (RuntimeError, LookupError) as error:
            logger.error(MESSAGE_SCHEDULER_STOP_FAILURE)
            logger.error(error)
