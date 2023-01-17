from typing import Any

from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger
from starlette.exceptions import HTTPException

from common.constants import MESSAGE_EMPTY_FORM_CONFIG
from common.utils.asyncio_run import asyncio_run
from services.form import FormService
from services.form_response import FormResponseService
from services.form_scheduler_config import FormSchedulerConfigService
from services.google import GoogleService
from services.oauth_credential import OauthCredentialService
from settings import settings


class SchedulerService:
    def __init__(
        self,
        form_service: FormService,
        form_response_service: FormResponseService,
        fsc_service: FormSchedulerConfigService,
        oauth_credential_service: OauthCredentialService,
        google_service: GoogleService,
    ):
        """
        A class that handles scheduling of form imports from Google Forms.

        Args:
            form_service (FormService) : A service that handles form related operations.
            form_response_service (FormResponseService) : A service that handles
                form response related operations.
            fsc_service (FormSchedulerConfigService) : A service that handles
                scheduling configurations related to forms.
            oauth_credential_service (OauthCredentialService) : A service that handles
                OAuth2 credentials related operations.
            google_service (GoogleService) : A service that handles Google API related
                operations.
        """
        self.form_service: FormService = form_service
        self.form_response_service: FormResponseService = form_response_service
        self.fsc_service: FormSchedulerConfigService = fsc_service
        self.oauth_credential_service: OauthCredentialService = oauth_credential_service
        self.google_service: GoogleService = google_service

        _scheduler = settings.scheduler_settings
        _scheduler.add_job(
            callback=self.sync_import_form_and_responses,
            trigger=IntervalTrigger(
                seconds=settings.api_settings.scheduler_time_in_seconds
            ),
            job_id="GOOGLE_FORM_IMPORT_SCHEDULER",
            job_name="GOOGLE_FORM_IMPORT_SCHEDULER",
        )

    def sync_import_form_and_responses(self):
        """
        Synchronously runs the async_import_form_and_responses method,
        with a timeout of 60 seconds.

        This method imports forms and responses from Google Forms.
        """
        asyncio_run(self.async_import_form_and_responses(), timeout=60)

    async def _import_form(self, form_id: str, credentials: Any):
        """
        An asynchronous method that imports a form from Google Forms and
        updates it in the form_service.

        Args:
            form_id (str) : The id of the form to import.
            credentials (Any) : The OAuth2 credentials used to authenticate the request.
        """
        google_form = self.google_service.get_form(
            form_id=form_id, credentials=credentials
        )
        await self.form_service.update_form(form_id, google_form)

    async def _import_responses(self, form_id: str, credentials: Any):
        """
        An asynchronous method that imports responses for a form from Google
        Forms and updates it in the form_response_service.

        Parameters:
            form_id (str) : The id of the form to import responses for.
            credentials (Any) : The OAuth2 credentials used to authenticate the request.
        """
        google_form_responses = self.google_service.get_form_response_list(
            form_id=form_id, credentials=credentials
        ).get("responses", [])

        for form_response in google_form_responses:
            await self.form_response_service.update_submission(
                form_id,
                form_response.get("responseId"),
                form_response,
            )

    async def async_import_form_and_responses(self):
        """
        An asynchronous method that imports forms and their responses from Google
        Forms, as per the configurations present in the FormSchedulerConfigService.

        It verifies the token for each user, gets the form and responses from Google,
        and updates it in the form_service and form_response_service.
        """
        form_configs = await self.fsc_service.get_all_form_scheduler_configs()
        if not form_configs:
            return logger.info(MESSAGE_EMPTY_FORM_CONFIG)
        for config in form_configs:
            if not config.email or not config.formId:
                return logger.info(MESSAGE_EMPTY_FORM_CONFIG)

            # Verifies token, gets form, gets responses from google
            for email in config.email:
                try:
                    oauth_credential = (
                        await self.oauth_credential_service.verify_oauth_token(
                            email=email, provider=config.provider
                        )
                    )
                    await self._import_form(config.formId, oauth_credential.credentials)
                    await self._import_responses(
                        config.formId, oauth_credential.credentials
                    )

                    logger.success(
                        f"Google form with id: {config.formId} import by user: {email}"
                    )
                    break
                except Exception as error:
                    if isinstance(error, HTTPException):
                        error = error.detail
                    logger.error(
                        f"Google form with id: {config.formId} import by user: {email} has failed! "
                        f"Error: {error} Trying with another user."
                    )
                    continue
