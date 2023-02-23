import json

import google_auth_oauthlib.flow
from auth.app.services.base_auth_provider import BaseAuthProvider
from auth.config import settings
from common.configs.crypto import Crypto

crypto: Crypto = Crypto(settings.AEX_HEX_KEY)
google_settings = settings.google_settings

client_config = {
    "web": {
        "client_id": google_settings.client_id,
        "project_id": google_settings.project_id,
        "auth_uri": google_settings.auth_uri,
        "token_uri": google_settings.token_uri,
        "auth_provider_x509_cert_url": google_settings.auth_provider_x509_cert_url,
        "client_secret": google_settings.client_secret,
        "redirect_uris": google_settings.redirect_uris.split(','),
        "javascript_origins": google_settings.javascript_origins.split(',')
    }
}


class GoogleAuthProvider(BaseAuthProvider):

    async def get_basic_auth_url(self, client_referer_url: str):
        state_json = json.dumps({"client_referer_url": client_referer_url})
        state = crypto.encrypt(state_json)
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config=client_config,
            scopes="https://www.googleapis.com/auth/userinfo.email openid"
        )
        flow.redirect_uri = settings.google_settings.basic_auth_redirect

        authorization_url, state = flow.authorization_url(
            state=state,
            include_granted_scopes='false'
        )
        return authorization_url

    async def basic_auth_callback(self, code: str, *args, **kwargs):
        pass
