import datetime
from http import HTTPStatus
from typing import Any, Dict, List

import requests
from fastapi import HTTPException

from common.constants import MESSAGE_UNAUTHORIZED
from common.models.form_import import FormImportResponse
from common.models.user import Credential, Token
from typeform.app.exceptions import HTTPException
from typeform.app.services.transformer_service import TypeFormTransformerService
from typeform.config import settings


def refresh_typeform_token(refresh_token) -> Token:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.TYPEFORM_CLIENT_ID,
        "client_secret": settings.TYPEFORM_CLIENT_SECRET,
        "scope": settings.TYPEFORM_SCOPE.replace("+", " "),
    }
    typeform_response = requests.post(settings.TYPEFORM_TOKEN_URI, data=data)
    if typeform_response.status_code > 299 or typeform_response.status_code < 200:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, content=MESSAGE_UNAUTHORIZED)
    typeform_token = Token(**typeform_response.json())
    return typeform_token


def perform_typeform_request(
    access_token: str, path: str, params: Dict[str, Any] = None
) -> Dict[str, Any]:
    api_response = requests.get(
        f"{settings.TYPEFORM_API_URI}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    if api_response.status_code != 200:
        raise HTTPException(
            status_code=400, detail="Error while fetching forms from typeform."
        )
    return api_response.json()


async def get_form_responses(access_token, form_id) -> List[Dict[str, Any]]:
    page_size = 1000
    typeform_responses = get_all_data_without_pagination(
        page_size, access_token, f"/forms/{form_id}/responses"
    )
    return typeform_responses


def get_all_data_without_pagination(
    page_size, access_token, path
) -> List[Dict[str, Any]]:
    page = 1
    all_data = []
    while True:
        response = perform_typeform_request(
            access_token, path, {"page": page, "page_size": page_size}
        )
        all_data.extend(response["items"])
        if page * page_size >= response["total_items"]:
            break
        else:
            page = page + 1
    return all_data


def get_latest_token(credential: Credential):
    expiration_time = credential.updated_at + datetime.timedelta(
        seconds=credential.access_token_expires
    )
    current_time = datetime.datetime.now()

    token = Token(
        access_token=credential.access_token, refresh_token=credential.refresh_token
    )
    # If the token is expired then refresh the token if the refresh
    # token itself is expired then it throws error
    if current_time > expiration_time:
        token = refresh_typeform_token(credential.refresh_token)

    return token.access_token


async def get_forms(credential: Credential):
    access_token = get_latest_token(credential)
    page_size = 200
    all_forms = get_all_data_without_pagination(page_size, access_token, "/forms")
    return all_forms


async def get_single_form(form_id: str, credential: Credential):
    access_token = get_latest_token(credential)
    form = perform_typeform_request(access_token, f"/forms/{form_id}")
    return form


async def convert_form(
    form_import: Dict[str, Any], convert_responses: bool, credential: Credential
):
    access_token = get_latest_token(credential)
    transformer = TypeFormTransformerService()
    standard_form = transformer.transform_form(form_import)
    if convert_responses:
        form_responses = await get_form_responses(access_token, standard_form.form_id)
        standard_responses = transformer.transform_form_responses(form_responses)
        return FormImportResponse(form=standard_form, responses=standard_responses)
    else:
        return standard_form
