from auth.app.services.base_auth_provider import BaseAuthProvider
from auth.config import settings
from common.configs.crypto import Crypto
import json

crypto = Crypto(settings.AEX_HEX_KEY)

typeform_settings = settings.typeform_settings


class TypeformAuthProvider(BaseAuthProvider):
    async def get_basic_auth_url(self, client_referer_url: str) -> str:
        state_json = json.dumps({"client_referer_url": client_referer_url})
        state = crypto.encrypt(state_json)
        authorization_url = typeform_settings.auth_uri.format(
            state=state,
            client_id=typeform_settings.client_id,
            redirect_uri=typeform_settings.redirect_uri,
            scope=typeform_settings.scope
        )
        return authorization_url

    async def basic_auth_callback(self, code: str, *args, **kwargs) -> (bool, str):
        pass
