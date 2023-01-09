import json
from datetime import datetime, timedelta
from http import HTTPStatus
from urllib import parse

import google_auth_oauthlib.flow
import requests
from fastapi import HTTPException
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from loguru import logger
from oauthlib.oauth1 import InvalidClientError
from oauthlib.oauth2 import InvalidGrantError

from common.configs.crypto import Crypto
from common.constants import (
    GOOGLE_DATETIME_FORMAT,
    MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
    MESSAGE_OAUTH_INVALID_CLIENT,
    MESSAGE_OAUTH_INVALID_GRANT,
    MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY,
)
from repositories.oauth_credential import OauthCredentialRepository
from common.schemas.oauth_credential import Oauth2CredentialDocument
from settings import settings
from utils.google import dict_to_credential

_crypto = Crypto(settings.google_settings.aes_key)


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
                "client_id": settings.google_settings.client_id,
                "project_id": settings.google_settings.project_id,
                "auth_uri": settings.google_settings.auth_uri,
                "token_uri": settings.google_settings.token_uri,
                "auth_provider_x509_cert_url": settings.google_settings.auth_provider_x509_cert_url,
                "client_secret": settings.google_settings.client_secret,
                "redirect_uris": settings.google_settings.redirect_uris.split(","),
                "javascript_origins": settings.google_settings.javascript_origins.split(
                    ","
                ),
            }
        }

    def authorize(self, email: str, client_referer_url: str):
        """
        Authorize the user and obtain an authorization URL.

        Args:
            email (str): The email address of the user.
            client_referer_url (str): The URL of the client page where
                the authorization request originated.

        Returns:
            (authorization_url, state): A tuple containing
                - str: The authorization URL.
                - str: An encrypted state containing the email address and client referer URL.

        Raises:
            HTTPException: If there is an error during the authorization process.
        """
        try:
            state_json = json.dumps(
                {
                    "email_address": email,
                    "client_referer_url": client_referer_url,
                }
            )
            state = _crypto.encrypt(state_json)
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config=self.client_config,
                scopes=settings.google_settings.scopes,
            )

            flow.redirect_uri = settings.google_settings.redirect_uris

            authorization_url, state = flow.authorization_url(
                access_type="offline", state=state, include_granted_scopes="true"
            )

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

    async def oauth2callback(self, url: str):
        """
        Process the OAuth 2.0 callback and fetch the access token.

        Args:
            url (str): The URL of the OAuth 2.0 callback.

        Returns:
            (json_credentials, client_referer_url): A tuple containing
                - str: The JSON representation of the OAuth 2.0 credentials.
                - str: The client referer URL.

        Raises:
            HTTPException: If there is an error during the authorization process.
        """
        try:
            state = dict(parse.parse_qsl(parse.urlparse(url).query)).get("state", "")
            credentials = self.fetch_token(auth_code=url, state=state)
            json_credentials = credentials.to_json()
            state_json = dict(json.loads(_crypto.decrypt(state)))
            client_referer_url = state_json.get("client_referer_url")
            # TODO: use email to save credentials
            # email = state_json.get('email_address')
            # await google_repository.save_credentials(email=email, credentials=json_credentials, state=str(state))
            return json_credentials, client_referer_url
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
                scopes=settings.google_settings.scopes,
                state=state,
            )
            flow.redirect_uri = settings.google_settings.redirect_uris
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
            credentials = dict_to_credential(oauth_credential.credentials)
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
                if not token.get("access_token") or not token.get("expires_in"):
                    raise HttpError()
                oauth_credential.credentials["token"] = token.get("access_token")
                expiry = current_date + timedelta(seconds=token.get("expires_in"))
                oauth_credential.credentials["expiry"] = expiry.strftime(
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
        except Exception as error:
            logger.error(error)
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )
