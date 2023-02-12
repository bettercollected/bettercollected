import datetime
import json
from typing import Tuple, Dict, Any, List

import requests
from common.models.dtos.auth import User
from common.models.schemas.credentials import Provider
from common.models.schemas.form_responses import TypeFormResponseDocument
from common.models.schemas.forms import TypeFormDocument
from common.models.schemas.user import Roles, UserDocument
from common.models.schemas.workspace import WorkspaceDocument
from common.models.schemas.workspace_users import WorkspaceUsers
from common.repositories import credentials_repository
from typeform.config import settings
from fastapi import HTTPException
from pydantic import BaseModel
from common.configs import crypto

typeform_settings = settings.typeform_settings

crypto = crypto.Crypto(settings.AES_HEX_KEY)


class TypeformTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


async def typeform_auth(client_referer_url: str) -> str:
    state_json = json.dumps({"client_referer_url": client_referer_url})
    state = crypto.encrypt(state_json)
    authorization_url = typeform_settings.auth_uri.format(
        state=state,
        client_id=typeform_settings.client_id,
        redirect_uri=typeform_settings.redirect_uri,
        scope=typeform_settings.scope
    )
    return authorization_url


async def typeform_callback(code: str, state: str) -> Tuple[UserDocument, str]:
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': typeform_settings.client_id,
        'client_secret': typeform_settings.client_secret,
        'redirect_uri': typeform_settings.redirect_uri
    }
    typeform_response = requests.post(typeform_settings.token_uri, data=data)
    if not typeform_response.json():
        raise HTTPException(500, "Could not fetch token from typeform!")
    token_response = TypeformTokenResponse(**typeform_response.json())
    me_response = perform_typeform_request(token_response.access_token, "/me")
    await credentials_repository.save_credentials(email=me_response['email'],
                                                  credentials=token_response.dict(),
                                                  state=state,
                                                  provider=Provider.TYPEFORM)
    # TODO Refactor this
    user_document = await save_user_with_workspace(me_response['email'])
    state = json.loads(crypto.decrypt(state))
    client_referer_url = state.get('client_referer_url', '')
    return user_document, client_referer_url


def perform_typeform_request(access_token: str, path: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
    api_response = requests.get(f'{typeform_settings.api_uri}{path}',
                                headers={
                                    'Authorization': f'Bearer {access_token}'
                                },
                                params=params)
    if api_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Error while fetching forms from typeform.")
    return api_response.json()
