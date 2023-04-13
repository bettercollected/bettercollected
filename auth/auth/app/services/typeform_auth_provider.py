import json
from http import HTTPStatus
from typing import Any, Dict

from auth.app.exceptions import HTTPException
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.base_auth_provider import BaseAuthProvider
from auth.config import settings

from common.configs.crypto import Crypto
from common.models.user import User

import requests

crypto = Crypto(settings.AUTH_AEX_HEX_KEY)

typeform_settings = settings.typeform_settings


class TypeformAuthProvider(BaseAuthProvider):
    async def get_basic_auth_url(self, client_referer_url: str, *args, **kwargs) -> str:
        state_json = json.dumps({"client_referer_url": client_referer_url})
        state = crypto.encrypt(state_json)
        authorization_url = typeform_settings.auth_uri.format(
            state=state,
            client_id=typeform_settings.client_id,
            redirect_uri=typeform_settings.redirect_uri,
            scope=typeform_settings.scope,
        )
        return authorization_url

    async def basic_auth_callback(
        self, code: str, state: str, *args, **kwargs
    ) -> (bool, str):
        state_decrypted = crypto.decrypt(state)
        state_json = json.loads(state_decrypted)
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": typeform_settings.client_id,
            "client_secret": typeform_settings.client_secret,
            "redirect_uri": typeform_settings.redirect_uri,
        }
        typeform_response = requests.post(typeform_settings.token_uri, data=data)
        if state is not None:
            state = json.loads(crypto.decrypt(state))

        token_response = typeform_response.json()
        if (
            not token_response
            or typeform_response.status_code != 200
            or not state
            or not code
        ):
            return state_json

        user_response = TypeformAuthProvider.perform_typeform_request(
            token_response.get("access_token"), "/me"
        )
        if not user_response:
            return state_json
        name: str = user_response.get("alias").split()
        user_document = await UserRepository.save_user(
            user_response.get("email"), first_name=name[0], last_name=name[-1]
        )
        user = User(
            id=str(user_document.id),
            sub=user_document.email,
            roles=user_document.roles,
            plan=user_document.plan,
        )
        state_json["user"] = user.dict()
        return state_json

    @staticmethod
    def perform_typeform_request(
        access_token: str, path: str, params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        api_response = requests.get(
            f"{typeform_settings.api_uri}{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        if api_response.status_code != 200:
            raise HTTPException(
                HTTPStatus.BAD_REQUEST, "Error while fetching forms from typeform."
            )
        return api_response.json()
