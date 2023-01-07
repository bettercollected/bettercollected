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
    """
    Scheduler settings for storing and configuring apscheduler jobs.

    Attributes:
        _scheduler: The scheduler instance.
        jobstores: A dictionary of job stores, with the key being the
            alias and the value being a MongoDBJobStore instance.
        executors: A dictionary of executors, with the key being the
            alias and the value being a ProcessPoolExecutor or
            ThreadPoolExecutor instance.
        mongo_settings: An instance of the MongoSettings class, which
            stores settings for connecting to a MongoDB database.
    """

    def __init__(self):
        self._scheduler: AsyncIOScheduler | None = None
        self.jobstores: Dict[str, MongoDBJobStore] | None = None
        self.executors: Dict[
            str, ProcessPoolExecutor | ThreadPoolExecutor
        ] | None = None
        self.mongo_settings: MongoSettings = MongoSettings()

    @property
    def scheduler(self):
        """
        scheduler: AsyncIOScheduler | None

        The asyncio scheduler instance for the application.
        """
        return self._scheduler

    def load_schedule_or_create_blank(self):
        """
        This method creates a new scheduler or loads an existing
        one from the MongoDB jobstore.

        If an existing scheduler is not found, a new one is
        created and returned.

        Returns:
        AsyncIOScheduler -- The scheduler instance.
        """
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
        """
        Adds a job to the scheduler.

        Args:
            callback: The function to be executed when the job runs.
            trigger: The trigger that determines when the job should run.
            job_id: The unique ID of the job.
            job_name: The name of the job (optional).
            replace_existing: Whether to replace an existing job with the same ID (default: True).
            misfire_grace_time: The time in seconds after the job's scheduled run time that the job is still allowed to be run (optional).
            args: The arguments to pass to the callback function (optional).

        Returns:
            None

        Raises:
            RuntimeError: If the job could not be removed.
            LookupError: If the job id is not found in the scheduler.
        """
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
        """Remove a job from the scheduler.

        Args:
            job_id (str): The id of the job to be removed.

        Returns:
            None

        Raises:
            RuntimeError: If the job could not be removed.
            LookupError: If the job id is not found in the scheduler.
        """
        try:
            self.scheduler.remove_job(job_id=job_id)
            logger.info(f"Removed a job with the id={job_id}")
        except (RuntimeError, LookupError) as error:
            logger.error(MESSAGE_SCHEDULER_REMOVE_JOB_FAILURE)
            logger.error(error)

    def remove_all_jobs(self):
        """
        Remove all jobs from the scheduler.

        Returns:
            None

        Raises:
            RuntimeError: If the scheduler is not running.
            LookupError: If the job is not found.
        """
        try:
            self.scheduler.remove_all_jobs()
            logger.info(MESSAGE_SCHEDULER_REMOVE_ALL_JOBS_SUCCESS)
        except (RuntimeError, LookupError) as error:
            logger.error(MESSAGE_SCHEDULER_REMOVE_ALL_JOBS_FAILURE)
            logger.error(error)

    def shutdown_scheduler(self):
        """
        Shuts down the scheduler instance.

        This method stops the scheduler and waits until all scheduled jobs
        have completed before returning.

        Returns:
            None

        Raises:
            RuntimeError: If the scheduler is not running or has already been shutdown.
            LookupError: If the scheduler cannot be found in the job store.
        """
        try:
            self.scheduler.pause()
            self.scheduler.shutdown(wait=True)
            logger.info(MESSAGE_SCHEDULER_STOP_SUCCESS)
        except (RuntimeError, LookupError) as error:
            logger.error(MESSAGE_SCHEDULER_STOP_FAILURE)
            logger.error(error)
