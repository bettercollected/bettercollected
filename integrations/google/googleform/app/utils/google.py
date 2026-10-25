from datetime import datetime

from common.constants import GOOGLE_DATETIME_FORMAT

import google.oauth2.credentials

from googleform.config import settings

#: Google's documented OAuth token endpoints. A stored ``token_uri`` that is
#: one of these is expected (older credentials carry the second one); either
#: way the refresh goes to the configured ``GOOGLE_TOKEN_URI``.
GOOGLE_TOKEN_URIS = frozenset(
    {
        "https://oauth2.googleapis.com/token",
        "https://accounts.google.com/o/oauth2/token",
    }
)


def dict_to_credential(credentials_dict):
    """
    Convert a dictionary to a Google oauth2 credentials object.

    Args:
        credentials_dict (dict): A dictionary containing the credentials' information.

    Returns:
        google.oauth2.credentials.Credentials: A Google oauth2 credentials object.

    The credential's own ``token_uri`` is not used: google-auth refreshes at it
    by itself, and a stored address would send the client secret and refresh
    token to any host. It is replaced (on a copy) by the configured
    ``GOOGLE_TOKEN_URI``.
    """
    credentials_dict = {**credentials_dict, "token_uri": settings.GOOGLE_TOKEN_URI}
    credentials = google.oauth2.credentials.Credentials(**credentials_dict)
    expiry = credentials.expiry
    if isinstance(expiry, datetime):
        expiry = expiry.strftime(GOOGLE_DATETIME_FORMAT)
    credentials.expiry = datetime.strptime(expiry, GOOGLE_DATETIME_FORMAT)
    return credentials
