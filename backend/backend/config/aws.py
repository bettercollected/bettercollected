from pydantic import BaseSettings


class AWSSettings(BaseSettings):
    access_key_id: str = ""
    secret_access_key: str = ""

    class Config:
        env_prefix = "AWS_"
