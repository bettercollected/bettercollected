from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class GoogleSettings(BaseSettings):
    client_id: Optional[str] = ""
    project_id: Optional[str] = ""
    auth_uri: Optional[str] = "https://accounts.google.com/o/oauth2/auth"
    token_uri: Optional[str] = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url: Optional[str] = (
        "https://www.googleapis.com/oauth2/v1/certs"
    )
    client_secret: Optional[str] = ""
    redirect_uris: Optional[str] = ""
    basic_auth_redirect: Optional[str] = ""
    javascript_origins: Optional[str] = ""

    model_config = SettingsConfigDict(env_prefix="GOOGLE_")
