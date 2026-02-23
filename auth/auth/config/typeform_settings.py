from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class TypeformSettings(BaseSettings):
    auth_uri: Optional[str] = (
        "https://api.typeform.com/oauth/authorize?state={state}&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"
    )
    token_uri: Optional[str] = "https://api.typeform.com/oauth/token"
    scope: Optional[str] = "accounts:read"
    client_id: Optional[str] = ""
    client_secret: Optional[str] = ""
    redirect_uri: Optional[str] = ""
    api_uri: Optional[str] = "https://api.typeform.com"

    model_config = SettingsConfigDict(env_prefix="TYPEFORM_")
