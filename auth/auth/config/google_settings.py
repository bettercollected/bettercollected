from pydantic import BaseSettings


class GoogleSettings(BaseSettings):
    client_type: str = "web"
    client_id: str = ''
    project_id: str = ''
    auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    token_uri: str = "https://oauth2.googleapis.com/token"
    auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    client_secret: str = ''
    redirect_uris: str = ''
    basic_auth_redirect: str = ''
    javascript_origins: str = ''
    scopes: str = "email profile openid https://www.googleapis.com/auth/drive.metadata.readonly " \
                  "https://www.googleapis.com/auth/forms.body.readonly " \
                  "https://www.googleapis.com/auth/forms.responses.readonly "
    revoke_credentials_url: str = "https://oauth2.googleapis.com/revoke"

    class Config:
        env_prefix = "GOOGLE_"
