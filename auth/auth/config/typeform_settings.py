from pydantic import BaseSettings


class TypeformSettings(BaseSettings):
    auth_uri = "https://api.typeform.com/oauth/authorize?state={state}&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"
    token_uri = "https://api.typeform.com/oauth/token"
    scope = "accounts:read"
    client_id = ""
    client_secret = ""
    redirect_uri = ""
    api_uri = "https://api.typeform.com"

    class Config:
        env_prefix = "TYPEFORM_"
