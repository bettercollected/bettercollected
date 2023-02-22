from typing import Optional

from pydantic import BaseModel


class FormProviderConfigDto(BaseModel):
    enabled: bool
    provider_name: str
    provider_url: str
    auth_callback_url: str
    type: Optional[str]
    scope: Optional[str]
    client_id: Optional[str]
    client_secret: Optional[str]
    api_uri: Optional[str]
    auth_uri: Optional[str]
    token_uri: Optional[str]
    redirect_uri: Optional[str]
    revoke_uri: Optional[str]
