"""Application configuration - Redis."""
from typing import Optional

from pydantic_settings import BaseSettings


class Redis(BaseSettings):
    """Define Redis configuration model.

    Constructor will attempt to determine the values of any fields not passed
    as keyword arguments by reading from the environment. Default values will
    still be used if the matching environment variable is not set.

    Environment variables:
        * FASTAPI_REDIS_HOSTS
        * FASTAPI_REDIS_PORT
        * FASTAPI_REDIS_USERNAME
        * FASTAPI_REDIS_PASSWORD
        * FASTAPI_REDIS_USE_SENTINEL

    Attributes:
        REDIS_HOST (str): Redis host.
        REDIS_PORT (int): Redis port.
        REDIS_USERNAME (str): Redis username.
        REDIS_PASSWORD (str): Redis password.
        REDIS_USE_SENTINEL (bool): If provided Redis config is for Sentinel.

    """

    REDIS_HOST: Optional[str] = "127.0.0.1"
    REDIS_PORT: Optional[int] = 6379
    REDIS_USERNAME: Optional[str] = None
    REDIS_PASSWORD: Optional[str] = None
    REDIS_USE_SENTINEL: Optional[bool] = False

    class Config:
        """Config sub-class needed to customize BaseSettings settings.

        Attributes:
            case_sensitive (bool): When case_sensitive is True, the environment
                variable names must match field names (optionally with a prefix)
            env_prefix (str): The prefix for environment variable.

        Resources:
            https://pydantic-docs.helpmanual.io/usage/settings/

        """

        case_sensitive = True
        env_prefix = "FASTAPI_"


redis = Redis()
