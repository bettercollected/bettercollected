from datetime import datetime

from common.constants import GOOGLE_DATETIME_FORMAT

import google.oauth2.credentials


def dict_to_credential(credentials_dict):
    """
    Convert a dictionary to a Google oauth2 credentials object.

    Args:
        credentials_dict (dict): A dictionary containing the credentials' information.

    Returns:
        google.oauth2.credentials.Credentials: A Google oauth2 credentials object.
    """
    credentials = google.oauth2.credentials.Credentials(**credentials_dict)
    expiry = credentials.expiry
    if isinstance(expiry, datetime):
        expiry = expiry.strftime(GOOGLE_DATETIME_FORMAT)
    credentials.expiry = datetime.strptime(expiry, GOOGLE_DATETIME_FORMAT)
    return credentials
