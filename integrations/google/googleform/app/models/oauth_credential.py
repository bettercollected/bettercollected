from typing import Optional

from pydantic import BaseModel


class GoogleCredentialResponse(BaseModel):
    """Data transfer object for a response to a request for Google credentials."""

    token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_uri: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    scopes: Optional[str] = None
    expiry: Optional[str] = None
