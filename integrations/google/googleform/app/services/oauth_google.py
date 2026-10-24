import base64
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timedelta
from http import HTTPStatus
from urllib import parse

import google_auth_oauthlib.flow
from common.configs.crypto import Crypto
from common.constants import (
    GOOGLE_DATETIME_FORMAT,
    MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
    MESSAGE_OAUTH_INVALID_CLIENT,
    MESSAGE_OAUTH_INVALID_GRANT,
    MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY,
)
from common.models.user import UserInfo
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from cryptography.fernet import InvalidToken
from oauthlib.oauth2 import InvalidClientError, InvalidGrantError, OAuth2Error
from pydantic import EmailStr
from starlette.requests import Request

from googleform.app.exceptions import HTTPException
from googleform.app.models.oauth_credential import GoogleCredentialResponse
from googleform.app.repositories.oauth_credential import OauthCredentialRepository
from googleform.app.schemas.oauth_credential import Oauth2CredentialDocument
from googleform.app.utils import AiohttpClient
from googleform.app.utils.google import dict_to_credential
from googleform.config import settings

log = logging.getLogger(__name__)

_crypto = Crypto(settings.AUTH_AES_HEX_KEY)

# oauthlib refuses a token whose scopes differ from the requested ones ("Scope
# has changed") unless OAUTHLIB_RELAX_TOKEN_SCOPE is set in the process
# environment; the settings store cannot supply it. Google always answers with
# a different set (the email/profile aliases, scopes granted earlier through
# include_granted_scopes), so the relaxed mode is set here and the scopes this
# service needs are checked explicitly after the exchange
# (_refuse_missing_scopes).
if not os.environ.get("OAUTHLIB_RELAX_TOKEN_SCOPE"):
    os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

_SCOPE_PREFIX = "https://www.googleapis.com/auth/"
# Short names Google may return for the scopes requested as full URLs.
_SCOPE_ALIASES = {
    "email": _SCOPE_PREFIX + "userinfo.email",
    "profile": _SCOPE_PREFIX + "userinfo.profile",
}
# What the Google Forms import cannot work without: reading the form, its
# responses, and the account's email (the credential is stored under it).
REQUIRED_FORMS_SCOPES = (
    _SCOPE_PREFIX + "forms.body.readonly",
    _SCOPE_PREFIX + "forms.responses.readonly",
    _SCOPE_PREFIX + "userinfo.email",
)
MESSAGE_OAUTH_SCOPES_NOT_GRANTED = (
    "Google did not grant access to your forms. Connect again and allow "
    "access to your Google Forms and their responses."
)
MESSAGE_OAUTH_INVALID_STATE = "The authorization request is invalid or has expired."


