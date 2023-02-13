from typing import Optional

from starlette.requests import Request
from starlette.responses import RedirectResponse

from common.base.plugin import BasePluginRoute
from common.enums.form_provider import FormProvider
from common.models.form_scheduler_config import AddNewFormImportJobRequest
from dependencies import Container


class GoogleRouter(BasePluginRoute):
    def __init__(self):
        """
        This class defines the routes for interacting with the Google forms.
        """

        # Injecting dependencies
        self.oauth_credential_service = Container.oauth_credential_service()
        self.oauth_google_service = Container.oauth_google_service()
        self.google_service = Container.google_service()
        self.form_service = Container.form_service()
        self.form_response_service = Container.form_response_service()
        self.fsc_service = Container.fsc_service()

    async def authorize(self, email: str, request: Request):
        client_referer_url = request.headers.get("referer")
        authorization_url, state = self.oauth_google_service.authorize(
            email, client_referer_url
        )
        return RedirectResponse(authorization_url)

    async def callback(self, request: Request):
        url = str(request.url)
        (
            json_credentials,
            client_referer_url,
        ) = await self.oauth_google_service.oauth2callback(url)
        if client_referer_url is not None:
            return RedirectResponse(client_referer_url)
        return json_credentials

    async def revoke(self, email: str):
        credential = await self.oauth_credential_service.verify_oauth_token(email)
        return await self.oauth_google_service.revoke(credential)

    async def list_forms(self, email: str):
        credential = await self.oauth_credential_service.verify_oauth_token(email)
        return self.google_service.get_form_list(credential.credentials)

    async def get_form(self, form_id: str, email: str):
        credential = await self.oauth_credential_service.verify_oauth_token(email)
        return self.google_service.get_form(form_id, credential.credentials)

    async def import_form(
        self, form_id: str, email: str, data_owner_field: Optional[str] = None
    ):
        credential = await self.oauth_credential_service.verify_oauth_token(email)
        form = self.google_service.get_form(form_id, credential.credentials)
        form_responses = self.google_service.get_form_response_list(
            form_id, credential.credentials
        ).get("responses", [])
        if form:
            await self.form_service.update_form(form_id, form, data_owner_field)
        if form_responses:
            for form_response in form_responses:
                await self.form_response_service.update_submission(
                    form_id,
                    form_response.get("responseId"),
                    form_response,
                    data_owner_field,
                )

        await self.fsc_service.add_new_form_import_job(
            AddNewFormImportJobRequest(
                email=[email],
                provider=FormProvider.GOOGLE,
                formId=form_id,
            )
        )  # Adding the form import in scheduler job

        return form
