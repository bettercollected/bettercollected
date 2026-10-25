import json
import logging
from http import HTTPStatus
from datetime import datetime, timedelta

import httpx
import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from configs.crypto import crypto
from models.date import GOOGLE_DATETIME_FORMAT
from models.exception_enum import ExceptionType
from utilities.exceptions import HTTPException
from settings.application import settings

logger = logging.getLogger(__name__)

# Google's documented OAuth token endpoints. A credential's own ``token_uri``
# is only as trustworthy as whoever stored it (action secrets can be written
# through the API), and a stored address would make this worker post the
# client secret and refresh token to any host. Refreshes go to one of these
# and nowhere else; the field stays in the stored credential but is not used.
DEFAULT_GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_TOKEN_URIS = frozenset(
    {DEFAULT_GOOGLE_TOKEN_URI, "https://accounts.google.com/o/oauth2/token"}
)


def google_token_uri(stored_token_uri, action_id=None) -> str:
    """The endpoint to refresh at: the stored one only when it is one of
    Google's, otherwise Google's default (logged without the value)."""
    if stored_token_uri in GOOGLE_TOKEN_URIS:
        return stored_token_uri
    if stored_token_uri:
        logger.warning(
            "Ignored a credential token_uri that is not a Google token endpoint "
            "(action %s)",
            action_id or "unknown",
        )
    return DEFAULT_GOOGLE_TOKEN_URI


def build_google_service(credentials, service_name: str, version: str = "v1"):
    return build(
        serviceName=service_name,
        version=version,
        credentials=dict_to_credential(credentials),
    )


def dict_to_credential(credentials_dict, action_id=None):
    # google-auth refreshes at ``token_uri`` by itself when a call is refused
    # or the token has expired: pin it here too, on a copy.
    credentials_dict = {
        **credentials_dict,
        "token_uri": google_token_uri(credentials_dict.get("token_uri"), action_id),
    }
    credentials = google.oauth2.credentials.Credentials(**credentials_dict)
    expiry = credentials.expiry
    if isinstance(expiry, datetime):
        expiry = expiry.strftime(GOOGLE_DATETIME_FORMAT)
    credentials.expiry = datetime.strptime(expiry, GOOGLE_DATETIME_FORMAT)
    return credentials


def fetch_oauth_token(oauth_credential, action_id, form_id):
    try:
        credentials = dict_to_credential(oauth_credential, action_id)
        expiry_datetime = credentials.expiry
        current_date = get_current_dt_in_google_format()
        if expiry_datetime < current_date:
            updated_creds = refresh_access_token(
                oauth_credential=oauth_credential, action_id=action_id
            )
            # todo call backend to update creds
            update_credentials_in_form(updated_creds, action_id, form_id)
            return updated_creds
        return oauth_credential
    except HttpError:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            content="Either oauth access token is missing or expiry time is missing!",
        )


def refresh_access_token(oauth_credential, action_id=None):
    try:
        credentials = dict_to_credential(oauth_credential, action_id)
        current_date = get_current_dt_in_google_format()
        data = {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "grant_type": "refresh_token",
        }
        # credentials.token_uri is pinned to a Google endpoint above
        refreshed_token_response = httpx.post(url=credentials.token_uri, data=data)
        token = refreshed_token_response.json()
        if not token.get("access_token") or not token.get("expires_in"):
            raise HTTPException(
                status_code=HTTPStatus.EXPECTATION_FAILED,
                content=ExceptionType.OAUTH_TOKEN_MISSING,
            )
        oauth_credential["token"] = token.get("access_token")
        expiry = current_date + timedelta(seconds=token.get("expires_in"))
        oauth_credential["expiry"] = expiry.strftime(GOOGLE_DATETIME_FORMAT)
        return oauth_credential
    except TimeoutError:
        raise HTTPException(
            status_code=HTTPStatus.GATEWAY_TIMEOUT, content="Request Timed out"
        )


def get_current_dt_in_google_format():
    current_date = datetime.now()
    current_date = current_date.strftime(GOOGLE_DATETIME_FORMAT)
    current_date = datetime.strptime(current_date, GOOGLE_DATETIME_FORMAT)
    return current_date


def update_credentials_in_form(credentials: dict, action_id: str, form_id: str):
    creds = crypto.encrypt(json.dumps(credentials))
    payload = {"name": "Credentials", "value": creds, "type": "secrets"}
    # call backend to update the credentials in form
    httpx.patch(
        # in-network (SERVER_URL), never the public BACKEND_URL: the backend
        # refuses its internal routes through the public ingress
        url=f"{settings.server_url}/temporal/forms/{form_id}/actions/{action_id}/secrets",
        headers={"api-key": settings.api_key},
        json=payload,
    )
