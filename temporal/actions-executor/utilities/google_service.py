from datetime import datetime, timedelta
from http import HTTPStatus

import google.oauth2.credentials
import google.oauth2.credentials
import httpx
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models.date import GOOGLE_DATETIME_FORMAT
from utilities.exceptions import HTTPException


def build_google_service(credentials, service_name: str, version: str = "v1"):
    return build(
        serviceName=service_name,
        version=version,
        credentials=dict_to_credential(credentials),
    )


def dict_to_credential(credentials_dict):
    print("id is : ", credentials_dict)
    credentials = google.oauth2.credentials.Credentials(**credentials_dict)
    expiry = credentials.expiry
    if isinstance(expiry, datetime):
        expiry = expiry.strftime(GOOGLE_DATETIME_FORMAT)
    credentials.expiry = datetime.strptime(expiry, GOOGLE_DATETIME_FORMAT)
    return credentials


def fetch_oauth_token(oauth_credential):
    try:
        credentials = dict_to_credential(oauth_credential)
        expiry_datetime = credentials.expiry
        current_date = get_current_dt_in_google_format()
        if expiry_datetime < current_date:
            return refresh_access_token(oauth_credential=oauth_credential)
        return oauth_credential
    except HttpError:
        raise HTTPException(
            status_code=HTTPStatus.UNAUTHORIZED,
            content="Either oauth access token is missing or expiry time is missing!",
        )


def refresh_access_token(oauth_credential):
    try:
        credentials = dict_to_credential(oauth_credential)
        current_date = get_current_dt_in_google_format()
        data = {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "grant_type": "refresh_token",
        }
        refreshed_token_response = httpx.post(
            url=credentials.token_uri, data=data
        )
        token = refreshed_token_response.json()
        if not token.get("access_token") or not token.get("expires_in"):
            raise HttpError()
        oauth_credential["token"] = token.get("access_token")
        expiry = current_date + timedelta(seconds=token.get("expires_in"))
        oauth_credential["expiry"] = expiry.strftime(
            GOOGLE_DATETIME_FORMAT
        )
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
