from pydantic import BaseSettings


class TypeformSettings(BaseSettings):
    auth_uri: str = "https://api.typeform.com/oauth/authorize?state={state}&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"
    token_uri: str = "https://api.typeform.com/oauth/token"
    scope: str = "accounts:read"
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    api_uri: str = "https://api.typeform.com"

    class Config:
        env_prefix = "TYPEFORM_"
