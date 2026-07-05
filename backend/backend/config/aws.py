from pydantic_settings import BaseSettings, SettingsConfigDict


class AWSSettings(BaseSettings):
    ACCESS_KEY_ID: str = ""
    SECRET_ACCESS_KEY: str = ""
    PRE_SIGNED_URL_EXPIRY: int = 10

    model_config = SettingsConfigDict(env_prefix='AWS_')
