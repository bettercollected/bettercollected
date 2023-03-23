import json
from datetime import datetime, timedelta
from http import HTTPStatus
from urllib import parse

import google_auth_oauthlib.flow
import requests
from fastapi import HTTPException
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from loguru import logger
from oauthlib.oauth1 import InvalidClientError
from oauthlib.oauth2 import InvalidGrantError
from starlette.requests import Request

from common.configs.crypto import Crypto
from common.constants import (
    GOOGLE_DATETIME_FORMAT,
    MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
    MESSAGE_OAUTH_INVALID_CLIENT,
    MESSAGE_OAUTH_INVALID_GRANT,
    MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY,
)
from common.models.user import UserInfo
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.app.utils.google import dict_to_credential
from googleform.config import settings

_crypto = Crypto(settings.GOOGLE_AES_KEY)


class OauthGoogleService:
    """
    Class for interacting with the Google OAuth2 API.

    This class provides a convenient way to access the Google OAuth2
    API and perform various operations on it.
    """

    def __init__(self, oauth_credential_repo: OauthCredentialRepository):
        """
        Initialize the OAuth2 Google service.

        Args:
            oauth_credential_repo (OauthCredentialRepository): An instance
                of the OAuth2 credential repository.
        """
        self.oauth_credential_repo: OauthCredentialRepository = oauth_credential_repo

        self.client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "project_id": settings.GOOGLE_PROJECT_ID,
                "auth_uri": settings.GOOGLE_AUTH_URI,
                "token_uri": settings.GOOGLE_TOKEN_URI,
                "auth_provider_x509_cert_url": settings.GOOGLE_AUTH_PROVIDER_X509_CERT_URL,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uris": settings.GOOGLE_REDIRECT_URIS.split(","),
                "javascript_origins": settings.GOOGLE_JAVASCRIPT_ORIGINS.split(","),
            }
        }

    def authorize(self, state: str):
        """
        Authorize the user and obtain an authorization URL.

        Args:
            state (str): Encrypted state of user info with email.

        Returns:
            authorization_url (str): The authorization URL.

        Raises:
            HTTPException: If there is an error during the authorization process.
        """
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config=self.client_config,
                scopes=settings.GOOGLE_SCOPES,
            )

            flow.redirect_uri = settings.GOOGLE_REDIRECT_URIS

            logger.warning(state)

            authorization_url, state = flow.authorization_url(
                access_type="offline",
                state=state,
                include_granted_scopes="true",
                prompt="consent",
            )

            logger.warning(state)

            return authorization_url, state
        except InvalidGrantError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_INVALID_GRANT,
            )
        except HttpError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.error_details
            )
        except RefreshError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )
        except InvalidClientError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_INVALID_CLIENT,
            )
        except Exception as error:
            logger.error(error)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )

    async def oauth2callback(self, request: Request):
        """
        Process the OAuth 2.0 callback and fetch the access token.

        Args:
            request (Request): The request object of the OAuth 2.0 callback.

        Returns:
            user_info: Returns user info with email.

        Raises:
            HTTPException: If there is an error during the authorization process.
        """
        try:
            tmp = str(request.url)
            authorization_response = (
                tmp if tmp[0:5] == "https" else tmp.replace(tmp[0:4], "https", 1)
            )
            state = dict(
                parse.parse_qsl(parse.urlparse(authorization_response).query)
            ).get("state", "")
            credentials = self.fetch_token(
                auth_code=authorization_response, state=state
            )
            json_credentials = credentials.to_json()
            state_json = dict(json.loads(_crypto.decrypt(state)))
            user = await self.get_google_user(credentials)
            email = user.get("email")
            if user.get("email") == state_json.get("email"):
                db_credentials = await self.oauth_credential_repo.get(email)
                if db_credentials:
                    db_credentials.updated_at = datetime.now()
                    db_credentials.credentials = json.loads(json_credentials)
                    await self.oauth_credential_repo.update(email, db_credentials)
                else:
                    await self.oauth_credential_repo.add(
                        email, json.loads(json_credentials)
                    )
            user_info = UserInfo(email=email)
            return user_info
        except InvalidGrantError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_INVALID_GRANT,
            )
        except HttpError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.error_details
            )
        except RefreshError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )
        except InvalidClientError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_INVALID_CLIENT,
            )
        except Exception as error:
            logger.error(error)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )

    def fetch_token(self, auth_code: str, state: str):
        """
        Fetch the OAuth 2.0 access token. Used in oauth2callback.

        Args:
            auth_code (str): The authorization code returned by the authorization server.
            state (str): The encrypted state returned by the authorization server.

        Returns:
            google.oauth2.credentials.Credentials: The OAuth 2.0 credentials.

        Raises:
            HTTPException: If there is an error during the authorization process.
        """
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config=self.client_config,
                scopes=settings.GOOGLE_SCOPES,
                state=state,
            )
            flow.redirect_uri = settings.GOOGLE_REDIRECT_URIS
            flow.fetch_token(authorization_response=auth_code)
            credentials = flow.credentials
            return credentials
        except InvalidGrantError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_INVALID_GRANT,
            )
        except HttpError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.error_details
            )
        except RefreshError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )
        except InvalidClientError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_INVALID_CLIENT,
            )
        except Exception as error:
            logger.error(error)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )

    async def fetch_oauth_token(self, oauth_credential: Oauth2CredentialDocument):
        """
        Fetch an OAuth2 token for a given credential document.

        If the token has expired or is about to expire, it will be refreshed.
        Otherwise, the existing token will be returned.

        Args:
            oauth_credential (Oauth2CredentialDocument): The OAuth2 credential
                document to fetch the token for.

        Returns:
            Oauth2CredentialDocument: The OAuth2 credential document with a
                valid access token.

        Raises:
            HTTPException: If there is an error fetching the token, or if the
                token is missing or has expired.
        """
        try:
            credentials = dict_to_credential(oauth_credential.credentials.dict())
            expiry_datetime = credentials.expiry
            current_date = datetime.now()
            current_date = current_date.strftime(GOOGLE_DATETIME_FORMAT)
            current_date = datetime.strptime(current_date, GOOGLE_DATETIME_FORMAT)
            if expiry_datetime < current_date:
                data = {
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "refresh_token": credentials.refresh_token,
                    "grant_type": "refresh_token",
                }
                token = requests.post(credentials.token_uri, data).json()
                if token.get("error"):
                    raise InvalidGrantError()
                if not token.get("access_token") or not token.get("expires_in"):
                    raise HttpError()
                oauth_credential.credentials.token = token.get("access_token")
                expiry = current_date + timedelta(seconds=token.get("expires_in"))
                oauth_credential.credentials.expiry = expiry.strftime(
                    GOOGLE_DATETIME_FORMAT
                )
                oauth_credential.updated_at = current_date
                return await self.oauth_credential_repo.update(
                    oauth_credential.email, oauth_credential
                )
            return oauth_credential
        except HttpError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                detail=MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY,
            )
        except InvalidGrantError:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, detail=MESSAGE_OAUTH_INVALID_GRANT
            )
        except Exception as error:
            logger.error(error)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )

    @staticmethod
    async def revoke(credentials: Oauth2CredentialDocument):
        """
        Static method that revokes a set of OAuth2 credentials.

        Args:
        credentials (Oauth2CredentialDocument) : The set of OAuth2 credentials to be revoked.

        Returns:
        bool : True if the credentials were successfully revoked, False otherwise.
        """
        cred = dict_to_credential(credentials.credentials.dict())
        revoke = requests.post(
            url=settings.GOOGLE_REVOKE_CREDENTIALS_URL,
            params={"token": cred.token},
            headers={"content-type": "application/x-www-vendors-urlencoded"},
        )
        # flake8: noqa
        status_code = getattr(revoke, "status_code")
        credentials_revoked = status_code == 200
        if credentials_revoked:
            await credentials.delete()
        return credentials_revoked

    async def get_google_user(self, credentials):
        try:
            oauth_service = build(
                serviceName="oauth2", version="v2", credentials=credentials
            )
            return oauth_service.userinfo().get().execute()
        except HttpError as error:
            raise HTTPException(
                status_code=error.status_code, detail=error.error_details
            )
        except RefreshError:
            raise HTTPException(
                status_code=401, detail="Google auth token refresh error."
            )
        except InvalidClientError as error:
            raise HTTPException(
                status_code=401, detail="Google auth invalid client error."
            )
        except AttributeError:
            raise HTTPException(
                status_code=401, detail="State not found. Connect with google services."
            )
        except InvalidGrantError:
            raise HTTPException(401, "Invalid Grant error.")
