import datetime
from typing import Dict, Any, List

import requests
from common.models.user import User, Credential, Token
from fastapi import HTTPException

from typeform.config import settings


async def import_forms(credential: Credential):
    access_token = get_latest_token(credential)
    page_size = 200
    all_forms = get_all_data_without_pagination(page_size, access_token, "/forms")
    return all_forms


def refresh_typeform_token(refresh_token) -> Token:
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': settings.TYPEFORM_CLIENT_ID,
        'client_secret': settings.TYPEFORM_CLIENT_SECRET,
        'scope': settings.TYPEFORM_SCOPE.replace("+", " ")
    }
    typeform_response = requests.post(settings.TYPEFORM_TOKEN_URI, data=data)
    typeform_token = Token(**typeform_response.json())
    return typeform_token


def perform_typeform_request(access_token: str, path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    api_response = requests.get(f'{settings.TYPEFORM_API_URI}{path}',
                                headers={
                                    'Authorization': f'Bearer {access_token}'
                                },
                                params=params)
    if api_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error while fetching forms from typeform.")
    return api_response.json()


# async def save_typeform(email: str,
#                         request_form: Dict[str, Any],
#                         response_data_owner: str):
#     form = TypeFormDocument(info=request_form, formId=request_form['id'])
#     existing_form = await TypeFormDocument.find_one(TypeFormDocument.formId == form.formId)
#     if existing_form:
#         existing_form.info = request_form
#         form = existing_form
#     form.dataOwnerFields.append(response_data_owner)
#     form.dataOwnerFields = list(set(form.dataOwnerFields))
#     await form.save()
#
#     form_responses = await get_form_responses(email, form.formId)
#     for response in form_responses:
#         answers = response['answers']
#         if not response_data_owner:
#             data_owner_answer = ""
#         else:
#             data_owner_answer_field = list(filter(lambda x: x['field']['id'] == response_data_owner, answers))[0]
#             data_owner_answer = data_owner_answer_field[data_owner_answer_field['type']]
#         response_id = response['response_id']
#         document = await TypeFormResponseDocument.find_one({'responseId': response_id})
#         if document:
#             document.response_data = response
#             document.dataOwnerIdentifier = data_owner_answer
#         else:
#             document = TypeFormResponseDocument(
#                 responseId=response_id,
#                 formId=form.formId,
#                 response_data=response,
#                 dataOwnerIdentifier=data_owner_answer
#             )
#         await document.save()


# async def get_form_responses(email, form_id) -> List[Dict[str, Any]]:
#     access_token = await get_access_token(email)
#     page_size = 1000
#     typeform_responses = get_all_data_without_pagination(page_size,
#                                                          access_token,
#                                                          f"/forms/{form_id}/responses")
#     return typeform_responses

def get_all_data_without_pagination(page_size, access_token, path) -> List[Dict[str, Any]]:
    page = 1
    all_data = []
    while True:
        response = perform_typeform_request(access_token,
                                            path,
                                            {'page': page, 'page_size': page_size})
        all_data.extend(response['items'])
        if page * page_size >= response['total_items']:
            break
        else:
            page = page + 1
    return all_data


def get_latest_token(credential: Credential):
    expiration_time = credential.updated_at + datetime.timedelta(seconds=credential.access_token_expires)
    current_time = datetime.datetime.now()

    token = Token(access_token=credential.access_token, refresh_token=credential.refresh_token)
    # If the token is expired then refresh the token if the refresh token itself is expired then it throws error
    if current_time > expiration_time:
        token = refresh_typeform_token(credential.refresh_token)

    return token.access_token


async def import_single_form(form_id: str, credential: Credential):
    access_token = get_latest_token(credential)
    form = perform_typeform_request(access_token, f"/forms/{form_id}")
    return form
