import json

from auth.app.exceptions import HTTPException
from auth.app.repositories.user_repository import UserRepository
from auth.app.services.base_auth_provider import BaseAuthProvider
from auth.config import settings

from common.configs.crypto import Crypto
from common.models.user import User

from google.auth.exceptions import RefreshError

import google_auth_oauthlib.flow

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from oauthlib.oauth1 import InvalidClientError
from oauthlib.oauth2 import InvalidGrantError

from starlette.requests import Request

crypto: Crypto = Crypto(settings.AUTH_AEX_HEX_KEY)
google_settings = settings.google_settings

client_config = {
    "web": {
        "client_id": google_settings.client_id,
        "project_id": google_settings.project_id,
        "auth_uri": google_settings.auth_uri,
        "token_uri": google_settings.token_uri,
        "auth_provider_x509_cert_url": google_settings.auth_provider_x509_cert_url,
        "client_secret": google_settings.client_secret,
        "redirect_uris": google_settings.redirect_uris.split(","),
        "javascript_origins": google_settings.javascript_origins.split(","),
    }
}


class GoogleAuthProvider(BaseAuthProvider):
    async def get_basic_auth_url(self, client_referer_url: str, *args, **kwargs):
        creator = kwargs.get("creator", False)
        state_json = json.dumps(
            {"client_referer_url": client_referer_url, "creator": creator}
        )
        state = crypto.encrypt(state_json)
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config=client_config,
            scopes="https://www.googleapis.com/auth/userinfo.email profile openid",
        )
        flow.redirect_uri = settings.google_settings.basic_auth_redirect

        authorization_url, state = flow.authorization_url(
            state=state, include_granted_scopes="false"
        )
        return authorization_url

    async def basic_auth_callback(self, code: str, state: str, *args, **kwargs):
        request: Request = kwargs.get("request")
        tmp = str(request.url)
        authorization_response = (
            tmp if tmp[0:5] == "https" else tmp.replace(tmp[0:4], "https", 1)
        )
        state_decrypted = crypto.decrypt(state)
        state_json = json.loads(state_decrypted)
        credentials = self.fetch_basic_token(
            auth_code=authorization_response, state=state
        )
        user = await self.get_google_user(credentials)
        if not user:
            return state_json
        creator = state_json.get("creator", False)
        user_document = await UserRepository.save_user(
            user.get("email"),
            creator=creator,
            first_name=user.get("given_name"),
            last_name=user.get("family_name"),
            profile_image=user.get("picture")
        )
        user = User(
            id=str(user_document.id),
            sub=user_document.email,
            roles=user_document.roles,
            plan=user_document.plan,
        )
        state_json["user"] = user.dict()
        return state_json

    def fetch_basic_token(self, auth_code: str, state):
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            client_config=client_config,
            scopes="https://www.googleapis.com/auth/userinfo.email profile openid",
            state=state,
        )
        flow.redirect_uri = settings.google_settings.basic_auth_redirect
        try:
            flow.fetch_token(authorization_response=auth_code)
        except Exception:
            return None
        credentials = flow.credentials
        return credentials

    async def get_google_user(self, credentials):
        try:
            oauth_service = build(
                serviceName="oauth2", version="v2", credentials=credentials
            )
            return oauth_service.userinfo().get().execute()
        except HttpError as error:
            raise HTTPException(error.status_code, error.error_details)
        except RefreshError:
            raise HTTPException(401, "Google auth token refresh error.")
        except InvalidClientError:
            raise HTTPException(401, "Google auth invalid client error.")
        except AttributeError:
            raise HTTPException(401, "State not found. Connect with google services.")
        except InvalidGrantError:
            raise HTTPException(401, "Invalid Grant error.")
