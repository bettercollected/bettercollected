"""The Google Sheets action's OAuth flow and spreadsheet creation, run by the
backend itself (``GOOGLE_SHEETS_OAUTH=backend``).

It uses the Google sign-in client (``GOOGLE_CLIENT_ID``/``GOOGLE_CLIENT_SECRET``)
and asks for one scope only, ``drive.file``: access to the files this app
creates, which covers creating the spreadsheet and appending rows to it. All
calls to Google are plain HTTPS requests (no Google SDK).

The credential is stored exactly as the Google Forms service stored it, so the
actions executor reads and refreshes it unchanged: the Fernet encryption (key
``AUTH_AES_HEX_KEY``) of ``json.dumps`` of ``token``, ``refresh_token``,
``token_uri``, ``client_id``, ``client_secret``, ``scopes`` (a space-separated
string) and ``expiry`` (``%Y-%m-%dT%H:%M:%S.%fZ``, UTC), in that order.

Nothing here logs a token, a spreadsheet title or an address; only HTTP
status codes and Google's error codes.
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from typing import Optional
from urllib.parse import urlencode

import httpx
from common.configs.crypto import Crypto
from common.constants import (
    MESSAGE_OAUTH_FETCH_TOKEN_ERROR,
    MESSAGE_OAUTH_INVALID_CLIENT,
    MESSAGE_OAUTH_INVALID_GRANT,
    MESSAGE_OAUTH_MISSING_REFRESH_TOKEN,
    MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY,
)
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

from backend.app.exceptions import HTTPException
from backend.config import settings

DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
SHEETS_API_URL = "https://sheets.googleapis.com/v4/spreadsheets"
# The format the actions executor parses (models/date.py there).
CREDENTIAL_EXPIRY_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
# How long a started authorization may take before its state is refused.
STATE_MAX_AGE_SECONDS = 3600
# Refresh an access token that expires within this margin before using it.
REFRESH_MARGIN = timedelta(seconds=60)
REQUEST_TIMEOUT_SECONDS = 30

MESSAGE_NOT_CONFIGURED = "Google Sheets is not configured on this server."
MESSAGE_INVALID_STATE = "The authorization request is invalid or has expired."
MESSAGE_SCOPE_NOT_GRANTED = (
    "Google did not grant access to the spreadsheets this app creates. "
    "Connect again and allow it."
)
MESSAGE_GOOGLE_UNREACHABLE = "Google could not be reached. Try again later."
MESSAGE_SHEET_NOT_CREATED = "Error Creating Sheet in Google"
MESSAGE_SHEET_UNAUTHORIZED = (
    "Google refused access to create the spreadsheet. Connect Google Sheets again."
)

_PKCE_LABEL = b"google-sheets-pkce-v1|"


def pkce_code_verifier(state: str) -> str:
    """The PKCE verifier of the authorization request carrying ``state``.

    The authorization URL and the code exchange run in different requests
    (and possibly different replicas), so the verifier is derived from the
    state with a server-side key instead of being kept anywhere. Without the
    key an intercepted code and state cannot be exchanged. 43 characters from
    the unreserved set (RFC 7636 section 4.1).
    """
    digest = hmac.new(
        settings.auth_settings.AES_HEX_KEY.encode(),
        _PKCE_LABEL + state.encode(),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def pkce_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _utcnow() -> datetime:
    # naive UTC, as google-auth writes and the executor compares expiries
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _google_error(response: httpx.Response) -> str:
    """Google's error code of a failed token request (never its description)."""
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return "unknown"
    if isinstance(error, dict):  # the Sheets API's error object
        error = error.get("status")
    return error if isinstance(error, str) and error.isidentifier() else "unknown"


