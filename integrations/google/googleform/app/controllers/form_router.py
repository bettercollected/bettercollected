import asyncio
from http import HTTPStatus
from typing import Any, Dict, Optional

from classy_fastapi import Routable, get, post
from common.models.form_import import FormImportResponse
from fastapi import Depends

from googleform.app.containers import Container
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.app.services.oauth_credential import OauthCredentialService
from googleform.app.services.transformer import GoogleFormTransformerService
from googleform.app.services.user_service import get_user_credential


class GoogleFormRouter(Routable):
    def __init__(
            self,
            *args,
            **kwargs,
    ):
        """This class defines the routes for interacting with the Google forms."""
        # Injecting dependencies
        super().__init__(*args, **kwargs)
        self.executor = Container.executor()
        self.oauth_credential_service: OauthCredentialService = Container.oauth_credential_service()
        self.google_service = Container.google_service()
        self.form_service = Container.form_service()

    @get("", status_code=HTTPStatus.OK)
    async def _get_all_google_forms(
            self, credential: Oauth2CredentialDocument = Depends(get_user_credential)
    ):
        credential = await self.oauth_credential_service.verify_oauth_token(
            credential.email
        )

        task = asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.google_service.get_form_list,
            credential.credentials.dict(),
        )

        forms_list = await task
        return forms_list

    @get("/read_google_sheet")
    async def read_google_sheet(self, google_sheet_id: str,
                                credential: Oauth2CredentialDocument = Depends(get_user_credential)):
        credential = await self.oauth_credential_service.verify_oauth_token(
            credential.email
        )
        read_google_sheet = asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.google_service.read_google_sheet,
            google_sheet_id,
            credential.credentials.dict(),
        )
        response = await read_google_sheet
        return response

    @get("/{form_id}", status_code=HTTPStatus.OK)
    async def _get_single_google_form(
            self,
            form_id: str,
            credential: Oauth2CredentialDocument = Depends(get_user_credential),
    ):
        credential = await self.oauth_credential_service.verify_oauth_token(
            credential.email
        )

        task = asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.google_service.get_form,
            form_id,
            credential.credentials.dict(),
        )
        form = await task
        return form

    @post("/convert/standard_form")
    async def _convert_form(
            self,
            form_import: Dict[str, Any],
            convert_responses: Optional[bool] = True,
            credential: Oauth2CredentialDocument = Depends(get_user_credential),
    ):
        credential = await self.oauth_credential_service.verify_oauth_token(
            credential.email
        )
        transformer = GoogleFormTransformerService()
        standard_form, field_id_and_fields_map = transformer.transform_form(form_import)
        if convert_responses:
            task = asyncio.get_event_loop().run_in_executor(
                self.executor,
                self.google_service.get_form_response_list,
                standard_form.imported_form_id,
                credential.credentials.dict(),
            )
            form_responses = await task
            standard_responses = transformer.transform_form_responses(
                form_responses, field_id_and_fields_map
            )
            return FormImportResponse(form=standard_form, responses=standard_responses)
        return standard_form

    @get("/oauth/verify")
    async def _get_oauth_credentials(self, credential: Oauth2CredentialDocument = Depends(get_user_credential)):
        credential = await self.oauth_credential_service.verify_oauth_token(
            credential.email
        )
        return await self.oauth_credential_service.verify_token_validity(credential=credential)

    @post("/create_google_sheet")
    async def create_google_sheet(self, title: str,
                                  credential: str):
        task = asyncio.get_event_loop().run_in_executor(
            self.executor,
            self.google_service.create_sheet,
            title,
            credential,
        )
        google_sheet_id = await task
        return google_sheet_id


