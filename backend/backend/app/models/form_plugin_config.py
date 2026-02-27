from typing import Optional

from pydantic import BaseModel


class FormProviderConfigDto(BaseModel):
    enabled: bool
    provider_name: str
    provider_url: str
    auth_callback_url: str
    type: Optional[str] = None
    scope: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    api_uri: Optional[str] = None
    auth_uri: Optional[str] = None
    token_uri: Optional[str] = None
    redirect_uri: Optional[str] = None
    revoke_uri: Optional[str] = None