class GoogleSheetsOAuth:
    def __init__(
        self,
        crypto: Crypto,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ):
        self._crypto = crypto
        # tests replace it with a fake Google
        self.transport = transport

    @staticmethod
    def _client_config():
        config = settings.google_sheets
        if not config.CLIENT_ID or not config.CLIENT_SECRET:
            raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, MESSAGE_NOT_CONFIGURED)
        return config

    def _http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=self.transport, timeout=REQUEST_TIMEOUT_SECONDS
        )

    def authorization_url(self, state: str) -> str:
        config = self._client_config()
        params = {
            "client_id": config.CLIENT_ID,
            "redirect_uri": config.SHEET_REDIRECT_URL,
            "response_type": "code",
            "scope": DRIVE_FILE_SCOPE,
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
            # no scopes granted to this client earlier (sign-in, Forms) are
            # merged into the Sheets grant
            "include_granted_scopes": "false",
            "code_challenge": pkce_code_challenge(pkce_code_verifier(state)),
            "code_challenge_method": "S256",
        }
        return f"{config.AUTH_URI}?{urlencode(params)}"

    def _check_state_age(self, state: str) -> None:
        try:
            Fernet.decrypt(self._crypto, state, ttl=STATE_MAX_AGE_SECONDS)
        except (InvalidToken, TypeError, ValueError):
            raise HTTPException(HTTPStatus.BAD_REQUEST, MESSAGE_INVALID_STATE)

    async def _post_token(self, url: str, data: dict) -> dict:
        try:
            async with self._http() as client:
                response = await client.post(
                    url, data=data, headers={"Accept": "application/json"}
                )
        except httpx.TimeoutException:
            logger.warning("google sheets token request timed out")
            raise HTTPException(HTTPStatus.GATEWAY_TIMEOUT, MESSAGE_GOOGLE_UNREACHABLE)
        except httpx.HTTPError as error:
            logger.warning("google sheets token request failed: {}", type(error).__name__)
            raise HTTPException(HTTPStatus.BAD_GATEWAY, MESSAGE_GOOGLE_UNREACHABLE)
        if response.status_code != HTTPStatus.OK:
            error = _google_error(response)
            logger.warning(
                "google sheets token request refused: status={} error={}",
                response.status_code,
                error,
            )
            message = {
                "invalid_grant": MESSAGE_OAUTH_INVALID_GRANT,
                "invalid_client": MESSAGE_OAUTH_INVALID_CLIENT,
                "unauthorized_client": MESSAGE_OAUTH_INVALID_CLIENT,
            }.get(error, MESSAGE_OAUTH_FETCH_TOKEN_ERROR)
            raise HTTPException(HTTPStatus.EXPECTATION_FAILED, message)
        try:
            token = response.json()
        except ValueError:
            token = None
        if not isinstance(token, dict):
            logger.warning("google sheets token response is not a JSON object")
            raise HTTPException(
                HTTPStatus.EXPECTATION_FAILED, MESSAGE_OAUTH_FETCH_TOKEN_ERROR
            )
        if not token.get("access_token") or not isinstance(
            token.get("expires_in"), (int, float)
        ):
            logger.warning("google sheets token response without token or expiry")
            raise HTTPException(
                HTTPStatus.EXPECTATION_FAILED, MESSAGE_OAUTH_MISSING_TOKEN_OR_EXPIRY
            )
        return token

    async def exchange_code(self, code: str, state: str) -> str:
        """Exchange the authorization code; returns the encrypted credential."""
        config = self._client_config()
        self._check_state_age(state)
        token = await self._post_token(
            config.TOKEN_URI,
            {
                "code": code,
                "client_id": config.CLIENT_ID,
                "client_secret": config.CLIENT_SECRET,
                "redirect_uri": config.SHEET_REDIRECT_URL,
                "grant_type": "authorization_code",
                "code_verifier": pkce_code_verifier(state),
            },
        )
        # A response without ``scope`` grants what was requested (RFC 6749
        # section 5.1); with granular consent the user may have unticked it.
        granted = (token.get("scope") or DRIVE_FILE_SCOPE).split()
        if DRIVE_FILE_SCOPE not in granted:
            logger.warning("google sheets authorization without the drive.file scope")
            raise HTTPException(HTTPStatus.FORBIDDEN, MESSAGE_SCOPE_NOT_GRANTED)
        if not token.get("refresh_token"):
            # the executor refreshes the token on its own; without a refresh
            # token the action would stop working within the hour
            logger.warning("google sheets token response without a refresh token")
            raise HTTPException(
                HTTPStatus.EXPECTATION_FAILED, MESSAGE_OAUTH_MISSING_REFRESH_TOKEN
            )
        credential = {
            "token": token["access_token"],
            "refresh_token": token["refresh_token"],
            "token_uri": config.TOKEN_URI,
            "client_id": config.CLIENT_ID,
            "client_secret": config.CLIENT_SECRET,
            "scopes": DRIVE_FILE_SCOPE,
            "expiry": (_utcnow() + timedelta(seconds=token["expires_in"])).strftime(
                CREDENTIAL_EXPIRY_FORMAT
            ),
        }
        return self._crypto.encrypt(json.dumps(credential))

    async def _access_token(self, credential: dict) -> str:
        """The credential's access token, refreshed when it has (nearly) expired.

        The refreshed token is used for this request only; the stored
        credential is left as it is (the executor refreshes its own copy).
        """
        try:
            expiry = datetime.strptime(
                credential.get("expiry") or "", CREDENTIAL_EXPIRY_FORMAT
            )
        except ValueError:
            expiry = None
        if credential.get("token") and expiry and expiry - REFRESH_MARGIN > _utcnow():
            return credential["token"]
        if not credential.get("refresh_token") or not credential.get("token_uri"):
            raise HTTPException(
                HTTPStatus.UNAUTHORIZED, MESSAGE_OAUTH_MISSING_REFRESH_TOKEN
            )
        token = await self._post_token(
            credential["token_uri"],
            {
                "client_id": credential.get("client_id") or "",
                "client_secret": credential.get("client_secret") or "",
                "refresh_token": credential["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        return token["access_token"]

    async def create_spreadsheet(self, title: str, encrypted_credential: str) -> str:
        """Create a spreadsheet with the stored credential; returns its id."""
        try:
            credential = json.loads(self._crypto.decrypt(encrypted_credential))
        except (InvalidToken, TypeError, ValueError):
            credential = None
        if not isinstance(credential, dict):
            logger.warning("google sheets credential could not be read")
            raise HTTPException(HTTPStatus.UNAUTHORIZED, MESSAGE_SHEET_UNAUTHORIZED)
        access_token = await self._access_token(credential)
        try:
            async with self._http() as client:
                response = await client.post(
                    SHEETS_API_URL,
                    params={"fields": "spreadsheetId"},
                    json={"properties": {"title": title}},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.TimeoutException:
            logger.warning("google sheets creation timed out")
            raise HTTPException(HTTPStatus.GATEWAY_TIMEOUT, "Request Timed out")
        except httpx.HTTPError as error:
            logger.warning("google sheets creation failed: {}", type(error).__name__)
            raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, MESSAGE_SHEET_NOT_CREATED)
        if response.status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            logger.warning(
                "google sheets creation refused: status={}", response.status_code
            )
            raise HTTPException(HTTPStatus.UNAUTHORIZED, MESSAGE_SHEET_UNAUTHORIZED)
        spreadsheet_id = None
        if response.status_code == HTTPStatus.OK:
            try:
                spreadsheet_id = response.json().get("spreadsheetId")
            except (ValueError, AttributeError):
                spreadsheet_id = None
        if not isinstance(spreadsheet_id, str) or not spreadsheet_id:
            logger.warning(
                "google sheets creation failed: status={} error={}",
                response.status_code,
                _google_error(response),
            )
            raise HTTPException(HTTPStatus.SERVICE_UNAVAILABLE, MESSAGE_SHEET_NOT_CREATED)
        return spreadsheet_id
