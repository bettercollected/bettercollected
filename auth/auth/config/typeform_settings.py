from pydantic import BaseSettings


class TypeformSettings(BaseSettings):
    auth_uri = ""
    token_uri = ""
    scope = ""
    client_id = ""
    client_secret = ""
    redirect_uri = ""
    api_uri = ""

    class Config:
        env_prefix = "TYPEFORM_"
