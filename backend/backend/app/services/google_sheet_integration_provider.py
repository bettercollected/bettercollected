import json
from http import HTTPStatus
from typing import Tuple

from common.configs.crypto import Crypto
from common.enums.form_provider import FormProvider
from common.services.http_client import HttpClient
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.app.models.dtos.action_dto import AddActionToFormDto
from backend.app.models.workspace import ParameterValue
from backend.app.services.base_integration_provider import BaseIntegrationProvider
from backend.app.services.form_plugin_provider_service import FormPluginProviderService
from backend.app.services.google_sheets_oauth import GoogleSheetsOAuth
from backend.app.services.integration_action_service import IntegrationActionService
from backend.app.services.sheets_reconsent import (
    RECONSENT_REQUIRED_CODE,
    is_legacy_credential,
)
from backend.app.repositories.form_repository import FormRepository
from backend.config import settings


def backend_runs_sheets_oauth() -> bool:
    """GOOGLE_SHEETS_OAUTH=backend: the backend runs the flow and creates the
    spreadsheet itself (google_sheets_oauth.py); otherwise the Google Forms
    service does, as before."""
    return settings.google_sheets.SHEETS_OAUTH == "backend"


class GoogleSheetIntegrationProvider(BaseIntegrationProvider):
    def __init__(
        self,
        form_provider_service: FormPluginProviderService,
        crypto: Crypto,
        http_client: HttpClient,
        integration_action_service: IntegrationActionService,
        form_repo: FormRepository,
    ):
        self.form_provider_service = form_provider_service
        self.crypto = crypto
        self.http_client = http_client
        self.integration_action_service = integration_action_service
        self._form_repo = form_repo
        self.sheets_oauth = GoogleSheetsOAuth(crypto)

    async def get_basic_integration_oauth_url(
        self, client_referer_url: str, *args, **kwargs
    ) -> str:
        # Bound to the user who starts the flow; checked on the callback.
        state = {
            "client_referer_uri": client_referer_url,
            "user_id": kwargs.get("user_id"),
        }
        state = self.crypto.encrypt(json.dumps(state))
        if backend_runs_sheets_oauth():
            return self.sheets_oauth.authorization_url(state)
        provider_url = await self.form_provider_service.get_provider_url(
            FormProvider.GOOGLE
        )
        authorization_url = (
            f"{provider_url}/{FormProvider.GOOGLE}/oauth/integration/authorize"
        )
        response_data = await self.http_client.get(
            authorization_url, params={"state": state}, timeout=60
        )
        oauth_url = response_data.get("oauth_url")
        return oauth_url

    async def handle_basic_integration_callback(
        self, code: str, state: str, form_id: str, action_id: str, *args, **kwargs
    ) -> Tuple[bool, str]:
        if backend_runs_sheets_oauth():
            credential = await self.sheets_oauth.exchange_code(code=code, state=state)
            # one write with the re-consent markers cleared; then the legacy
            # grant it replaced is revoked (a failure queues a retry)
            outcome = await self.integration_action_service.store_sheets_grant(
                form_id=form_id, action_id=action_id, credentials=credential
            )
            logger.info(
                "google sheets connected: form={} action={} old_grant={}",
                form_id,
                action_id,
                outcome,
            )
            return "Added credentials to form action"
        provider_url = await self.form_provider_service.get_provider_url(
            FormProvider.GOOGLE
        )
        fetch_credential_url = (
            f"{provider_url}/{FormProvider.GOOGLE}/oauth/integration/callback"
        )
        credential = await self.http_client.post(
            fetch_credential_url, params={"state": state, "code": code}, timeout=60
        )
        await self.integration_action_service.add_credentials_to_form_action(
            form_id=form_id, action_id=action_id, credentials=credential
        )
        return "Added credentials to form action"

    async def add_google_sheet_id_to_form_action(
        self, action_params: AddActionToFormDto, form_id: str
    ):
        form = await self._form_repo.get_form_document_by_id(form_id)
        title = [
            params.value
            for params in action_params.parameters
            if params.name == "Title"
        ]
        credential = [
            secrets.value
            for secrets in form.secrets[str(action_params.action_id)]
            if secrets.name == "Credentials"
        ]
        if backend_runs_sheets_oauth():
            if is_legacy_credential(credential[0], self.crypto):
                # A grant from before drive.file (services/sheets_reconsent.py)
                # is never refreshed or used again: the user reconnects first.
                # Raised before the form is saved, so the action's parameters,
                # and its reconsent markers, stay as they are.
                logger.info(
                    "google sheet not created, reconsent required: form={} action={}",
                    form_id,
                    action_params.action_id,
                )
                raise HTTPException(
                    HTTPStatus.CONFLICT,
                    content={
                        "code": RECONSENT_REQUIRED_CODE,
                        "message": "Reconnect Google Sheets before saving this action.",
                    },
                )
            sheet_id = await self.sheets_oauth.create_spreadsheet(
                title=title[0], encrypted_credential=credential[0]
            )
            logger.info(
                "google sheet created: form={} action={}",
                form_id,
                action_params.action_id,
            )
            return ParameterValue(name="Google Sheet Id", value=sheet_id)
        provider_url = await self.form_provider_service.get_provider_url(
            FormProvider.GOOGLE
        )
        create_google_sheet_url = (
            f"{provider_url}/{FormProvider.GOOGLE}/forms/create_google_sheet"
        )
        # In the body, never the query string: a URL ends up in access logs.
        response = await self.http_client.post(
            create_google_sheet_url,
            json={"title": title[0], "credential": credential[0]},
        )
        return ParameterValue(name="Google Sheet Id", value=response)