def pkce_code_verifier(state: str) -> str:
    """The PKCE code verifier of the authorization request carrying ``state``.

    google-auth-oauthlib (1.3+) sends a PKCE challenge with every authorization
    URL, and the token exchange must present the matching verifier. The two
    steps run in different requests (and possibly different replicas), so the
    verifier is derived from the request's state with a server-side key instead
    of being kept anywhere: the same state gives the same verifier, and without
    the key an intercepted code and state are not enough to exchange the code.
    43 characters from the unreserved set (RFC 7636 section 4.1).
    """
    digest = hmac.new(
        settings.AUTH_AES_HEX_KEY.encode(),
        b"google-oauth-pkce-v1|" + state.encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def granted_scopes(token: dict, requested) -> set:
    """The scopes Google granted, aliases expanded. A token response without
    ``scope`` grants what was requested (RFC 6749 section 5.1)."""
    scope = token.get("scope") if token else None
    if scope is None:
        scope = requested
    if isinstance(scope, str):
        scope = scope.split()
    return {_SCOPE_ALIASES.get(s, s) for s in scope or ()}


def _refuse_missing_scopes(granted: set, required) -> None:
    missing = [s for s in required if s not in granted]
    if missing:
        log.warning(
            "google token exchange: required scopes not granted (%s)",
            ", ".join(s.removeprefix(_SCOPE_PREFIX) for s in missing),
        )
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_OAUTH_SCOPES_NOT_GRANTED
        )


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

    def authorize(self, state: str, is_integration: bool = False):
        """
        Authorize the user and obtain an authorization URL.

        Args:
            state (str): Encrypted state of user info with email.
            is_integration (bool): To change the scope and redirect uri if it is google_sheet_integration

        Returns:
            authorization_url (str): The authorization URL.

        Raises:
            HTTPException: If there is an error during the authorization process.
        """
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config=self.client_config,
                scopes=(
                    settings.GOOGLE_SHEET_SCOPE
                    if is_integration
                    else settings.GOOGLE_SCOPES
                ),
                code_verifier=pkce_code_verifier(state),
                autogenerate_code_verifier=False,
            )

            flow.redirect_uri = (
                settings.GOOGLE_SHEET_REDIRECT_URL
                if is_integration
                else settings.GOOGLE_REDIRECT_URIS
            )
            authorization_url, state = flow.authorization_url(
                access_type="offline",
                state=state,
                include_granted_scopes="true",
                prompt="select_account consent",
            )
            return authorization_url, state
        except InvalidGrantError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_INVALID_GRANT,
            )
        except HttpError as error:
            raise HTTPException(
                status_code=error.status_code, content=error.error_details
            )
        except RefreshError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )
        except InvalidClientError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_INVALID_CLIENT,
            )

    async def oauth2callback(self, request: Request, user_id: str):
        """
        Process the OAuth 2.0 callback and fetch the access token.

        Args:
            request (Request): The request object of the OAuth 2.0 callback.
            user_id (str): The user_id of user to get credential for


        Returns:
            user_info: Returns user info with email.

        Raises:
            HTTPException: If there is an error during the authorization process.
        """
        tmp = str(request.url)
        authorization_response = (
            tmp if tmp[0:5] == "https" else tmp.replace(tmp[0:4], "https", 1)
        )
        state = dict(
            parse.parse_qsl(parse.urlparse(authorization_response).query)
        ).get("state", "")
        # the state is checked before the code is spent on the token exchange
        try:
            state_json = dict(json.loads(_crypto.decrypt(state)))
        except (InvalidToken, TypeError, ValueError):
            log.warning("google oauth callback: state refused")
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST, content=MESSAGE_OAUTH_INVALID_STATE
            )
        credentials = self.fetch_token(auth_code=authorization_response, state=state)
        try:
            json_credentials = credentials.to_json()
            user = await self.get_google_user(credentials)
            email = user.get("email")
            if user.get("email") == state_json.get("email"):
                db_credentials = await self.oauth_credential_repo.get(
                    email, user_id=user_id
                )
                if db_credentials:
                    db_credentials.updated_at = datetime.now()
                    db_credentials.credentials = json.loads(json_credentials)
                    await self.oauth_credential_repo.update(email, db_credentials)
                else:
                    await self.oauth_credential_repo.add(
                        email, json.loads(json_credentials), user_id=user_id
                    )
            user_info = UserInfo(email=email)
            return user_info
        except InvalidGrantError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_INVALID_GRANT,
            )
        except HttpError as error:
            raise HTTPException(
                status_code=error.status_code, content=error.error_details
            )
        except RefreshError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )
        except InvalidClientError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_INVALID_CLIENT,
            )

    def fetch_token(self, auth_code: str, state: str, is_integration: bool = False):
        """
        Fetch the OAuth 2.0 access token. Used in oauth2callback.

        Args:
            auth_code (str): The authorization code returned by the authorization server.
            state (str): The encrypted state returned by the authorization server.
            is_integration (bool): It is to check whether this is called for google service integration

        Returns:
            google.oauth2.credentials.Credentials: The OAuth 2.0 credentials.

        Raises:
            HTTPException: If there is an error during the authorization process,
                or when Google did not grant a scope the Forms import needs.
        """
        scopes = settings.GOOGLE_SHEET_SCOPE if is_integration else settings.GOOGLE_SCOPES
        try:
            flow = google_auth_oauthlib.flow.Flow.from_client_config(
                client_config=self.client_config,
                scopes=scopes,
                state=state,
                # the verifier of the challenge sent by authorize() for this state
                code_verifier=pkce_code_verifier(state),
                autogenerate_code_verifier=False,
            )
            flow.redirect_uri = (
                settings.GOOGLE_SHEET_REDIRECT_URL
                if is_integration
                else settings.GOOGLE_REDIRECT_URIS
            )
            (
                flow.fetch_token(code=auth_code)
                if is_integration
                else flow.fetch_token(authorization_response=auth_code)
            )
            credentials = flow.credentials
        except InvalidGrantError as error:
            log.warning("google token exchange refused: %s", error.error)
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_INVALID_GRANT,
            )
        except InvalidClientError as error:
            log.warning("google token exchange refused: %s", error.error)
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_INVALID_CLIENT,
            )
        except OAuth2Error as error:
            # any other error Google answers with (redirect_uri_mismatch,
            # unauthorized_client, ...) or a malformed callback
            log.warning("google token exchange refused: %s", error.error)
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )
        except HttpError as error:
            raise HTTPException(
                status_code=error.status_code, content=error.error_details
            )
        except RefreshError:
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
            )
        if not is_integration:
            _refuse_missing_scopes(
                granted_scopes(flow.oauth2session.token, scopes.split()),
                REQUIRED_FORMS_SCOPES,
            )
        return credentials

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
            current_date = OauthGoogleService.get_current_dt_in_google_format()
            if expiry_datetime < current_date:
                return await self.refresh_access_token(
                    oauth_credential=oauth_credential
                )
            return oauth_credential
        except HttpError:
            raise HTTPException(
                status_code=HTTPStatus.UNAUTHORIZED,
                content=MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY,
            )
        except InvalidGrantError:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN, content=MESSAGE_OAUTH_INVALID_GRANT
            )

    @staticmethod
    def get_current_dt_in_google_format():
        current_date = datetime.now()
        current_date = current_date.strftime(GOOGLE_DATETIME_FORMAT)
        current_date = datetime.strptime(current_date, GOOGLE_DATETIME_FORMAT)
        return current_date

    async def refresh_access_token(self, oauth_credential: Oauth2CredentialDocument):
        try:
            credentials = dict_to_credential(oauth_credential.credentials.dict())
            current_date = OauthGoogleService.get_current_dt_in_google_format()
            data = {
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "refresh_token": credentials.refresh_token,
                "grant_type": "refresh_token",
            }
            refreshed_token_response = await AiohttpClient.post(
                credentials.token_uri, data
            )
            token = await refreshed_token_response.json()
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
            saved_credentials = await self.oauth_credential_repo.update(
                oauth_credential.email, oauth_credential
            )
            return saved_credentials
        except TimeoutError:
            raise HTTPException(
                status_code=HTTPStatus.GATEWAY_TIMEOUT, content="Request Timed out"
            )

    async def get_google_user(self, credentials):
        try:
            oauth_service = build(
                serviceName="oauth2", version="v2", credentials=credentials
            )
            return oauth_service.userinfo().get().execute()
        except HttpError as error:
            raise HTTPException(
                status_code=error.status_code, content=error.error_details
            )
        except RefreshError:
            raise HTTPException(
                status_code=401, content="Google auth token refresh error."
            )
        except InvalidClientError as error:
            raise HTTPException(
                status_code=401, content="Google auth invalid client error."
            )
        except AttributeError:
            raise HTTPException(
                status_code=401,
                content="State not found. Connect with google services.",
            )
        except InvalidGrantError:
            raise HTTPException(401, "Invalid Grant error.")

    async def delete_oauth_credentials_for_user(self, email: EmailStr, user_id: str):
        return await self.oauth_credential_repo.delete_oauth_credential_for_user(
            email=email, user_id=user_id
        )

    async def get_oauth_credentials_for_user(self, email: EmailStr):
        return await self.oauth_credential_repo.get(email=email)

    async def get_encrypted_credential_for_user(self, email: EmailStr):
        if email is None:
            raise HTTPException(400, "Provide email")
        credentials = await self.get_oauth_credentials_for_user(email=email)
        encrypted_credential = _crypto.encrypt(credentials.json())
        return encrypted_credential

    def handle_integration_oauth_callback(self, code: str, state: str):
        credentials = self.fetch_token(state=state, auth_code=code, is_integration=True)
        json_credentials = credentials.to_json()
        google_credential = GoogleCredentialResponse(**json.loads(json_credentials))
        integration_credential = google_credential.dict()
        creds = _crypto.encrypt(json.dumps(integration_credential))
        return creds
