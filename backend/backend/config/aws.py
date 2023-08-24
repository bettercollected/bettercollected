from pydantic import BaseSettings


class AWSSettings(BaseSettings):
    ACCESS_KEY_ID: str = ""
    SECRET_ACCESS_KEY: str = ""
    PRE_SIGNED_URL_EXPIRY: int = 10

    class Config:
        env_prefix = "AWS_"
