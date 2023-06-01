from http import HTTPStatus
from typing import Any, Dict, Optional

from classy_fastapi import Routable, get, post

from common.models.form_import import FormImportResponse

from fastapi import Depends

from googleform.app.containers import Container
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.app.services.transformer import GoogleFormTransformerService
from googleform.app.services.user_service import get_user_credential


class GoogleFormRouter(Routable):
    def __init__(self, *args, **kwargs):
        """This class defines the routes for interacting with the Google forms."""
        # Injecting dependencies
        super().__init__(*args, **kwargs)
        self.oauth_credential_service = Container.oauth_credential_service()
        self.google_service = Container.google_service()
        self.form_service = Container.form_service()

    @get("", status_code=HTTPStatus.OK)
    async def _get_all_google_forms(
        self, credential: Oauth2CredentialDocument = Depends(get_user_credential)
    ):
        credential = await self.oauth_credential_service.verify_oauth_token(
            credential.email
        )
        return self.google_service.get_form_list(credential.credentials.dict())

    @get("/{form_id}", status_code=HTTPStatus.OK)
    async def _get_single_google_form(
        self,
        form_id: str,
        credential: Oauth2CredentialDocument = Depends(get_user_credential),
    ):
        credential = await self.oauth_credential_service.verify_oauth_token(
            credential.email
        )
        return self.google_service.get_form(form_id, credential.credentials.dict())

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
        standard_form = transformer.transform_form(form_import)
        if convert_responses:
            form_responses = self.google_service.get_form_response_list(
                standard_form.form_id, credential.credentials.dict()
            )
            standard_responses = transformer.transform_form_responses(form_responses)
            return FormImportResponse(form=standard_form, responses=standard_responses)
        return standard_form
