import logging
from typing import Any, Dict

from common.models.user import Token, UserInfo

from fastapi import HTTPException

import requests

from typeform.app.repositories.credentials_repository import CredentialRepository
from typeform.config import settings


async def get_oauth_url(state: str) -> str:
    oauth_url = settings.TYPEFORM_AUTH_URI.format(
        state=state,
        client_id=settings.TYPEFORM_CLIENT_ID,
        redirect_uri=settings.TYPEFORM_REDIRECT_URI,
        scope=settings.TYPEFORM_SCOPE,
    )
    return oauth_url


async def handle_oauth_callback(code: str) -> UserInfo:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.TYPEFORM_CLIENT_ID,
        "client_secret": settings.TYPEFORM_CLIENT_SECRET,
        # Here type form uses this redirect uri just to verify
        # that it is register in this application
        "redirect_uri": settings.TYPEFORM_REDIRECT_URI,
    }
    typeform_response = requests.post(settings.TYPEFORM_TOKEN_URI, data=data)
    if not typeform_response.json():
        raise HTTPException(500, "Could not fetch token from typeform!")
    token = Token(**typeform_response.json())
    me_response = perform_typeform_request(token.access_token, "/me")
    email = me_response["email"]
    name = me_response.get("alias").split()
    user_info = UserInfo(email=email, first_name=name[0], last_name=name[-1])
    await CredentialRepository.save_credentials(user_info, token)
    return user_info


def perform_typeform_request(
        access_token: str, path: str, params: Dict[str, Any] = None
) -> Dict[str, Any]:
    api_response = requests.get(
        f"{settings.TYPEFORM_API_URI}{path}",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    if api_response.status_code != 200:
        logging.error(api_response.url)
        logging.error(api_response.status_code)
        logging.error(api_response.content)
        raise HTTPException(
            status_code=400, detail="Error while performing typeform request."
        )
    return api_response.json()
