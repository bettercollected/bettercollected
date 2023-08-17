from pydantic import BaseSettings


class GoogleSettings(BaseSettings):
    client_id: str = ""
    project_id: str = ""
    auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    token_uri: str = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    client_secret: str = ""
    redirect_uris: str = ""
    basic_auth_redirect: str = ""
    javascript_origins: str = ""

    class Config:
        env_prefix = "GOOGLE_"
