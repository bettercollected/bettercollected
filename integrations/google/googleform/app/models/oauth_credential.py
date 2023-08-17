from typing import Optional

from pydantic import BaseModel


class GoogleCredentialResponse(BaseModel):
    """Data transfer object for a response to a request for Google credentials."""

    token: Optional[str]
    refresh_token: Optional[str]
    token_uri: Optional[str]
    client_id: Optional[str]
    client_secret: Optional[str]
    scopes: Optional[str]
    expiry: Optional[str]
