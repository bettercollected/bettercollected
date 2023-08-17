from pydantic import BaseSettings


class AWSSettings(BaseSettings):
    ACCESS_KEY_ID: str = ""
    SECRET_ACCESS_KEY: str = ""

    class Config:
        env_prefix = "AWS_"
