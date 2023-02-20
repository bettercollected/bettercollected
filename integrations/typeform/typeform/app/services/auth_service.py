from typing import Dict, Any, Optional

import jwt
import requests
from fastapi import HTTPException

from common.configs.crypto import Crypto
from common.enums.form_provider import FormProvider
from common.models.user import Token, UserInfo, OAuthState
from typeform.app.container import AppContainer, container
from typeform.config import settings

crypto = Crypto(settings.AES_HEX_KEY)


async def get_oauth_url(*, oauth_state: OAuthState) -> str:
    state = crypto.encrypt(oauth_state.json())
    oauth_url = settings.TYPEFORM_AUTH_URI.format(
        state=state,
        client_id=settings.TYPEFORM_CLIENT_ID,
        redirect_uri=settings.TYPEFORM_REDIRECT_URI,
        scope=settings.TYPEFORM_SCOPE,
    )
    return oauth_url


async def handle_oauth_callback(code: str, *, state: str):
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
    user_info = UserInfo(**token.dict(), email=email, provider=FormProvider.TYPEFORM)
    oauth_state = OAuthState.parse_raw(crypto.decrypt(state))

    token = jwt.encode(
        {
            "user_info": user_info.dict(),
            "oauth_state": oauth_state.dict(),
        },
        settings.JWT_SECRET,
    )

    await container.http_client.get(
        oauth_state.auth_server_redirect_uri, params={"jwt_token": token}
    )


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
